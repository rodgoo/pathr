"""O escopo do cookie de sessão.

O PathR é um site independente: o usuário entra em pathr.notter.com.br, com
conta própria. O Notter só tem um link que abre isso numa aba nova — não há
sessão compartilhada entre os dois.

Este teste fixa a consequência disso no cookie: ele é host-only. Um
`Domain=.notter.com.br` faria o navegador anexar a sessão do PathR também em
requisições ao Notter e ao FinanceR, que são outras aplicações com outras
contas. É a regressão que este arquivo existe para impedir.
"""

import pytest
from fastapi import Response

from app.config import settings
from app.routers.auth import _clear_session_cookies, _set_session_cookies


def _cookie_headers(response: Response) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


@pytest.fixture(autouse=True)
def _restore_cookie_domain():
    original = settings.cookie_domain
    yield
    settings.cookie_domain = original


def test_cookie_e_host_only_por_padrao():
    settings.cookie_domain = ""
    response = Response()
    _set_session_cookies(response, "access-token", "refresh-token")

    headers = _cookie_headers(response)
    assert len(headers) == 2
    for header in headers:
        # Sem Domain: o navegador devolve o cookie só para o host que o emitiu.
        assert "domain=" not in header.lower()


def test_cookie_nunca_sai_sem_httponly_secure_e_samesite():
    """As três defesas juntas: HttpOnly tira o token do alcance do JavaScript,
    Secure exige HTTPS, SameSite barra o envio a partir de outro site."""
    settings.cookie_domain = ""
    response = Response()
    _set_session_cookies(response, "access-token", "refresh-token")

    for header in _cookie_headers(response):
        lowered = header.lower()
        assert "httponly" in lowered
        assert "secure" in lowered
        assert f"samesite={settings.cookie_samesite}" in lowered


def test_o_escopo_amplo_continua_possivel_mas_precisa_ser_pedido():
    """A porta existe para um ambiente em que a API responda num host
    diferente do que o navegador chama. O default é não usá-la."""
    settings.cookie_domain = ".exemplo.com"
    response = Response()
    _set_session_cookies(response, "access-token", "refresh-token")

    for header in _cookie_headers(response):
        assert "domain=.exemplo.com" in header.lower()


def test_logout_apaga_no_mesmo_escopo_em_que_criou():
    """Se o apagar usasse outro escopo, o cookie sobreviveria ao logout — o
    navegador casa Name+Domain+Path para saber o que remover."""
    settings.cookie_domain = ""
    response = Response()
    _clear_session_cookies(response)

    headers = _cookie_headers(response)
    assert len(headers) == 2
    for header in headers:
        assert "domain=" not in header.lower()
