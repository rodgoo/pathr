"""Aparelhos conectados e o e-mail de novo acesso."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import get_current_user_allow_unverified
from app.main import app
from app.routers import sessoes
from app.services import aparelho
from tests.fake_supabase import FakeSupabase

ANA = "aaaaaaaa-0000-0000-0000-000000000001"
BRUNO = "bbbbbbbb-0000-0000-0000-000000000002"
FAM_PC = "11111111-0000-0000-0000-00000000000a"
FAM_CEL = "22222222-0000-0000-0000-00000000000b"
FAM_BRUNO = "33333333-0000-0000-0000-00000000000c"

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
SAFARI_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
EDGE_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 Edg/140.0"


def _token(id_, user, familia, ua, *, criado_ha=timedelta(minutes=5), revogado=False, ip="189.40.12.7"):
    agora = datetime.now(timezone.utc)
    return {
        "id": id_, "user_id": user, "family_id": familia, "user_agent": ua, "ip": ip,
        "token_hash": id_, "created_at": (agora - criado_ha).isoformat(),
        "expires_at": (agora + timedelta(days=20)).isoformat(),
        "revoked_at": (agora - timedelta(minutes=1)).isoformat() if revogado else None,
    }


@pytest.fixture
def banco():
    return FakeSupabase(pathr_refresh_token=[
        _token("pc-1", ANA, FAM_PC, CHROME_WIN, criado_ha=timedelta(days=3), revogado=True),
        _token("pc-2", ANA, FAM_PC, CHROME_WIN, criado_ha=timedelta(minutes=10)),
        _token("cel-1", ANA, FAM_CEL, SAFARI_IPHONE, criado_ha=timedelta(hours=5)),
        _token("bruno-1", BRUNO, FAM_BRUNO, EDGE_WIN),
    ])


@pytest.fixture
def cliente(banco):
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user_allow_unverified] = lambda: {
        "id": ANA, "email": "ana@x.com", "name": "Ana", "session_id": "pc-2",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lista_um_aparelho_por_login_com_o_atual_primeiro_e_nada_de_outra_conta(cliente):
    lista = cliente.get("/auth/sessoes").json()
    assert [s["id"] for s in lista] == [FAM_PC, FAM_CEL]
    pc, cel = lista
    assert pc["este_aparelho"] is True and pc["aparelho"] == "Chrome no Windows"
    assert cel["aparelho"] == "Safari no iPhone" and cel["celular"] is True
    assert pc["ip"] == "189.40.12.…"
    # "entrou em" é o começo da família, e não a última renovação.
    assert pc["entrou_em"] < pc["ultimo_uso"]
    assert "token_hash" not in str(lista)


def test_encerrar_revoga_a_familia_inteira_so_daquela_conta(cliente, banco):
    assert cliente.delete(f"/auth/sessoes/{FAM_CEL}").status_code == 204
    estado = {t["id"]: t.get("revoked_at") for t in banco.linhas("pathr_refresh_token")}
    assert estado["cel-1"] and estado["pc-2"] is None and estado["bruno-1"] is None
    assert [s["id"] for s in cliente.get("/auth/sessoes").json()] == [FAM_PC]


def test_nao_encerra_sessao_de_outra_conta_nem_diz_que_existe(cliente, banco):
    assert cliente.delete(f"/auth/sessoes/{FAM_BRUNO}").status_code == 404
    assert cliente.delete("/auth/sessoes/nao-e-uuid").status_code == 404
    bruno = next(t for t in banco.linhas("pathr_refresh_token") if t["id"] == "bruno-1")
    assert bruno["revoked_at"] is None


def test_aparelho_novo_so_quando_navegador_e_sistema_nunca_entraram(banco):
    assert sessoes.aparelho_novo(banco, ANA, CHROME_WIN.replace("140.0", "141.0")) is False  # só atualizou
    assert sessoes.aparelho_novo(banco, ANA, EDGE_WIN) is True
    # Primeiro login da conta: não há com o que comparar, não é "novo acesso".
    assert sessoes.aparelho_novo(banco, "cccccccc-0000-0000-0000-000000000003", EDGE_WIN) is False


def test_descricao_do_aparelho():
    assert aparelho.descrever(EDGE_WIN) == "Edge no Windows"
    assert aparelho.descrever(SAFARI_IPHONE) == "Safari no iPhone"
    assert aparelho.descrever(None) == "Navegador desconhecido no sistema desconhecido"
    assert aparelho.ip_mascarado("2804:14c:5b84:8f10::1") == "2804:14c:5b84:…"


def test_email_de_novo_acesso_diz_o_aparelho_e_o_que_fazer(monkeypatch):
    from app.services import email as emails

    capturado = {}
    monkeypatch.setattr(emails, "_send", lambda to, nome, assunto, html: capturado.update(a=assunto, h=html) or True)
    assert emails.send_new_login(
        "ana@x.com", "Ana Souza", aparelho="Edge no Windows", ip="189.40.12.…",
        quando=datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc), metodo="senha",
    )
    assert capturado["a"] == "Novo acesso à sua conta do PathR: Edge no Windows"
    assert "15/09/2026 às 12:00" in capturado["h"] and "Aparelhos conectados" in capturado["h"]


def test_mesmo_dispositivo_colapsa_em_uma_linha(cliente, banco):
    # Duas famílias (dois logins), mesmo device_id: uma linha só na lista.
    DEV = "dddddddd-0000-0000-0000-0000000000d0"

    def tok(id_, fam, criado_ha):
        t = _token(id_, ANA, fam, CHROME_WIN, criado_ha=criado_ha)
        t["device_id"] = DEV
        return t

    banco.tabelas["pathr_refresh_token"] = [
        tok("pc-2", FAM_PC, timedelta(minutes=10)),  # sessão atual (session_id do fixture)
        tok("re-1", "99999999-0000-0000-0000-00000000009a", timedelta(hours=2)),
    ]
    lista = cliente.get("/auth/sessoes").json()
    assert [s["id"] for s in lista] == [DEV]
    assert lista[0]["este_aparelho"] is True

    # Encerrar por device_id revoga as duas famílias do aparelho.
    assert cliente.delete(f"/auth/sessoes/{DEV}").status_code == 204
    assert all(t.get("revoked_at") for t in banco.linhas("pathr_refresh_token"))


def test_cookie_limpo_herda_o_dispositivo_da_sessao_viva_do_mesmo_navegador():
    """Sem cookie, o aparelho é reconhecido por uma sessão VIVA do mesmo
    usuário no mesmo navegador+sistema — limpar cookies não vira aparelho novo."""
    from app.routers import auth

    agora = datetime.now(timezone.utc)
    banco = FakeSupabase(pathr_refresh_token=[
        {"id": "s1", "user_id": "u1", "device_id": "dev-1", "user_agent": CHROME_WIN,
         "created_at": (agora - timedelta(hours=1)).isoformat(),
         "expires_at": (agora + timedelta(days=10)).isoformat(), "revoked_at": None},
    ])
    # mesmo navegador -> herda o device_id existente
    assert auth._dispositivo_por_assinatura(banco, "u1", CHROME_WIN) == "dev-1"
    # navegador diferente -> não herda (aparelho de verdade novo)
    assert auth._dispositivo_por_assinatura(banco, "u1", SAFARI_IPHONE) is None
    # sessão já revogada não empresta a identidade
    banco.tabelas["pathr_refresh_token"][0]["revoked_at"] = agora.isoformat()
    assert auth._dispositivo_por_assinatura(banco, "u1", CHROME_WIN) is None
