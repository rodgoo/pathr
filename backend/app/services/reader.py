"""Modo leitura: o artigo aberto DENTRO do PathR.

## Por que existe

Metade dos sites de artigo recusa ser exibida num quadro. Medido nos materiais
reais da biblioteca: freecodecamp, docs.github.com e w3schools respondem
`x-frame-options` ou `frame-ancestors 'self'`. E o bloqueio NÃO é detectável
pelo JavaScript — o quadro fica em branco, sem erro, sem evento. Um "abre num
iframe e vê no que dá" entregaria metade dos artigos como uma área vazia.

Então quem busca é o servidor. Ele baixa a página, extrai o artigo do meio do
menu/banner/rodapé e devolve HTML limpo, que a tela mostra com a tipografia do
PathR — e, por ser conteúdo nosso, dá para medir a rolagem e contabilizar
progresso sozinho, que é o ponto do recurso.

## O que este módulo NÃO faz

Não substitui o original. Toda leitura carrega o link da fonte, e o texto é
buscado a cada expiração do cache, nunca copiado para dentro do nosso banco
como se fosse nosso.

## Segurança

Duas coisas que um "baixe esta URL no servidor" precisa ter:

1. **SSRF.** A URL vem da nossa tabela de recursos, mas os recursos nascem de
   uma busca na web — não são digitados por nós. Um resultado apontando para
   `http://169.254.169.254/` ou `http://10.0.0.5/` faria o backend buscar, com
   a credencial de rede dele, algo que o usuário jamais alcançaria. Por isso o
   host é resolvido e conferido contra as faixas privadas ANTES da requisição.

2. **XSS.** O HTML vem de terceiro e é renderizado na NOSSA origem. Sem
   sanitizar, quem controlasse a página de origem executaria script no PathR
   com a sessão da pessoa ao alcance. `nh3` limpa com lista de permissão —
   nada de `script`, `iframe`, `on*`, `style` ou `javascript:`.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
import nh3
import trafilatura

# Um agente identificado, com endereço de contato. Um raspador anônimo é o
# tipo de tráfego que sites bloqueiam primeiro, e com razão.
_AGENTE = "Mozilla/5.0 (compatible; PathR/1.0; +https://pathr.notter.com.br)"

_TIMEOUT = 25
# Teto do que se baixa. Um artigo grande fica em centenas de KB; o que passa
# muito disso é vídeo, instalador ou um erro de curadoria — e ler o corpo
# inteiro antes de descobrir isso é como se enche a memória do processo.
_MAX_BYTES = 5 * 1024 * 1024

# As marcações que um artigo realmente usa. Tudo fora daqui é removido.
_TAGS = {
    "p", "br", "hr", "blockquote", "pre", "code", "em", "strong", "b", "i", "u",
    "s", "sub", "sup", "mark", "small", "span", "div",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "a", "img", "figure", "figcaption",
}
_ATRIBUTOS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
}


# --------------------------------------------------------------------------
# O código no meio da frase
#
# trafilatura devolve TODO trecho de código como `<pre>`, sem distinguir o
# bloco da linha solta no meio de um parágrafo. Isso quebra o texto de um
# jeito que parece defeito nosso: `<pre>` é elemento de bloco, e o navegador
# FECHA o parágrafo ao encontrá-lo. Uma frase como
#
#     <p>The <pre>push</pre>, <pre>release</pre>, and <pre>pull_request</pre>
#     events are the most common.</p>
#
# chega à tela como cinco pedaços empilhados — "The", uma caixa larga, uma
# vírgula sozinha, outra caixa, ", and" — que foi exatamente o que se viu nos
# artigos do freeCodeCamp.
#
# O que separa um caso do outro está na própria saída: o bloco de código vem
# ANINHADO (`<pre><pre>…</pre></pre>`) e o código inline vem simples. Medido
# no artigo "Learn to Use GitHub Actions": 11 aninhados, todos blocos de
# verdade, e 58 simples, nenhum com quebra de linha e o maior com 37
# caracteres.
#
# A quebra de linha entra como segunda opinião: um `<pre>` simples com mais de
# uma linha é bloco de qualquer jeito, venha aninhado ou não. Errar para o
# lado do bloco preserva o alinhamento, que num trecho de YAML é o conteúdo.

_PRE_ANINHADO = re.compile(r"<pre>\s*<pre>(.*?)</pre>\s*</pre>", re.DOTALL)
_PRE_SIMPLES = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)

# Marca os blocos já resolvidos enquanto os inline são trocados. Sem isso, a
# segunda passada reabriria o que a primeira acabou de fechar. O texto é
# improvável o bastante em artigo de verdade para não colidir, e some antes
# de sair desta função.
_MARCA = "\ue000pathr-bloco\ue000"
_MARCADO = re.compile(re.escape(_MARCA) + r"(.*?)" + re.escape(_MARCA), re.DOTALL)


def _bloco(trecho: str) -> str:
    return f"<pre><code>{trecho}</code></pre>"


def _arruma_codigo(html: str) -> str:
    """Bloco vira `<pre><code>`; código de uma linha volta a ser inline."""

    def inline(achado: re.Match[str]) -> str:
        trecho = achado.group(1)
        return _bloco(trecho) if "\n" in trecho.strip() else f"<code>{trecho}</code>"

    marcado = _PRE_ANINHADO.sub(lambda achado: _MARCA + achado.group(1) + _MARCA, html)
    trocado = _PRE_SIMPLES.sub(inline, marcado)
    return _MARCADO.sub(lambda achado: _bloco(achado.group(1)), trocado)


class LeituraIndisponivel(Exception):
    """A página não pôde ser lida. `motivo` é escrito para a tela."""

    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


@dataclass(frozen=True)
class Leitura:
    html: str
    palavras: int


def _endereco_publico(host: str) -> bool:
    """O host resolve para um endereço da internet pública?

    Resolve de verdade em vez de olhar o texto: `localtest.me` e incontáveis
    domínios apontam para 127.0.0.1, e uma checagem por nome não veria isso.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _url_permitida(url: str) -> bool:
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return False
    return _endereco_publico(partes.hostname)


