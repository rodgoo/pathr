"""Administração de contas: quem vê a lista, e banir com a chave de acesso.

A assinatura WebAuthn é da py_webauthn (com suíte própria); aqui ela é trocada
por uma falsa que aceita ou recusa. O que se segura é o que é NOSSO: só o
super admin alcança; banir exige um desafio de moderação dele, com uma chave
DELE; não bane a si nem outro admin; banir revoga as sessões; e a conta banida
fica fora de toda rota, de toda sessão nova e das telas de amigos.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app import deps
from app.routers import admin as router
from app.routers import auth as auth_router
from app.routers import social
from app.security import create_access_token
from app.services import passkeys as chaves
from tests.fake_supabase import FakeSupabase

ADMIN_ID = "11111111-1111-1111-1111-111111111111"
ANA_ID = "22222222-2222-2222-2222-222222222222"
BIA_ID = "33333333-3333-3333-3333-333333333333"
CRED_ADMIN = "Y3JlZC1hZG1pbg"  # base64url, como o navegador manda
CRED_ANA = "Y3JlZC1hbmE"
VERIFICADO = "2026-09-01T00:00:00+00:00"

ADMIN = {"id": ADMIN_ID, "email": "chefe@exemplo.com", "name": "Chefe", "username": "chefe",
         "email_verified_at": VERIFICADO, "created_at": "2026-09-01T00:00:00+00:00"}
ANA = {"id": ANA_ID, "email": "ana@exemplo.com", "name": "Ana Souza", "username": "anasouza",
       "email_verified_at": VERIFICADO, "avatar_path": "u/ana.jpg", "created_at": "2026-09-10T00:00:00+00:00"}
BIA = {"id": BIA_ID, "email": "bia@exemplo.com", "name": "Bia Lima", "username": "bialima",
       "email_verified_at": VERIFICADO, "created_at": "2026-09-05T00:00:00+00:00",
       "banned_at": "2026-09-12T00:00:00+00:00", "banned_reason": "spam"}


def _pedido() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"user-agent", b"pytest")],
                    "client": ("127.0.0.1", 1), "query_string": b""})


def _futuro() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def _banco():
    return FakeSupabase(
        pathr_user=[dict(ADMIN), dict(ANA), dict(BIA)],
        pathr_passkey=[
            {"id": "p-admin", "user_id": ADMIN_ID, "credential_id": CRED_ADMIN, "public_key": "AQID", "sign_count": 0},
            {"id": "p-ana", "user_id": ANA_ID, "credential_id": CRED_ANA, "public_key": "AQID", "sign_count": 0},
        ],
        pathr_webauthn_challenge=[],
        pathr_refresh_token=[
            {"id": "s1", "user_id": ANA_ID, "revoked_at": None, "expires_at": _futuro()},
            {"id": "s2", "user_id": ANA_ID, "revoked_at": None, "expires_at": _futuro()},
            {"id": "s3", "user_id": ADMIN_ID, "revoked_at": None, "expires_at": _futuro()},
        ],
        pathr_security_event=[],
        pathr_profile=[],
    )


@pytest.fixture(autouse=True)
def _configuracao(monkeypatch):
    monkeypatch.setattr(router.settings, "super_admin_emails", ["chefe@exemplo.com"])
    monkeypatch.setattr(chaves.settings, "frontend_url", "https://pathr.notter.com.br")
    monkeypatch.setattr(chaves.settings, "webauthn_rp_id", "")


@pytest.fixture
def assinatura(monkeypatch):
    """A py_webauthn falsa: aceita por padrão; `recusar = True` faz falhar."""
    estado = SimpleNamespace(recusar=False)

    def verificar(**_kwargs):
        if estado.recusar:
            raise ValueError("assinatura inválida")
        return SimpleNamespace(new_sign_count=1)

    monkeypatch.setattr(router, "verify_authentication_response", verificar)
    return estado


def _desafio(banco) -> str:
    return router.pedir_confirmacao(ADMIN, banco)["challenge_id"]


# --- quem alcança ----------------------------------------------------------


def test_so_o_super_admin_alcanca():
    with pytest.raises(HTTPException) as erro:
        router.exigir_super_admin(ANA)
    assert erro.value.status_code == 404
    assert router.exigir_super_admin(ADMIN) is ADMIN


def test_sessao_diz_quem_e_super_admin():
    assert auth_router._user_out(ADMIN).is_super_admin is True
    assert auth_router._user_out(ANA).is_super_admin is False


# --- a lista -----------------------------------------------------------------


def test_lista_mostra_nome_email_foto_e_situacao():
    saida = router.listar_usuarios(admin=ADMIN, supabase=_banco())
    por_id = {u["id"]: u for u in saida["usuarios"]}
    assert [u["id"] for u in saida["usuarios"]] == [ANA_ID, BIA_ID, ADMIN_ID]  # mais novos primeiro
    assert por_id[ANA_ID]["email"] == "ana@exemplo.com" and por_id[ANA_ID]["has_avatar"] is True
    assert por_id[BIA_ID]["banned_at"] and por_id[BIA_ID]["banned_reason"] == "spam"
    assert por_id[ADMIN_ID]["voce"] is True and por_id[ADMIN_ID]["is_super_admin"] is True
    assert "password_hash" not in por_id[ANA_ID]


def test_lista_busca_e_filtra_banidos():
    banco = _banco()
    assert [u["id"] for u in router.listar_usuarios(busca="souza", admin=ADMIN, supabase=banco)["usuarios"]] == [ANA_ID]
    assert [u["id"] for u in router.listar_usuarios(busca="bia@", admin=ADMIN, supabase=banco)["usuarios"]] == [BIA_ID]
    assert [u["id"] for u in router.listar_usuarios(situacao="banidos", admin=ADMIN, supabase=banco)["usuarios"]] == [BIA_ID]
    # Sintaxe do filtro vira texto, não filtro.
    assert router.listar_usuarios(busca="a,id.eq.x", admin=ADMIN, supabase=banco)["usuarios"] == []


# --- banir exige a chave -----------------------------------------------------


def test_sem_chave_cadastrada_nao_da_para_confirmar():
    banco = _banco()
    banco.tabelas["pathr_passkey"] = [p for p in banco.tabelas["pathr_passkey"] if p["user_id"] != ADMIN_ID]
    with pytest.raises(HTTPException) as erro:
        router.pedir_confirmacao(ADMIN, banco)
    assert erro.value.status_code == 409


def test_confirmacao_so_oferece_as_chaves_do_admin():
    opcoes = router.pedir_confirmacao(ADMIN, _banco())["options"]
    assert [c["id"] for c in opcoes["allowCredentials"]] == [CRED_ADMIN]
    assert opcoes["userVerification"] == "required"


def test_banir_com_a_chave_marca_e_derruba_as_sessoes(assinatura):
    banco = _banco()
    corpo = router.Banir(motivo="Assédio a outros usuários", challenge_id=_desafio(banco), credential={"id": CRED_ADMIN})
    saida = router.banir(ANA_ID, corpo, _pedido(), ADMIN, banco)

    ana = next(u for u in banco.linhas("pathr_user") if u["id"] == ANA_ID)
    assert ana["banned_at"] and ana["banned_reason"] == "Assédio a outros usuários" and ana["banned_by"] == ADMIN_ID
    assert saida["banned_at"]
    sessoes = {s["id"]: s["revoked_at"] for s in banco.linhas("pathr_refresh_token")}
    assert sessoes["s1"] and sessoes["s2"], "as sessões da pessoa banida caem na hora"
    assert sessoes["s3"] is None, "as do admin continuam"
    assert any(e.get("event_type") == "user_banned" for e in banco.linhas("pathr_security_event"))


def test_banir_sem_assinatura_valida_nao_bane(assinatura):
    banco = _banco()
    assinatura.recusar = True
    corpo = router.Banir(motivo="spam", challenge_id=_desafio(banco), credential={"id": CRED_ADMIN})
    with pytest.raises(HTTPException) as erro:
        router.banir(ANA_ID, corpo, _pedido(), ADMIN, banco)
    assert erro.value.status_code == 403
    assert not next(u for u in banco.linhas("pathr_user") if u["id"] == ANA_ID).get("banned_at")


def test_chave_de_outra_pessoa_nao_serve(assinatura):
    banco = _banco()
    corpo = router.Banir(motivo="spam", challenge_id=_desafio(banco), credential={"id": CRED_ANA})
    with pytest.raises(HTTPException) as erro:
        router.banir(ANA_ID, corpo, _pedido(), ADMIN, banco)
    assert erro.value.status_code == 403


def test_desafio_e_de_uso_unico_e_so_de_moderacao(assinatura):
    banco = _banco()
    desafio = _desafio(banco)
    router.banir(ANA_ID, router.Banir(motivo="spam", challenge_id=desafio, credential={"id": CRED_ADMIN}), _pedido(), ADMIN, banco)
    with pytest.raises(HTTPException) as reuso:
        router.desbanir(ANA_ID, router.Assinatura(challenge_id=desafio, credential={"id": CRED_ADMIN}), _pedido(), ADMIN, banco)
    assert reuso.value.status_code == 400
    # Um desafio de LOGIN não serve para banir.
    login = router._guardar_desafio(banco, "login", b"x" * 32, ADMIN_ID)
    with pytest.raises(HTTPException):
        router.banir(ANA_ID, router.Banir(motivo="spam", challenge_id=login, credential={"id": CRED_ADMIN}), _pedido(), ADMIN, banco)


def test_nao_bane_a_si_nem_outro_admin(assinatura, monkeypatch):
    banco = _banco()
    corpo = router.Banir(motivo="teste", challenge_id=_desafio(banco), credential={"id": CRED_ADMIN})
    with pytest.raises(HTTPException) as proprio:
        router.banir(ADMIN_ID, corpo, _pedido(), ADMIN, banco)
    assert proprio.value.status_code == 400
    monkeypatch.setattr(router.settings, "super_admin_emails", ["chefe@exemplo.com", "ana@exemplo.com"])
    with pytest.raises(HTTPException) as outro:
        router.banir(ANA_ID, corpo, _pedido(), ADMIN, banco)
    assert outro.value.status_code == 403


def test_desbanir_devolve_a_conta(assinatura):
    banco = _banco()
    saida = router.desbanir(BIA_ID, router.Assinatura(challenge_id=_desafio(banco), credential={"id": CRED_ADMIN}), _pedido(), ADMIN, banco)
    bia = next(u for u in banco.linhas("pathr_user") if u["id"] == BIA_ID)
    assert bia["banned_at"] is None and saida["banned_at"] is None


# --- a conta banida fica de fora -----------------------------------------------


def test_banida_nao_recebe_sessao_nova():
    with pytest.raises(HTTPException) as erro:
        auth_router._issue_session(_banco(), dict(BIA), Response(), None)
    assert erro.value.status_code == 403
    assert "suspensa" in erro.value.detail


def test_banida_e_recusada_em_toda_rota_mesmo_com_token_valido():
    banco = _banco()
    banco.tabelas["pathr_refresh_token"].append({"id": "s-bia", "user_id": BIA_ID, "revoked_at": None, "expires_at": _futuro()})
    token = create_access_token(BIA_ID, "s-bia")
    pedido = Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                      "headers": [(b"cookie", f"{deps.ACCESS_COOKIE}={token}".encode())]})
    with pytest.raises(HTTPException) as erro:
        deps.get_current_user(pedido, banco)
    assert erro.value.status_code == 401 and "suspensa" in erro.value.detail


def test_banida_some_das_telas_de_amigos():
    banco = _banco()
    cartoes = social._cartoes(banco, [ANA_ID, BIA_ID], {})
    assert ANA_ID in cartoes and BIA_ID not in cartoes
    with pytest.raises(HTTPException):
        social._id_por_username(banco, "bialima")
