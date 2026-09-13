"""O PathR com várias contas: nome de usuário, limites e a origem do IP.

Os três defeitos que estes testes seguram só aparecem quando há mais de uma
pessoa usando o app — com um usuário só, nenhum deles tinha como acontecer:

1. Uma pessoa esgotar um recurso de TODOS (e-mail, IA) por falta de limite.
2. O IP do log e do limite ser escolhido pelo próprio cliente.
3. Duas contas disputarem o mesmo @.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import client_ip
from app.main import app
from app.services import limites, usernames
from tests.fake_supabase import FakeSupabase

SENHA = "Senha-Bem-Longa-9!"
CADASTRO = {
    "name": "Rodrigo Carvalho",
    "email": "rodrigo@exemplo.com",
    "password": SENHA,
    "birth_date": "1998-04-12",
    "city": "Vitória",
    "state": "ES",
}


# ---------------------------------------------------------------------------
# Nome de usuário
# ---------------------------------------------------------------------------


def test_nomes_concatenados_primeiro_depois_underline_depois_numero():
    assert usernames.candidatos("Rodrigo Carvalho")[:5] == [
        "rodrigocarvalho",
        "rodrigo_carvalho",
        "rodrigocarvalho_",
        "rodrigocarvalho2",
        "rodrigo_carvalho2",
    ]


def test_sem_acento_sem_conectivo_e_sem_agnome():
    assert usernames.candidatos("José Ávila")[0] == "joseavila"
    assert usernames.candidatos("Maria da Silva")[0] == "mariasilva"
    assert usernames.candidatos("Rodrigo Augusto Pereira Carvalho Neto")[0] == "rodrigocarvalho"


def test_todo_candidato_tem_forma_valida():
    for nome in ("Rodrigo Carvalho", "Ana", "2Pac Shakur", "Ñandú Ç", "", "A B C D E F G H I J K L"):
        for candidato in usernames.candidatos(nome):
            assert usernames.problema(candidato) is None, (nome, candidato)


@pytest.mark.parametrize(
    "nome, motivo",
    [
        ("ro", "ao menos"),
        ("1rodrigo", "letra"),
        ("rod__go", "dois _"),
        ("rod-go", "minúsculas"),
        ("admin", "reservado"),
        ("a" * 25, "no máximo"),
    ],
)
def test_forma_invalida_diz_o_porque(nome, motivo):
    assert motivo in (usernames.problema(nome) or "")


def test_arroba_e_caixa_sao_ignorados():
    assert usernames.normalizar("  @RodGoo_ ") == "rodgoo_"
    assert usernames.problema("@RodGoo_") is None


def test_nome_ocupado_sugere_variacoes_do_proprio_nome_digitado():
    sugestoes = usernames.sugestoes_para("rodgoo", "Rodrigo Carvalho")
    assert sugestoes[0] == "rodgoo_"
    assert "rodgoo1" in sugestoes
    assert "rodrigocarvalho" in sugestoes


def test_primeiro_livre_pula_os_ocupados():
    ocupados = {"anasouza", "ana_souza", "anasouza_"}
    livre = usernames.primeiro_livre(usernames.candidatos("Ana Souza"), lambda lote: ocupados & set(lote))
    assert livre == "anasouza2"


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------


@pytest.fixture
def banco(monkeypatch):
    duplo = FakeSupabase()
    app.dependency_overrides[get_supabase] = lambda: duplo
    import app.routers.auth as rotas

    monkeypatch.setattr(rotas, "send_verification_email", lambda *a, **k: True)
    yield duplo
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(banco):
    with TestClient(app) as c:
        yield c


def test_quem_pula_o_username_ganha_os_nomes_concatenados(cliente, banco):
    assert cliente.post("/auth/signup", json=CADASTRO).status_code == 201
    assert banco.linhas("pathr_user")[0]["username"] == "rodrigocarvalho"


def test_segundo_homonimo_ganha_underline_entre_os_nomes(cliente, banco):
    cliente.post("/auth/signup", json=CADASTRO)
    cliente.post("/auth/signup", json={**CADASTRO, "email": "outro@exemplo.com"})
    assert [u["username"] for u in banco.linhas("pathr_user")] == ["rodrigocarvalho", "rodrigo_carvalho"]


def test_username_escolhido_e_gravado_normalizado(cliente, banco):
    resposta = cliente.post("/auth/signup", json={**CADASTRO, "username": "@RodGoo_"})
    assert resposta.status_code == 201
    assert banco.linhas("pathr_user")[0]["username"] == "rodgoo_"


def test_username_escolhido_ocupado_e_recusado_com_409(cliente, banco):
    cliente.post("/auth/signup", json={**CADASTRO, "username": "rodgoo_"})
    resposta = cliente.post(
        "/auth/signup", json={**CADASTRO, "email": "outro@exemplo.com", "username": "rodgoo_"}
    )
    assert resposta.status_code == 409
    assert len(banco.linhas("pathr_user")) == 1


def test_username_invalido_e_recusado_antes_de_criar_a_conta(cliente, banco):
    resposta = cliente.post("/auth/signup", json={**CADASTRO, "username": "a!"})
    assert resposta.status_code == 400
    assert banco.linhas("pathr_user") == []


def test_disponibilidade_sugere_quando_ocupado(cliente, banco):
    cliente.post("/auth/signup", json={**CADASTRO, "username": "rodgoo"})
    corpo = cliente.get("/social/username/disponivel", params={"username": "rodgoo", "nome": "Rodrigo"}).json()
    assert corpo["disponivel"] is False
    assert corpo["sugestoes"][0] == "rodgoo_"


def test_me_devolve_o_username(cliente, banco):
    from app.routers.auth import _user_out

    assert _user_out({"id": "1", "email": "a@b.c", "username": "rodgoo_"}).username == "rodgoo_"


# ---------------------------------------------------------------------------
# Limites
# ---------------------------------------------------------------------------

REGRA = limites.Regra("teste", 3, timedelta(hours=1), "chega")


def test_passa_do_limite_e_recebe_429_com_retry_after():
    banco = FakeSupabase()
    for _ in range(3):
        limites.consumir(banco, REGRA, "1.2.3.4")
    with pytest.raises(HTTPException) as erro:
        limites.consumir(banco, REGRA, "1.2.3.4")
    assert erro.value.status_code == 429
    assert erro.value.headers["Retry-After"] == "3600"


def test_o_limite_e_por_chave():
    banco = FakeSupabase()
    for _ in range(3):
        limites.consumir(banco, REGRA, "1.2.3.4")
    limites.consumir(banco, REGRA, "5.6.7.8")  # outra pessoa, outra conta


def test_uso_fora_da_janela_nao_conta():
    velho = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    banco = FakeSupabase(
        pathr_rate_event=[{"action": "teste", "key": "1.2.3.4", "created_at": velho}] * 5
    )
    limites.consumir(banco, REGRA, "1.2.3.4")


def test_banco_fora_do_ar_deixa_passar():
    """Um limite que derruba o login porque o Supabase piscou é pior que nenhum."""

    class Quebrado:
        def table(self, _nome):
            raise RuntimeError("fora do ar")

    limites.consumir(Quebrado(), REGRA, "1.2.3.4")


def test_sem_chave_nao_limita():
    banco = FakeSupabase()
    for _ in range(10):
        limites.consumir(banco, REGRA, None)


def test_esqueci_a_senha_limita_por_destino_mesmo_sem_conta(cliente, banco):
    """O limite vale exista a conta ou não: senão o 429 revelaria quem tem cadastro."""
    for _ in range(limites.EMAIL_POR_DESTINO.limite):
        assert cliente.post("/auth/forgot-password", json={"email": "ninguem@exemplo.com"}).status_code == 200
    assert cliente.post("/auth/forgot-password", json={"email": "ninguem@exemplo.com"}).status_code == 429


def test_cota_de_ia_e_por_usuario_e_so_com_usuario():
    banco = FakeSupabase()
    marca = limites.usuario_da_requisicao.set("user-a")
    try:
        for _ in range(limites.IA_POR_USUARIO.limite):
            limites.consumir_ia(lambda: banco)
        with pytest.raises(HTTPException):
            limites.consumir_ia(lambda: banco)
    finally:
        limites.usuario_da_requisicao.reset(marca)
    # Sem usuário (tarefa do próprio app) não conta nem trava.
    limites.consumir_ia(lambda: banco)


def test_middleware_anota_o_usuario_do_token_para_a_cota():
    import asyncio

    from app.middleware_usuario import UsuarioDaRequisicao
    from app.security import create_access_token

    visto = {}

    async def rota(scope, receive, send):
        visto["usuario"] = limites.usuario_da_requisicao.get()

    token = create_access_token("user-42", "sessao-1")
    scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
    asyncio.run(UsuarioDaRequisicao(rota)(scope, None, None))
    assert visto["usuario"] == "user-42"
    assert limites.usuario_da_requisicao.get() is None


# ---------------------------------------------------------------------------
# Origem do IP
# ---------------------------------------------------------------------------


class _Requisicao:
    def __init__(self, headers, host="10.0.0.9"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_na_fly_cabecalho_forjado_pelo_cliente_e_ignorado(monkeypatch):
    """A API recebe tráfego direto da Fly, sem Cloudflare: `cf-connecting-ip`
    e o começo de `x-forwarded-for` são o que o cliente quiser."""
    monkeypatch.setenv("FLY_APP_NAME", "pathr-backend")
    forjado = _Requisicao(
        {"cf-connecting-ip": "6.6.6.6", "x-forwarded-for": "7.7.7.7", "fly-client-ip": "200.1.2.3"}
    )
    assert client_ip(forjado) == "200.1.2.3"


def test_fora_da_fly_mantem_a_ordem_antiga(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    assert client_ip(_Requisicao({"cf-connecting-ip": "8.8.8.8"})) == "8.8.8.8"
