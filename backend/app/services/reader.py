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
from html import escape
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import nh3
import trafilatura
from lxml import etree
from lxml import html as lxml_html

# Um agente identificado, com endereço de contato. Um raspador anônimo é o
# tipo de tráfego que sites bloqueiam primeiro, e com razão.
_AGENTE = "Mozilla/5.0 (compatible; PathR/1.0; +https://pathr.notter.com.br)"

_TIMEOUT = 25
_MAX_REDIRECIONAMENTOS = 5
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
        if _ip_interno(ip):
            return False
    return True


def _ip_interno(ip: "ipaddress._BaseAddress") -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _url_permitida(url: str) -> bool:
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return False
    return _endereco_publico(partes.hostname)


def _resolver_e_validar(host: str, porta: int) -> str:
    """Resolve o host UMA vez, exige que TODA resposta seja pública, e devolve
    o IP que a conexão vai usar.

    É isto que fecha o DNS rebinding: antes, `_url_permitida` resolvia para
    checar e o httpx resolvia DE NOVO para conectar — o domínio do atacante
    podia dar um IP público na checagem e um interno (127.0.0.1, o metadata da
    nuvem) na conexão. Aqui a checagem e a conexão usam a MESMA resolução: o
    pedido vai ao IP validado, com Host e SNI mantendo o domínio.
    """
    try:
        infos = socket.getaddrinfo(host, porta, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise LeituraIndisponivel("Endereço não permitido para leitura.") from exc
    escolhido: Optional[str] = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as exc:
            raise LeituraIndisponivel("Endereço não permitido para leitura.") from exc
        if _ip_interno(ip):
            raise LeituraIndisponivel("Endereço não permitido para leitura.")
        if escolhido is None:
            escolhido = str(ip)
    if escolhido is None:
        raise LeituraIndisponivel("Endereço não permitido para leitura.")
    return escolhido


def _baixar(url: str) -> tuple[str, str]:
    """Devolve (html, endereço lógico onde se chegou).

    Conecta sempre no IP validado (ver `_resolver_e_validar`), nunca deixando o
    httpx resolver o nome por conta própria — é o que impede o DNS rebinding.
    Os redirecionamentos são seguidos à mão para revalidar e re-fixar o IP a
    cada salto; um link público que redireciona para um endereço interno é
    barrado antes de a conexão sair.
    """
    if not _url_permitida(url):
        raise LeituraIndisponivel("Endereço não permitido para leitura.")

    atual = url
    with httpx.Client(
        headers={"User-Agent": _AGENTE, "Accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
        timeout=_TIMEOUT,
    ) as cliente:
        for _ in range(_MAX_REDIRECIONAMENTOS + 1):
            partes = urlparse(atual)
            if partes.scheme not in ("http", "https") or not partes.hostname:
                raise LeituraIndisponivel("Endereço não permitido para leitura.")
            porta = partes.port or (443 if partes.scheme == "https" else 80)
            ip = _resolver_e_validar(partes.hostname, porta)

            # A URL aponta para o IP validado; Host e SNI mantêm o domínio, para
            # o servidor virtual certo responder e o certificado TLS conferir.
            hospedeiro = f"[{ip}]" if ":" in ip else ip
            alvo = partes._replace(netloc=f"{hospedeiro}:{porta}").geturl()
            cabecalho_host = partes.hostname if porta in (80, 443) else f"{partes.hostname}:{porta}"

            try:
                with cliente.stream(
                    "GET",
                    alvo,
                    headers={"Host": cabecalho_host},
                    extensions={"sni_hostname": partes.hostname},
                ) as resposta:
                    if resposta.status_code in (301, 302, 303, 307, 308):
                        destino = resposta.headers.get("location")
                        if not destino:
                            raise LeituraIndisponivel("O site respondeu com um redirecionamento sem destino.")
                        atual = urljoin(atual, destino)
                        continue
                    if resposta.status_code != 200:
                        raise LeituraIndisponivel(
                            f"O site respondeu {resposta.status_code} ao pedido de leitura."
                        )
                    if "html" not in resposta.headers.get("content-type", ""):
                        raise LeituraIndisponivel("O endereço não aponta para uma página de texto.")
                    corpo = bytearray()
                    for pedaco in resposta.iter_bytes():
                        corpo.extend(pedaco)
                        if len(corpo) > _MAX_BYTES:
                            raise LeituraIndisponivel("A página é grande demais para ler aqui.")
                    return (
                        corpo.decode(resposta.encoding or "utf-8", errors="replace"),
                        atual,
                    )
            except httpx.HTTPError as exc:
                raise LeituraIndisponivel("Não consegui alcançar o site do material.") from exc

    raise LeituraIndisponivel("O site redirecionou vezes demais.")


# --------------------------------------------------------------------------
# A moldura do site, antes de extrair
#
# O trafilatura decide o que é artigo por densidade de texto, e numa página de
# documentação a navegação É densa. No git-scm.com, o menu de idiomas, o menu
# "Topics" com treze categorias e o histórico de 60 versões — cada uma com dez
# bolinhas coloridas — ficam DENTRO do mesmo `#main` que o manual, e saíam na
# tela antes da primeira linha do texto: 688 imagens quebradas e 65% das
# palavras dentro de links.
#
# Então a moldura sai antes da extração, por três sinais que não dependem do
# site: a tag (`nav`), o papel declarado (`role="navigation"`) e o nome da
# classe (`dropdown-panel`, `sidebar`). Nome de classe é o sinal mais fraco dos
# três — por isso a proteção abaixo.

_TAGS_SEMPRE_FORA = frozenset(
    {"script", "style", "noscript", "template", "nav", "form", "button", "select",
     "textarea", "iframe", "svg", "canvas", "dialog", "object", "embed"}
)
# Só FORA do artigo: `<header>` dentro de `<article>` é título e autoria, e
# `<aside>` dentro dele costuma ser a nota que o próprio texto cita.
_TAGS_FORA_SE_SOLTAS = frozenset({"header", "footer", "aside"})
_PAPEIS_DE_MOLDURA = frozenset(
    {"navigation", "banner", "contentinfo", "search", "menu", "menubar", "toolbar",
     "dialog", "complementary"}
)
# Comparadas por PALAVRA inteira do nome da classe, nunca por pedaço:
# "dropdown-panel" tem "dropdown", mas "shared-notes" não tem "share".
_PALAVRAS_DE_MOLDURA = frozenset(
    {"nav", "navbar", "navigation", "menu", "dropdown", "sidebar", "breadcrumb",
     "breadcrumbs", "toc", "cookie", "cookies", "banner", "share", "sharing", "social",
     "newsletter", "subscribe", "advert", "advertisement", "ads", "popup", "modal", "skip"}
)

# Nenhum trecho que concentre esta fração das palavras da página é removido
# como moldura, por mais que o nome da classe sugira. Um site que embrulha o
# artigo inteiro em `<div class="content-with-sidebar">` perderia TUDO por
# causa de uma palavra; errar para o lado de sobrar menu é recuperável, errar
# para o lado de sumir o texto não é.
_PROTECAO_DO_CONTEUDO = 0.4

# Imagem com lado declarado até aqui é ícone, marcador ou pixel de rastreio —
# nunca a figura que o texto explica.
_LADO_DE_ICONE = 32

# Mais que isto das palavras dentro de links, e a página é um índice, não um
# texto. Medido nos 19 materiais da biblioteca, já com a moldura removida: o
# mais alto fica em 15% (docs.github.com/actions, uma página de entrada cheia
# de atalhos). Antes da remoção, o git-scm chegava a 65% e 69% — é esse o
# formato que o teto existe para barrar, se um site novo escapar da limpeza.
_TETO_DE_LINKS = 0.6

_BLOCOS = frozenset(
    {"p", "div", "pre", "ul", "ol", "li", "table", "blockquote", "h1", "h2", "h3", "h4",
     "h5", "h6", "dl", "figure", "section", "article", "hr"}
)

_DECLARACAO_XML = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
_ESCONDIDO = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)

# Muda quando a extração muda de um jeito que torna o que está gravado errado.
# library.py compara com a marca no começo do HTML guardado e busca de novo o
# que for de versão anterior — sem isso, corrigir o extrator não conserta nada
# do que já foi lido, e um artigo aberto uma vez por semana fica quebrado para
# sempre.
VERSAO = 3
MARCA_DA_VERSAO = f"<!--pathr-leitor:{VERSAO}-->"


def _palavras(elemento: lxml_html.HtmlElement) -> int:
    return len(" ".join(elemento.itertext()).split())


def _e_moldura(elemento: lxml_html.HtmlElement, dentro_do_artigo: bool) -> bool:
    tag = elemento.tag
    if tag in _TAGS_SEMPRE_FORA:
        return True
    if tag in _TAGS_FORA_SE_SOLTAS and not dentro_do_artigo:
        return True
    if (elemento.get("role") or "").strip().lower() in _PAPEIS_DE_MOLDURA:
        return True
    if elemento.get("hidden") is not None or (elemento.get("aria-hidden") or "").lower() == "true":
        return True
    if _ESCONDIDO.search(elemento.get("style") or ""):
        return True
    nomes = f"{elemento.get('class') or ''} {elemento.get('id') or ''}".lower()
    return any(palavra in _PALAVRAS_DE_MOLDURA for palavra in re.split(r"[\s_\-]+", nomes))


def _abre_artigo(elemento: lxml_html.HtmlElement) -> bool:
    return elemento.tag in ("article", "main") or (elemento.get("role") or "").lower() == "main"


def _tira_moldura(raiz: lxml_html.HtmlElement) -> None:
    # Script e estilo saem primeiro e sem proteção: não são conteúdo nunca, e o
    # texto deles inflaria a contagem que protege o conteúdo de verdade.
    for elemento in list(raiz.iter("script", "style", "noscript", "template")):
        elemento.drop_tree()
    for comentario in list(raiz.iter(etree.Comment)):
        comentario.drop_tree()

    total = max(_palavras(raiz), 1)
    # Em pilha, e não recursivo: página com aninhamento fundo estouraria o
    # limite de recursão do Python, e o erro viraria "não consegui ler".
    pilha: list[tuple[lxml_html.HtmlElement, bool]] = [(raiz, _abre_artigo(raiz))]
    while pilha:
        pai, dentro = pilha.pop()
        for filho in list(pai):
            if not isinstance(filho.tag, str):
                continue
            if _e_moldura(filho, dentro) and _palavras(filho) < total * _PROTECAO_DO_CONTEUDO:
                filho.drop_tree()  # drop_tree preserva o texto que vem DEPOIS
            else:
                pilha.append((filho, dentro or _abre_artigo(filho)))


def _prepara_pagina(pagina: str, url: str) -> str:
    """A página sem moldura, com endereços absolutos e definições legíveis."""
    try:
        raiz = lxml_html.document_fromstring(_DECLARACAO_XML.sub("", pagina))
    except (etree.ParserError, ValueError):
        return pagina

    _tira_moldura(raiz)

    # Âncora de seção (`<a class="anchor" href="#_resumo">`) e gatilho de menu
    # (`href="#"`, `javascript:`). No leitor elas não levam a lugar nenhum — o
    # trafilatura resolve "#_resumo" contra a RAIZ do site, e o clique sairia
    # para a página inicial. E pior: ele aninha errado, e a âncora vazia de um
    # título acabava EMBRULHANDO o parágrafo seguinte inteiro. Era isso que
    # deixava a documentação do git sublinhada de ponta a ponta.
    for link in list(raiz.iter("a")):
        destino = (link.get("href") or "").strip()
        if not destino or destino.startswith("#") or destino.lower().startswith("javascript:"):
            link.drop_tag()

    # Imagem preguiçosa: o endereço de verdade mora em data-src até o
    # JavaScript do site trocar, e aqui não roda JavaScript.
    for imagem in raiz.iter("img"):
        atual = (imagem.get("src") or "").strip()
        guardado = imagem.get("data-src") or imagem.get("data-original") or imagem.get("data-lazy-src")
        if guardado and (not atual or atual.startswith("data:")):
            imagem.set("src", guardado)

    # Relativo vira absoluto AQUI, contra o endereço final. O `url=` do
    # trafilatura só resolve links, não imagens: medido, todas as 688 imagens
    # do git-scm e as 6 do docs.github.com saíam com "/images/..." e apontavam
    # para o PathR.
    raiz.make_links_absolute(url, resolve_base_href=True, handle_failures="discard")

    # Lista de definição (`<dl>`), que é como toda documentação lista opções.
    # O trafilatura a achata em marcadores alternados — o nome da opção num
    # item, a explicação no seguinte — e a relação entre os dois some. O termo
    # vira subtítulo e a explicação vem logo abaixo, como numa página de manual.
    #
    # Termos seguidos sem explicação no meio são sinônimos da mesma opção
    # (`-v` e `--version`) e viram UM subtítulo, "-v, --version". Separados,
    # o primeiro aparecia como título sem nada embaixo.
    for lista in list(raiz.iter("dl")):
        anterior: Optional[lxml_html.HtmlElement] = None
        for item in list(lista):
            if not isinstance(item.tag, str):
                continue
            if item.tag == "dt":
                if anterior is not None:
                    # O espaço que sobra no fim do primeiro termo apareceria
                    # antes da vírgula: "-v , --version".
                    if len(anterior):
                        anterior[-1].tail = (anterior[-1].tail or "").rstrip()
                    else:
                        anterior.text = (anterior.text or "").rstrip()
                    separador = lxml_html.Element("span")
                    separador.text = ", "
                    anterior.append(separador)
                    if item.text and item.text.strip():
                        separador.tail = item.text.lstrip()
                    for pedaco in list(item):
                        anterior.append(pedaco)
                    item.drop_tree()
                    continue
                item.tag = "h4"
                anterior = item
            else:
                if item.tag == "dd":
                    item.tag = "div"
                anterior = None
        lista.tag = "div"

    return lxml_html.tostring(raiz, encoding="unicode")


def _minuscula(imagem: lxml_html.HtmlElement) -> bool:
    for lado in ("width", "height"):
        valor = (imagem.get(lado) or "").strip().removesuffix("px")
        if valor.isdigit() and int(valor) <= _LADO_DE_ICONE:
            return True
    return False


def _serializa(raiz: lxml_html.HtmlElement) -> str:
    inicio = escape(raiz.text) if raiz.text else ""
    return inicio + "".join(lxml_html.tostring(filho, encoding="unicode") for filho in raiz)


def _limpa_extraido(bruto: str, url: str) -> tuple[str, float]:
    """A segunda passada, sobre o que o extrator devolveu.

    Devolve o HTML e a fração das palavras que ficou dentro de links. É uma
    rede de segurança para o que a primeira passada não pegar num site que
    ainda não vimos — nenhuma das regras aqui depende de conhecer o site.
    """
    try:
        raiz = lxml_html.fragment_fromstring(bruto, create_parent="div")
    except (etree.ParserError, ValueError):
        return bruto, 0.0

    # Imagens primeiro: um link cujo único conteúdo era uma imagem inválida
    # fica vazio, e a limpeza de links logo abaixo o recolhe.
    for imagem in list(raiz.iter("img")):
        origem = (imagem.get("src") or "").strip().lower()
        if not origem.startswith(("http://", "https://")) or _minuscula(imagem):
            imagem.drop_tree()

    for link in list(raiz.iter("a")):
        destino = (link.get("href") or "").strip()
        partes = urlparse(destino)
        vazio = not "".join(link.itertext()).strip() and link.find(".//img") is None
        # "https://git-scm.com#_resumo": âncora da página resolvida contra a
        # raiz do site. Link escrito por gente para uma seção da página
        # inicial vem com a barra ("…com/#secao"); sem ela é defeito de
        # extração, e o clique levaria para fora do artigo.
        ancora_na_raiz = bool(partes.fragment) and partes.path == ""
        engole_bloco = any(
            isinstance(interno.tag, str) and interno.tag in _BLOCOS
            for interno in link.iterdescendants()
        )
        if vazio:
            link.drop_tree()
        elif ancora_na_raiz or engole_bloco or destino.startswith("#"):
            # Link que embrulha parágrafo, bloco de código ou lista nunca é
            # intencional num artigo: é aninhamento quebrado, e sublinha tudo.
            link.drop_tag()
        elif destino and not partes.scheme:
            link.set("href", urljoin(url, destino))

    # Contêineres que ficaram vazios depois das remoções. Em ordem reversa para
    # que o filho esvazie antes de o pai ser avaliado.
    for elemento in reversed(list(raiz.iter("li", "p", "ul", "ol", "h4", "figure"))):
        if elemento is raiz or elemento.getparent() is None:
            continue
        if not "".join(elemento.itertext()).strip() and elemento.find(".//img") is None:
            elemento.drop_tree()

    total = _palavras(raiz)
    em_links = sum(_palavras(link) for link in raiz.iter("a"))
    return _serializa(raiz), (em_links / total if total else 0.0)


def ler(url: str) -> Leitura:
    """Baixa, extrai o artigo e devolve HTML seguro para renderizar.

    Levanta `LeituraIndisponivel` com um motivo em português — a tela mostra
    esse texto e oferece o link original, em vez de um quadro vazio.
    """
    pagina, final = _baixar(url)
    preparada = _prepara_pagina(pagina, final)

    bruto = trafilatura.extract(
        preparada,
        output_format="html",
        include_links=True,
        include_images=True,
        include_tables=True,
        # `include_formatting` fica DESLIGADO de propósito, mesmo custando o
        # itálico e o negrito do texto. Ligado, o trafilatura transforma em
        # citação o bloco de código que tem ênfase dentro — medido: a sinopse
        # do git (`<pre><em>git</em> [-v | --version]…`) e um bloco em cada
        # quickstart do docs.github.com viravam `<blockquote>` em itálico,
        # sem alinhamento e sem fonte de código. Bloco de código é a parte que
        # a pessoa foi ler; a ênfase, não.
        url=final,
    )
    if not bruto or not bruto.strip():
        raise LeituraIndisponivel("Não consegui extrair o texto desta página.")

    html, fracao_em_links = _limpa_extraido(_arruma_codigo(bruto), final)
    if not "".join(lxml_html.fragment_fromstring(html or "<p></p>", create_parent="div").itertext()).strip():
        raise LeituraIndisponivel("Não consegui extrair o texto desta página.")
    if fracao_em_links > _TETO_DE_LINKS:
        # Melhor dizer isso e oferecer o original do que mostrar um índice de
        # links como se fosse um artigo — que é o defeito que motivou tudo acima.
        raise LeituraIndisponivel(
            "Esta página é mais um índice de links do que um texto. Abra no site original."
        )

    # A contagem sai da página já SEM a moldura: com o menu dentro, o git-scm
    # anunciava "54 min de leitura" para um texto bem mais curto.
    texto = trafilatura.extract(preparada, url=final) or ""
    limpo = nh3.clean(html, tags=_TAGS, attributes=_ATRIBUTOS)
    return Leitura(html=MARCA_DA_VERSAO + limpo, palavras=len(texto.split()))