def _baixar(url: str) -> str:
    if not _url_permitida(url):
        raise LeituraIndisponivel("Endereço não permitido para leitura.")
    try:
        with httpx.Client(
            headers={"User-Agent": _AGENTE, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
            timeout=_TIMEOUT,
        ) as cliente:
            with cliente.stream("GET", url) as resposta:
                if resposta.status_code != 200:
                    raise LeituraIndisponivel(
                        f"O site respondeu {resposta.status_code} ao pedido de leitura."
                    )
                if "html" not in resposta.headers.get("content-type", ""):
                    raise LeituraIndisponivel("O endereço não aponta para uma página de texto.")
                # Um redirecionamento pode terminar num endereço interno mesmo
                # tendo começado público — a checagem vale para onde se CHEGOU.
                if not _url_permitida(str(resposta.url)):
                    raise LeituraIndisponivel("Endereço não permitido para leitura.")
                corpo = bytearray()
                for pedaco in resposta.iter_bytes():
                    corpo.extend(pedaco)
                    if len(corpo) > _MAX_BYTES:
                        raise LeituraIndisponivel("A página é grande demais para ler aqui.")
                return corpo.decode(resposta.encoding or "utf-8", errors="replace")
    except httpx.HTTPError as exc:
        raise LeituraIndisponivel("Não consegui alcançar o site do material.") from exc


def ler(url: str) -> Leitura:
    """Baixa, extrai o artigo e devolve HTML seguro para renderizar.

    Levanta `LeituraIndisponivel` com um motivo em português — a tela mostra
    esse texto e oferece o link original, em vez de um quadro vazio.
    """
    pagina = _baixar(url)

    bruto = trafilatura.extract(
        pagina,
        output_format="html",
        include_links=True,
        include_images=True,
        include_tables=True,
        # Com a URL, os links e imagens relativos do artigo viram absolutos —
        # sem isso, "/img/fluxo.png" apontaria para o PathR e não carregaria.
        url=url,
    )
    if not bruto or not bruto.strip():
        raise LeituraIndisponivel("Não consegui extrair o texto desta página.")

    texto = trafilatura.extract(pagina, url=url) or ""
    limpo = nh3.clean(_arruma_codigo(bruto), tags=_TAGS, attributes=_ATRIBUTOS)
    return Leitura(html=limpo, palavras=len(texto.split()))
