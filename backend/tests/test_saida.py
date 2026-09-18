"""A guarda das requisições que saem para endereços de terceiros.

O que se segura: endereço interno não recebe pedido nenhum (nem o primeiro
pacote); nome que resolve para IP interno é barrado mesmo "passando" numa
checagem por nome (DNS rebinding); redirecionamento para dentro é barrado no
salto; e link público continua funcionando, inclusive quando o servidor recusa
HEAD e só responde a GET.

Os testes olham QUEM foi contactado, e não só o `True`/`False` — num defeito de
SSRF o estrago acontece no pedido que sai, mesmo que a resposta seja descartada.
"""

import asyncio

import httpx
import pytest

from app.services import noticias, reader, resource_search, saida


def _cliente(transporte: httpx.MockTransport) -> httpx.AsyncClient:
    # `follow_redirects=True` de propósito: é como o resource_search monta o
    # cliente, e a guarda tem de mandar salto a salto mesmo assim.
    return httpx.AsyncClient(transport=transporte, follow_redirects=True)


def _rodar(corotina):
    return asyncio.run(corotina)


def test_endereco_interno_nao_recebe_pedido(monkeypatch):
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(str(pedido.url))
        return httpx.Response(200)

    # O host resolve para o metadata da nuvem — o alvo clássico de SSRF.
    monkeypatch.setattr(
        reader.socket, "getaddrinfo",
        lambda host, porta=None, **k: [(2, 1, 6, "", ("169.254.169.254", porta or 443))],
    )

    async def cenario():
        async with _cliente(httpx.MockTransport(responder)) as cliente:
            return await saida.alcancavel(cliente, "https://parece-normal.exemplo/x")

    assert _rodar(cenario()) is False
    assert pedidos == []  # nada saiu


@pytest.mark.parametrize(
    "interno",
    ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"],
)
def test_faixas_privadas_todas_recusadas(monkeypatch, interno):
    familia = 23 if ":" in interno else 2
    monkeypatch.setattr(
        reader.socket, "getaddrinfo",
        lambda host, porta=None, **k: [(familia, 1, 6, "", (interno, porta or 443))],
    )
    with pytest.raises(saida.EnderecoRecusado):
        saida.destino_pinado(f"https://qualquer.exemplo/x")


def test_conecta_no_ip_validado_mantendo_host_e_sni(monkeypatch):
    monkeypatch.setattr(
        reader.socket, "getaddrinfo",
        lambda host, porta=None, **k: [(2, 1, 6, "", ("93.184.216.34", porta or 443))],
    )

    alvo, cabecalhos, extensoes = saida.destino_pinado("https://exemplo.com/vaga")

    # O pedido vai ao IP já validado — não ao nome, que resolveria de novo.
    assert alvo == "https://93.184.216.34:443/vaga"
    # E o domínio segue no Host e no SNI: sem isso o servidor virtual erra a
    # resposta e o certificado TLS não confere.
    assert cabecalhos == {"Host": "exemplo.com"}
    assert extensoes == {"sni_hostname": "exemplo.com"}


def test_redirecionamento_para_dentro_e_barrado(monkeypatch):
    pedidos: list[str] = []

    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido.headers.get("Host", ""))
        if pedido.headers.get("Host") == "publico.exemplo":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200)

    def resolver(host, porta=None, **k):
        if host == "publico.exemplo":
            return [(2, 1, 6, "", ("93.184.216.34", porta or 443))]
        return [(2, 1, 6, "", ("169.254.169.254", porta or 80))]

    monkeypatch.setattr(reader.socket, "getaddrinfo", resolver)

    async def cenario():
        async with _cliente(httpx.MockTransport(responder)) as cliente:
            return await saida.alcancavel(cliente, "https://publico.exemplo/evento")

    assert _rodar(cenario()) is False
    # O primeiro salto saiu; o metadata NUNCA foi pedido.
    assert pedidos == ["publico.exemplo"]


def test_link_publico_continua_valendo(monkeypatch):
    monkeypatch.setattr(
        reader.socket, "getaddrinfo",
        lambda host, porta=None, **k: [(2, 1, 6, "", ("93.184.216.34", porta or 443))],
    )

    async def cenario(responder):
        async with _cliente(httpx.MockTransport(responder)) as cliente:
            return await saida.alcancavel(cliente, "https://sympla.com.br/evento")

    assert _rodar(cenario(lambda p: httpx.Response(200))) is True

    # Servidor que recusa HEAD e serve GET: continua valendo, senão o app
    # descartaria material bom como link quebrado.
    def so_get(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(405 if pedido.method == "HEAD" else 200)

    assert _rodar(cenario(so_get)) is True

    # 404 é link morto de verdade.
    assert _rodar(cenario(lambda p: httpx.Response(404))) is False


def test_os_dois_reachable_passam_pela_guarda(monkeypatch):
    """A correção vale para os DOIS lugares que checam link de terceiro — foi
    justamente um deles que ficou de fora quando o reader foi corrigido."""
    vistos: list[str] = []

    async def espia(_cliente, url, *args, **kwargs):
        vistos.append(url)
        return True

    monkeypatch.setattr(saida, "alcancavel", espia)

    async def cenario():
        async with httpx.AsyncClient() as cliente:
            await noticias._reachable(cliente, "https://a.exemplo/1")
            await resource_search._reachable(cliente, "https://b.exemplo/2")

    _rodar(cenario())
    assert vistos == ["https://a.exemplo/1", "https://b.exemplo/2"]
