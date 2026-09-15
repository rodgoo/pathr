"""O cadastro contra contas falsas.

O que se segura: domínio que não existe, que não recebe e-mail ou de caixa
temporária é recusado; o DNS fora do ar não recusa ninguém; os limites por
faixa de IP funcionam; o Turnstile, quando ligado, exige token válido; e a
conta não confirmada em 3 dias é apagada.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import dns.exception
import dns.resolver
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services import antirrobo, email_dominio, faxina, limites
from tests.fake_supabase import FakeSupabase


@pytest.fixture
def dns_falso(monkeypatch):
    """Um DNS de mentira: cada domínio responde o que o teste mandar."""
    tabela: dict[tuple[str, str], object] = {}

    def resolver(dominio, tipo):
        resposta = tabela.get((dominio, tipo), dns.resolver.NoAnswer())
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr(email_dominio, "_resolver", resolver)
    email_dominio._cache.clear()
    return tabela


@pytest.mark.dns_real
def test_dominio_que_recebe_email_passa(dns_falso):
    dns_falso[("empresa.com.br", "MX")] = ["10 mx.empresa.com.br."]
    assert email_dominio.problema_do_email("ana@empresa.com.br") is None


@pytest.mark.dns_real
def test_sem_mx_mas_com_endereco_passa_pelo_padrao(dns_falso):
    dns_falso[("antigo.org", "A")] = ["203.0.113.10"]
    assert email_dominio.problema_do_email("ana@antigo.org") is None


@pytest.mark.dns_real
def test_dominio_inexistente_e_mx_nulo_sao_recusados(dns_falso):
    dns_falso[("naoexiste-xyz.com", "MX")] = dns.resolver.NXDOMAIN()
    assert email_dominio.problema_do_email("ana@naoexiste-xyz.com") == email_dominio.NAO_EXISTE
    dns_falso[("example.com", "MX")] = ["0 ."]
    assert email_dominio.problema_do_email("ana@example.com") == email_dominio.NAO_RECEBE
    assert email_dominio.problema_do_email("ana@semnada.net") == email_dominio.NAO_RECEBE


@pytest.mark.dns_real
def test_caixa_temporaria_e_recusada_sem_consultar(dns_falso):
    assert email_dominio.problema_do_email("bot@mailinator.com") == email_dominio.DESCARTAVEL
    assert email_dominio.problema_do_email("bot@qualquer.yopmail.com") == email_dominio.DESCARTAVEL


@pytest.mark.dns_real
def test_dns_fora_do_ar_nao_recusa_ninguem(dns_falso):
    dns_falso[("lento.com", "MX")] = dns.exception.Timeout()
    assert email_dominio.problema_do_email("ana@lento.com") is None


def test_faixa_do_ip():
    assert limites.rede_do_ip("203.0.113.77") == "203.0.113.0/24"
    assert limites.rede_do_ip("2001:db8:abcd:12::1") == "2001:db8:abcd::/48"
    assert limites.rede_do_ip(None) is None


def test_turnstile_desligado_nao_atrapalha(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    antirrobo.conferir_turnstile("", "1.2.3.4")


def test_turnstile_ligado_exige_token_valido(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_secret_key", "segredo-de-teste")
    with pytest.raises(HTTPException):
        antirrobo.conferir_turnstile("", "1.2.3.4")

    respostas = {"bom": {"success": True}, "ruim": {"success": False}}
    monkeypatch.setattr(
        antirrobo.httpx, "post",
        lambda _url, data, timeout: SimpleNamespace(status_code=200, json=lambda: respostas[data["response"]]),
    )
    antirrobo.conferir_turnstile("bom", "1.2.3.4")
    with pytest.raises(HTTPException):
        antirrobo.conferir_turnstile("ruim", "1.2.3.4")


def test_conta_nao_confirmada_em_3_dias_e_apagada():
    agora = datetime(2026, 9, 14, tzinfo=timezone.utc)
    banco = FakeSupabase(pathr_user=[
        {"id": "velha", "email_verified_at": None, "created_at": (agora - timedelta(days=4)).isoformat()},
        {"id": "nova", "email_verified_at": None, "created_at": (agora - timedelta(days=1)).isoformat()},
        {"id": "confirmada", "email_verified_at": "2026-09-01T00:00:00+00:00", "created_at": (agora - timedelta(days=30)).isoformat()},
    ])
    # O duplo não devolve as linhas apagadas (o PostgREST devolve): vale o que sobrou.
    assert faxina.apagar_contas_nao_confirmadas(banco, agora) is not None
    assert sorted(u["id"] for u in banco.linhas("pathr_user")) == ["confirmada", "nova"]
