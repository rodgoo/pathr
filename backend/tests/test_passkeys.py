"""Chave de acesso: o que dá para conferir sem um autenticador de verdade.

A assinatura em si é da py_webauthn, que tem a própria suíte. Aqui: o domínio,
a origem, o nome, as opções geradas, o desafio de uso único e as recusas que
acontecem ANTES da criptografia.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.routers import passkeys as router
from app.services import passkeys as chaves
from tests.fake_supabase import FakeSupabase

USUARIO = {"id": "11111111-1111-1111-1111-111111111111", "email": "ana@exemplo.com", "name": "Ana"}


def _pedido() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 1234),
            "query_string": b"",
        }
    )


def _banco(**extra):
    tabelas = {
        "pathr_webauthn_challenge": [],
        "pathr_passkey": [],
        "pathr_user": [dict(USUARIO, email_verified_at="2026-09-01T00:00:00+00:00")],
        "pathr_security_event": [],
    }
    tabelas.update(extra)
    return FakeSupabase(**tabelas)


@pytest.fixture(autouse=True)
def _site(monkeypatch):
    monkeypatch.setattr(chaves.settings, "frontend_url", "https://pathr.notter.com.br")
    monkeypatch.setattr(chaves.settings, "webauthn_rp_id", "")


# --- domínio, origem, nome -------------------------------------------------


def test_dominio_e_o_do_site_e_nao_o_de_cima():
    """notter.com.br faria a chave valer também para o Notter e o FinanceR."""
    assert chaves.rp_id() == "pathr.notter.com.br"
    assert chaves.origem() == "https://pathr.notter.com.br"


def test_dominio_pode_ser_sobrescrito(monkeypatch):
    monkeypatch.setattr(chaves.settings, "webauthn_rp_id", "localhost")
    assert chaves.rp_id() == "localhost"


@pytest.mark.parametrize(
    "agente,nome",
    [
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Chrome no Windows"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Version/17.5 Mobile/15E148 Safari/604.1", "Safari no iPhone"),
        ("Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/128.0 Safari/537.36 Edg/128.0", "Edge no Windows"),
        ("", "Chave de acesso"),
    ],
)
def test_nome_do_aparelho(agente, nome):
    assert chaves.nome_do_aparelho(agente) == nome


# --- opções ------------------------------------------------------------------


def test_opcoes_de_cadastro_exigem_chave_descobrivel_e_guardam_o_desafio():
    banco = _banco()
    resposta = router.opcoes_de_cadastro(current_user=USUARIO, supabase=banco)
    assert resposta["options"]["rp"]["id"] == "pathr.notter.com.br"
    assert resposta["options"]["authenticatorSelection"]["residentKey"] == "required"
    assert resposta["options"]["authenticatorSelection"]["userVerification"] == "required"
    guardado = banco.linhas("pathr_webauthn_challenge")[0]
    assert guardado["purpose"] == "register"
    assert guardado["challenge"] == resposta["options"]["challenge"]


def test_opcoes_de_entrada_nao_listam_credenciais():
    """Pedir o e-mail antes contaria a quem sonda quais endereços têm chave."""
    banco = _banco()
    resposta = router.opcoes_de_entrada(supabase=banco)
    assert not resposta["options"].get("allowCredentials")
    assert banco.linhas("pathr_webauthn_challenge")[0]["user_id"] is None


# --- desafio -------------------------------------------------------------------


def test_desafio_e_de_uso_unico():
    banco = _banco()
    cid = router._guardar_desafio(banco, "login", b"x" * 32)
    assert router._consumir_desafio(banco, cid, "login") == b"x" * 32
    with pytest.raises(HTTPException) as erro:
        router._consumir_desafio(banco, cid, "login")
    assert erro.value.status_code == 400


def test_desafio_vencido_nao_serve():
    vencido = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    banco = _banco()
    banco.tabelas["pathr_webauthn_challenge"].append(
        {"id": "22222222-2222-2222-2222-222222222222", "purpose": "login",
         "challenge": "eHh4", "expires_at": vencido, "used_at": None, "user_id": None}
    )
    with pytest.raises(HTTPException):
        router._consumir_desafio(banco, "22222222-2222-2222-2222-222222222222", "login")


def test_desafio_de_cadastro_nao_serve_para_entrar():
    banco = _banco()
    cid = router._guardar_desafio(banco, "register", b"y" * 32, USUARIO["id"])
    with pytest.raises(HTTPException):
        router._consumir_desafio(banco, cid, "login")


def test_id_malformado_e_400_e_nao_500():
    with pytest.raises(HTTPException) as erro:
        router._consumir_desafio(_banco(), "nao-e-uuid", "login")
    assert erro.value.status_code == 400


# --- recusas antes da criptografia --------------------------------------------


def test_chave_desconhecida_e_recusada_e_auditada():
    banco = _banco()
    cid = router._guardar_desafio(banco, "login", b"z" * 32)
    with pytest.raises(HTTPException) as erro:
        router.entrar(
            payload=router.VerificarEntrada(
                challenge_id=cid, credential={"id": "desconhecida", "type": "public-key"}
            ),
            request=_pedido(),
            response=Response(),
            supabase=banco,
        )
    assert erro.value.status_code == 401
    assert "passkey_fail" in banco.eventos()


def test_lista_so_as_chaves_da_propria_conta():
    banco = _banco(
        pathr_passkey=[
            {"id": "a", "user_id": USUARIO["id"], "name": "Minha", "backed_up": True},
            {"id": "b", "user_id": "99999999-9999-9999-9999-999999999999", "name": "De outra pessoa"},
        ]
    )
    nomes = [c["name"] for c in router.listar(current_user=USUARIO, supabase=banco)]
    assert nomes == ["Minha"]


def test_nao_remove_chave_de_outra_conta():
    outra = "33333333-3333-3333-3333-333333333333"
    banco = _banco(
        pathr_passkey=[{"id": outra, "user_id": "99999999-9999-9999-9999-999999999999"}]
    )
    with pytest.raises(HTTPException) as erro:
        router.remover(passkey_id=outra, request=_pedido(), current_user=USUARIO, supabase=banco)
    assert erro.value.status_code == 404
    assert len(banco.linhas("pathr_passkey")) == 1
