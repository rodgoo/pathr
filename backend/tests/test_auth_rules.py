"""As regras de entrada: quem pode criar conta e quem pode entrar.

Duas mudanças de política que este arquivo fixa:

1. **Cadastro pergunta nascimento e residência.** Sem eles a requisição é
   recusada — não são campos opcionais que o app preenche depois.
2. **Login exige e-mail confirmado.** Antes, a pessoa entrava na hora e
   confirmava quando quisesse. A troca fecha a porta para alguém criar conta
   com o e-mail de outra pessoa, já que é pelo e-mail que se recupera senha.

A consequência da regra 2 é testada junto: se o login exige confirmação, tem
de existir um caminho de reenvio que NÃO exija sessão, senão quem perdeu o
e-mail fica trancado do lado de fora com a conta já criada.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.database import get_supabase
from app.main import app
from app.schemas.auth import SignupRequest
from app.security import hash_password
from tests.fake_supabase import FakeSupabase

SENHA = "Senha-Bem-Longa-9!"

CADASTRO_VALIDO = {
    "name": "Rodrigo",
    "email": "pessoa@exemplo.com",
    "password": SENHA,
    "birth_date": "1998-04-12",
    "city": "Vitória",
    "state": "ES",
}


@pytest.fixture
def banco(monkeypatch):
    """Substitui o Supabase e silencia o envio de e-mail."""
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


def usuario(**campos) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "pessoa@exemplo.com",
        "name": "Rodrigo",
        "password_hash": hash_password(SENHA),
        "email_verified_at": None,
        "mfa_enabled": False,
        "failed_attempts": 0,
        "locked_until": None,
        "onboarding_completed": False,
        "locale": "pt-BR",
        "timezone_name": "America/Sao_Paulo",
        "theme": "system",
    }
    base.update(campos)
    return base


# ---------------------------------------------------------------------------
# 1. O cadastro pergunta nascimento e residência
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["birth_date", "city", "state"])
def test_cadastro_recusa_sem_os_campos_novos(campo):
    dados = {k: v for k, v in CADASTRO_VALIDO.items() if k != campo}
    with pytest.raises(ValidationError):
        SignupRequest(**dados)


def test_cadastro_aceita_o_conjunto_completo():
    pedido = SignupRequest(**CADASTRO_VALIDO)
    assert pedido.birth_date == date(1998, 4, 12)
    assert pedido.city == "Vitória"
    assert pedido.country == "BR"  # default, não precisa ser enviado


def test_nascimento_no_futuro_e_recusado():
    dados = {**CADASTRO_VALIDO, "birth_date": (date.today() + timedelta(days=1)).isoformat()}
    with pytest.raises(ValidationError, match="futuro"):
        SignupRequest(**dados)


def test_idade_abaixo_do_minimo_e_recusada():
    hoje = date.today()
    treze_anos = hoje.replace(year=hoje.year - 13)
    with pytest.raises(ValidationError, match="anos"):
        SignupRequest(**{**CADASTRO_VALIDO, "birth_date": treze_anos.isoformat()})


def test_aniversario_que_ainda_nao_chegou_conta_como_um_ano_a_menos():
    """A idade é em anos completos. Subtrair só os anos aceitaria alguém que
    faz 14 daqui a onze meses."""
    hoje = date.today()
    if (hoje.month, hoje.day) == (12, 31):  # sem "amanhã" no mesmo ano
        pytest.skip("virada de ano")
    amanha = hoje + timedelta(days=1)
    quase_14 = amanha.replace(year=amanha.year - 14)
    with pytest.raises(ValidationError):
        SignupRequest(**{**CADASTRO_VALIDO, "birth_date": quase_14.isoformat()})


def test_pais_e_normalizado_para_maiusculo():
    pedido = SignupRequest(**{**CADASTRO_VALIDO, "country": "br"})
    assert pedido.country == "BR"


def test_cadastro_grava_nascimento_e_residencia_no_perfil(cliente, banco):
    resposta = cliente.post("/auth/signup", json=CADASTRO_VALIDO)
    assert resposta.status_code == 201, resposta.text

    perfis = banco.linhas("pathr_profile")
    assert len(perfis) == 1
    assert perfis[0]["birth_date"] == "1998-04-12"
    assert perfis[0]["city"] == "Vitória"
    assert perfis[0]["state"] == "ES"
    assert perfis[0]["country"] == "BR"


# ---------------------------------------------------------------------------
# 2. Login exige e-mail confirmado
# ---------------------------------------------------------------------------


def test_cadastro_nao_devolve_sessao(cliente, banco):
    """O corpo não pode trazer token, e nenhum cookie pode sair. Se saísse, a
    pessoa entraria sem confirmar e a regra seria letra morta."""
    resposta = cliente.post("/auth/signup", json=CADASTRO_VALIDO)

    assert resposta.status_code == 201
    assert "access_token" not in resposta.json()
    assert not resposta.cookies
    assert banco.linhas("pathr_refresh_token") == []


def test_login_recusa_quem_nao_confirmou_o_email(cliente, banco):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at=None)]

    resposta = cliente.post(
        "/auth/login", json={"email": "pessoa@exemplo.com", "password": SENHA}
    )

    assert resposta.status_code == 403
    assert "Confirme seu e-mail" in resposta.json()["detail"]
    # Cabeçalho próprio para o frontend distinguir isto de senha errada e
    # oferecer o reenvio em vez de "tente de novo".
    assert resposta.headers.get("X-Pathr-Unverified") == "1"
    assert not resposta.cookies
    assert banco.linhas("pathr_refresh_token") == []


def test_login_deixa_entrar_depois_de_confirmado(cliente, banco):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at="2026-01-01T00:00:00+00:00")]

    resposta = cliente.post(
        "/auth/login", json={"email": "pessoa@exemplo.com", "password": SENHA}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["access_token"]
    assert len(banco.linhas("pathr_refresh_token")) == 1


def test_senha_errada_continua_401_e_nao_403(cliente, banco):
    """A ordem importa: o 403 de não-confirmado vem DEPOIS da senha. Se viesse
    antes, bastaria um e-mail qualquer para descobrir quem tem conta."""
    banco.tabelas["pathr_user"] = [usuario(email_verified_at=None)]

    resposta = cliente.post(
        "/auth/login", json={"email": "pessoa@exemplo.com", "password": "outra-senha-qualquer"}
    )

    assert resposta.status_code == 401
    assert "X-Pathr-Unverified" not in resposta.headers


def test_email_inexistente_nao_revela_nada(cliente, banco):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at=None)]

    resposta = cliente.post(
        "/auth/login", json={"email": "ninguem@exemplo.com", "password": SENHA}
    )

    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "E-mail ou senha incorretos."


# ---------------------------------------------------------------------------
# 3. O caminho de volta para quem não consegue entrar
# ---------------------------------------------------------------------------


def test_reenvio_publico_manda_novo_link_para_conta_pendente(cliente, banco):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at=None)]

    resposta = cliente.post(
        "/auth/resend-verification-public", json={"email": "pessoa@exemplo.com"}
    )

    assert resposta.status_code == 200
    assert len(banco.linhas("pathr_email_token")) == 1
    assert "verification_resent" in banco.eventos()


@pytest.mark.parametrize(
    "cenario,linhas",
    [
        ("conta inexistente", []),
        ("ja confirmada", [usuario(email_verified_at="2026-01-01T00:00:00+00:00")]),
    ],
)
def test_reenvio_publico_responde_igual_em_todos_os_casos(cliente, banco, cenario, linhas):
    """Mesma resposta para conta pendente, confirmada e inexistente — senão a
    rota vira um oráculo de quais e-mails têm conta."""
    banco.tabelas["pathr_user"] = linhas

    resposta = cliente.post(
        "/auth/resend-verification-public", json={"email": "pessoa@exemplo.com"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["detail"] == (
        "Se houver uma conta com este e-mail aguardando confirmação, enviamos um novo link."
    )
    assert banco.linhas("pathr_email_token") == []


# ---------------------------------------------------------------------------
# Renovação de sessão: corrida não é roubo
# ---------------------------------------------------------------------------
#
# Caso de produção: duas renovações quase simultâneas (várias chamadas da
# mesma tela expirando juntas) faziam a segunda cair em "reuso de token" e
# revogar TODAS as sessões. A pessoa clicava em desmarcar uma skill e era
# desconectada; e um aparelho derrubado derrubava o outro em cadeia.


from datetime import datetime, timezone  # noqa: E402

from app.deps import REFRESH_COOKIE  # noqa: E402
from app.security import hash_token  # noqa: E402


def _sessao(id_, token, *, revogada_ha=None, rotated_from=None, user_id="11111111-1111-1111-1111-111111111111"):
    agora = datetime.now(timezone.utc)
    return {
        "id": id_,
        "user_id": user_id,
        "token_hash": hash_token(token),
        "expires_at": (agora + timedelta(days=30)).isoformat(),
        "revoked_at": (agora - revogada_ha).isoformat() if revogada_ha is not None else None,
        "rotated_from": rotated_from,
        "created_at": agora.isoformat(),
    }


def _renova(cliente, token):
    cliente.cookies.set(REFRESH_COOKIE, token)
    return cliente.post("/auth/refresh")


def test_renovacao_concorrente_nao_derruba_as_sessoes(banco, cliente):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at="2026-01-01T00:00:00+00:00")]
    banco.tabelas["pathr_refresh_token"] = [
        # O token velho acabou de ser trocado por outra renovação da mesma tela.
        _sessao("velha", "token-velho", revogada_ha=timedelta(seconds=2)),
        _sessao("nova", "token-novo", rotated_from="velha"),
        _sessao("celular", "token-celular"),
    ]

    resposta = _renova(cliente, "token-velho")

    assert resposta.status_code == 200
    vivas = [s["id"] for s in banco.linhas("pathr_refresh_token") if not s.get("revoked_at")]
    assert {"nova", "celular"} <= set(vivas)
    assert "refresh_reuse" not in banco.eventos()


def test_token_de_sessao_ja_derrubada_nao_derruba_os_outros_aparelhos(banco, cliente):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at="2026-01-01T00:00:00+00:00")]
    banco.tabelas["pathr_refresh_token"] = [
        # Derrubada (logout/revogação geral): não tem sucessor.
        _sessao("pc", "token-pc", revogada_ha=timedelta(minutes=5)),
        _sessao("celular", "token-celular"),
    ]

    resposta = _renova(cliente, "token-pc")

    assert resposta.status_code == 401
    celular = next(s for s in banco.linhas("pathr_refresh_token") if s["id"] == "celular")
    assert celular.get("revoked_at") is None


def test_reuso_de_token_trocado_ha_tempo_continua_sendo_roubo(banco, cliente):
    banco.tabelas["pathr_user"] = [usuario(email_verified_at="2026-01-01T00:00:00+00:00")]
    banco.tabelas["pathr_refresh_token"] = [
        _sessao("velha", "token-roubado", revogada_ha=timedelta(hours=2)),
        _sessao("nova", "token-atual", rotated_from="velha"),
        _sessao("celular", "token-celular"),
    ]

    resposta = _renova(cliente, "token-roubado")

    assert resposta.status_code == 401
    assert all(s.get("revoked_at") for s in banco.linhas("pathr_refresh_token"))
    assert "refresh_reuse" in banco.eventos()
