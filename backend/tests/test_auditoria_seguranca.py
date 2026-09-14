"""As brechas achadas na auditoria de segurança, cada uma presa por um teste.

Um teste por defeito, com o ataque descrito em uma linha: se alguém desfizer
a trava sem querer, o teste diz qual porta reabriu.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app import deps
from app.config import settings
from app.limite_corpo import LimiteDeCorpo
from app.routers import auth as auth_router
from app.routers import quizzes, roadmap
from app.services import resource_search as rs
from app.services.upload import ler_com_limite
from tests.fake_supabase import FakeSupabase

AGORA = datetime.now(timezone.utc)
USUARIO = {"id": "11111111-1111-1111-1111-111111111111", "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}


# --- sessão -----------------------------------------------------------------


def test_producao_nao_sobe_sem_segredo_forte():
    """Ataque: JWT_SECRET_KEY esquecida na Fly → tokens assinados com "" → forja de qualquer conta."""
    fraca = settings.model_copy(update={"environment": "production", "jwt_secret_key": "", "mfa_encryption_key": "", "data_encryption_key": ""})
    problemas = fraca.problemas_de_producao()
    assert any("JWT_SECRET_KEY" in p for p in problemas)
    assert any("MFA_ENCRYPTION_KEY" in p for p in problemas) and any("DATA_ENCRYPTION_KEY" in p for p in problemas)
    forte = settings.model_copy(update={"environment": "production", "jwt_secret_key": "x" * 40, "mfa_encryption_key": "m", "data_encryption_key": "d"})
    assert forte.problemas_de_producao() == []
    assert settings.model_copy(update={"environment": "development", "jwt_secret_key": ""}).problemas_de_producao() == []


def test_sessao_de_outra_conta_nao_autoriza_o_token():
    """Ataque: token forjado com `sub` da vítima e o `sid` de uma sessão viva qualquer."""
    banco = FakeSupabase(pathr_refresh_token=[
        {"id": "s1", "user_id": "dono", "revoked_at": None, "expires_at": (AGORA + timedelta(days=1)).isoformat()},
    ])
    assert deps._session_is_live(banco, "s1", "dono") is True
    assert deps._session_is_live(banco, "s1", "vitima") is False


def test_em_producao_fora_da_fly_o_ip_nao_vem_do_cliente(monkeypatch):
    """Ataque: `X-Forwarded-For` inventado a cada pedido para fugir do limite por IP."""
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    monkeypatch.setattr(deps, "settings", settings.model_copy(update={"environment": "production"}))
    pedido = Request({"type": "http", "headers": [(b"x-forwarded-for", b"1.2.3.4")], "client": ("9.9.9.9", 1)})
    assert deps.client_ip(pedido) == "9.9.9.9"


def test_cookie_velho_de_outro_navegador_na_janela_de_corrida_e_roubo():
    """Ataque: cookie de renovação copiado, usado logo depois de o dono renovar."""
    revogado = {"id": "s1", "revoked_at": (AGORA - timedelta(seconds=5)).isoformat()}
    banco = FakeSupabase(pathr_refresh_token=[{"id": "s2", "rotated_from": "s1", "created_at": AGORA.isoformat(), "user_agent": "Chrome"}])

    def pedido(agente: str) -> Request:
        return Request({"type": "http", "headers": [(b"user-agent", agente.encode())], "client": ("1.1.1.1", 1)})

    assert auth_router._reuso(banco, revogado, pedido("Chrome")) == "corrida"
    assert auth_router._reuso(banco, revogado, pedido("curl/8.0")) == "roubo"


# --- SSRF -------------------------------------------------------------------


@pytest.fixture
def rede_falsa(monkeypatch):
    """Toda URL "interna" é recusada pela trava; a pública redireciona para a interna."""
    original = httpx.AsyncClient
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        if pedido.url.host == "redireciona.exemplo":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200)

    monkeypatch.setattr(rs, "url_publica", lambda url: "169.254" not in url and "interno" not in url)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(responder), **kw))
    return pedidos


async def test_curadoria_nao_faz_pedido_a_endereco_interno(rede_falsa):
    """Ataque: nome de tag com injeção faz a IA devolver o metadata da máquina como "material"."""
    entrada = [
        rs.Candidate(kind="article", title="ok", url="https://publico.exemplo/a", provider="x"),
        rs.Candidate(kind="doc", title="metadata", url="http://169.254.169.254/latest/meta-data/", provider="ia"),
        rs.Candidate(kind="doc", title="rede", url="http://servico.interno:8080/admin", provider="ia"),
        rs.Candidate(kind="doc", title="salto", url="https://redireciona.exemplo/x", provider="ia"),
    ]
    saida = await rs._keep_reachable(entrada)
    assert [c.url for c in saida] == ["https://publico.exemplo/a"]
    assert not any("169.254" in url or "interno" in url for url in rede_falsa), "nenhum pedido saiu para dentro"


# --- uploads ----------------------------------------------------------------


async def test_upload_para_de_ler_no_limite():
    """Ataque: arquivo gigante para ocupar a memória antes de ouvir "grande demais"."""
    grande = UploadFile(file=BytesIO(b"x" * 300_000), filename="a.pdf")
    with pytest.raises(HTTPException) as erro:
        await ler_com_limite(grande, 100_000, "grande")
    assert erro.value.status_code == 413
    pequeno = UploadFile(file=BytesIO(b"abc"), filename="a.pdf")
    assert await ler_com_limite(pequeno, 100_000, "grande") == b"abc"


def test_corpo_acima_do_teto_e_recusado_antes_da_rota():
    chamadas = []

    async def rota(pedido):
        chamadas.append(1)
        return PlainTextResponse("ok")

    app = LimiteDeCorpo(Starlette(routes=[Route("/", rota, methods=["POST"])]), maximo_bytes=100)
    cliente = TestClient(app)
    assert cliente.post("/", content=b"x" * 500).status_code == 413
    assert chamadas == []
    assert cliente.post("/", content=b"x" * 50).status_code == 200


# --- XP e trilha ------------------------------------------------------------


def test_refazer_o_mesmo_quiz_nao_rende_xp_nem_nivel(monkeypatch):
    """Ataque: enviar o mesmo quiz em laço para inflar XP e proficiência."""
    creditos = []
    monkeypatch.setattr(quizzes, "_owned_quiz", lambda *a: {"id": "Q1", "title": "Quiz", "tag_ids": ["t1"]})
    monkeypatch.setattr(quizzes, "_recycle", lambda *a, **k: {})
    monkeypatch.setattr(quizzes, "_apply_result_to_tags", lambda *a, **k: creditos.append("nivel"))
    monkeypatch.setattr(quizzes, "log_activity", lambda *a, **k: creditos.append("xp"))
    banco = FakeSupabase(
        pathr_question=[{"id": "q1", "quiz_id": "Q1", "order_index": 0, "correct": {"index": 1}, "explanation": "x"}],
        pathr_attempt=[],
    )
    corpo = quizzes.SubmitAnswers(answers={"q1": 1}, duration_s=60)
    quizzes.submit_quiz("Q1", corpo, USUARIO, banco)
    quizzes.submit_quiz("Q1", corpo, USUARIO, banco)
    assert creditos == ["nivel", "xp"], "só a primeira tentativa conta"
    assert len(banco.linhas("pathr_attempt")) == 2, "as duas tentativas continuam gravadas"


def _trilha(**no):
    return FakeSupabase(
        pathr_roadmap=[{"id": "R1", "user_id": USUARIO["id"]}],
        pathr_roadmap_node=[{"id": "N1", "roadmap_id": "R1", "title": "Git", "tag_ids": ["t1"], **no}],
        pathr_activity=[],
    )


def test_modulo_travado_nao_se_conclui_pela_api():
    """Ataque: PATCH direto no módulo travado pulando a ordem da trilha."""
    with pytest.raises(HTTPException) as erro:
        roadmap.patch_node("N1", roadmap.NodePatch(status="done"), USUARIO, _trilha(status="locked"))
    assert erro.value.status_code == 409


def test_reabrir_e_concluir_de_novo_nao_rende_xp(monkeypatch):
    """Ataque: alternar "a fazer" / "concluído" para ganhar XP e nível a cada volta."""
    creditos = []
    monkeypatch.setattr(roadmap, "log_activity", lambda *a, **k: creditos.append("xp"))
    monkeypatch.setattr(roadmap, "_bump_proficiency", lambda *a, **k: creditos.append("nivel"))
    monkeypatch.setattr(roadmap, "_destravar_dependentes", lambda *a, **k: None)
    monkeypatch.setattr(roadmap, "_advance_next", lambda *a, **k: None)

    roadmap.patch_node("N1", roadmap.NodePatch(status="done"), USUARIO, _trilha(status="doing", completed_at=None))
    assert creditos == ["xp", "nivel"]
    creditos.clear()
    ja_concluido = _trilha(status="todo", completed_at=(AGORA - timedelta(days=1)).isoformat())
    roadmap.patch_node("N1", roadmap.NodePatch(status="done"), USUARIO, ja_concluido)
    assert creditos == []
