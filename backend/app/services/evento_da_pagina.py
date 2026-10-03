"""O que a PÁGINA do evento diz sobre ele — data, lugar e imagem.

## Por que ler a página, e não confiar na busca

O trecho que Tavily e Brave devolvem é um pedaço de propaganda: quase nunca traz
a data, e quando traz é "neste sábado" ou "dia 12". Pedir à IA que extraia data
dali produz o pior resultado possível — uma data plausível e errada,
indistinguível de uma certa para quem lê. Era o que acontecia: sem data no
texto, o evento era gravado com a data de HOJE, e a tela anunciava com
confiança um encontro que não é hoje.

Sympla, Eventbrite, Even3 e Meetup publicam `schema.org/Event` em JSON-LD na
própria página: `startDate`, `endDate`, `location` e `image`, ditos pelo site
que vende o ingresso. É a fonte certa, e não custa IA nenhuma.

## Quando não há JSON-LD

Cai-se no `og:` (Open Graph), que quase toda página tem: `og:image` resolve a
imagem, e `og:title`/`og:description` melhoram título e resumo. Data, não —
sem data explícita o evento NÃO entra, porque faltar um evento é melhor do que
mandar alguém para a data errada.

## A Sympla parou de publicar JSON-LD

Foi o que zerou a varredura inteira: nenhuma página de evento da Sympla (a
maior fonte de `SITES_DE_EVENTO`) tem mais `<script type="application/ld+json">`
— só Open Graph, sem data. A busca achava dezenas de candidatos reais
(confirmado em produção) e `_montar` descartava TODOS por falta de data.

A data continua lá, só que em `<script id="__NEXT_DATA__">` — o payload de
hidratação do Next.js, não um formato pensado para terceiros lerem, mas a
única fonte de data/local/preço que a página ainda expõe sem rodar
JavaScript. `_evento_da_sympla` lê dali como alternativa ao JSON-LD; se a
Sympla também tirar isto um dia, a varredura volta a zerar PARA ELA — não
para Eventbrite/Meetup/Even3, que continuam no caminho de JSON-LD.
"""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("pathr.noticias")

_JSON_LD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_META = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](og:[a-z:]+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
# Alguns sites escrevem `content` antes de `property`.
_META_INVERTIDA = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\'](og:[a-z:]+)["\']',
    re.IGNORECASE,
)
# O payload de hidratação do Next.js que a Sympla embute na página — ver o
# cabeçalho do arquivo. `id="__NEXT_DATA__"` é o nome fixo que o framework usa.
_NEXT_DATA = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class DadosDaPagina:
    """Só o que a página afirmou. Campo ausente é `None`, nunca um palpite."""

    titulo: Optional[str] = None
    resumo: Optional[str] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    local: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    imagem: Optional[str] = None
    gratuito: Optional[bool] = None
    preco_info: Optional[str] = None
    online: bool = False


def _blocos_json(html: str) -> Iterator[Any]:
    for bruto in _JSON_LD.findall(html):
        try:
            yield json.loads(bruto.strip())
        except (ValueError, TypeError):
            continue


def _achatar(no: Any) -> Iterator[dict[str, Any]]:
    """JSON-LD vem de três jeitos: objeto, lista, ou `@graph` com tudo dentro."""
    if isinstance(no, list):
        for item in no:
            yield from _achatar(item)
    elif isinstance(no, dict):
        yield no
        for chave in ("@graph", "subEvent", "event"):
            if chave in no:
                yield from _achatar(no[chave])


def _e_evento(no: dict[str, Any]) -> bool:
    tipo = no.get("@type")
    tipos = tipo if isinstance(tipo, list) else [tipo]
    return any(isinstance(t, str) and "event" in t.lower() for t in tipos)


def _data(valor: Any) -> Optional[str]:
    """`2026-10-15T09:00:00-03:00` e `2026-10-15` viram `2026-10-15`."""
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        quando = datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            quando = date.fromisoformat(texto[:10])
        except ValueError:
            return None
    return quando.isoformat()


def _texto(valor: Any, limite: int) -> Optional[str]:
    if isinstance(valor, dict):
        valor = valor.get("name") or valor.get("@value")
    # `html.unescape` porque tanto o `content` de uma meta tag quanto o JSON da
    # Sympla chegam com entidade crua ("&amp;", "&nbsp;") — sem isto a tela
    # mostrava "Data &amp; AI Meetup" em vez de "Data & AI Meetup".
    texto = re.sub(r"\s+", " ", html.unescape(str(valor or ""))).strip()
    return texto[:limite] if texto else None


def _imagem(valor: Any, base: str) -> Optional[str]:
    """A imagem pode vir como texto, lista ou objeto `ImageObject`."""
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    if isinstance(valor, dict):
        valor = valor.get("url") or valor.get("contentUrl")
    endereco = str(valor or "").strip()
    if not endereco:
        return None
    endereco = urljoin(base, endereco)
    return endereco[:1000] if endereco.startswith(("http://", "https://")) else None


def _sigla_do_estado(estado: Optional[str]) -> Optional[str]:
    """Nome por extenso ou sigla viram a UF certa; texto irreconhecível vira `None`."""
    from app.services.geo import uf_de

    return uf_de(estado)


def _lugar(no: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str], bool]:
    """Devolve `(local, cidade, estado, online)` do campo `location`."""
    lugar = no.get("location")
    if isinstance(lugar, list):
        lugar = lugar[0] if lugar else None
    if not isinstance(lugar, dict):
        return None, None, None, False

    tipo = str(lugar.get("@type") or "")
    if "virtual" in tipo.lower():
        return None, None, None, True

    endereco = lugar.get("address")
    if not isinstance(endereco, dict):
        # Endereço em texto corrido: dá para guardar o nome do lugar, e a
        # cidade fica por conta de quem chamou (que sabe a região buscada).
        return _texto(lugar.get("name"), 200), None, None, False

    estado = _texto(endereco.get("addressRegion"), 40)
    return (
        _texto(lugar.get("name"), 200),
        _texto(endereco.get("addressLocality"), 120),
        _sigla_do_estado(estado),
        False,
    )


def _preco(no: dict[str, Any]) -> tuple[Optional[bool], Optional[str]]:
    ofertas = no.get("offers")
    if isinstance(ofertas, list):
        ofertas = ofertas[0] if ofertas else None
    if not isinstance(ofertas, dict):
        return None, None
    bruto = ofertas.get("price", ofertas.get("lowPrice"))
    if bruto is None:
        return None, None
    try:
        valor = float(str(bruto).replace(",", "."))
    except ValueError:
        return None, _texto(bruto, 200)
    if valor == 0:
        return True, None
    moeda = _texto(ofertas.get("priceCurrency"), 8) or "BRL"
    return False, f"a partir de {moeda} {valor:.2f}".replace(".", ",")


def _open_graph(html: str) -> dict[str, str]:
    marcas = {chave.lower(): valor for chave, valor in _META.findall(html)}
    for valor, chave in _META_INVERTIDA.findall(html):
        marcas.setdefault(chave.lower(), valor)
    return marcas


def _evento_da_sympla(html: str) -> Optional[dict[str, Any]]:
    """O evento, lido do `__NEXT_DATA__` — ver "A Sympla parou de publicar
    JSON-LD" no cabeçalho do arquivo. `None` quando a página não é da Sympla
    ou o formato mudou de novo: cada passo aqui pode falhar sozinho, e uma
    estrutura inesperada não pode virar exceção no meio da varredura."""
    bloco = _NEXT_DATA.search(html)
    if not bloco:
        return None
    try:
        dados = json.loads(bloco.group(1))
        evento = dados["props"]["pageProps"]["hydrationData"]["eventHydration"]["event"]
    except (ValueError, TypeError, KeyError):
        return None
    return evento if isinstance(evento, dict) else None


def extrair(html_: str, url: str) -> DadosDaPagina:
    """Lê a página uma vez e devolve o que ela afirma sobre o evento."""
    dados = DadosDaPagina()

    for bloco in _blocos_json(html_ or ""):
        for no in _achatar(bloco):
            if not _e_evento(no):
                continue
            dados.titulo = dados.titulo or _texto(no.get("name"), 300)
            dados.resumo = dados.resumo or _texto(no.get("description"), 2000)
            dados.data_inicio = dados.data_inicio or _data(no.get("startDate"))
            dados.data_fim = dados.data_fim or _data(no.get("endDate"))
            dados.imagem = dados.imagem or _imagem(no.get("image"), url)
            local, cidade, estado, online = _lugar(no)
            dados.local = dados.local or local
            dados.cidade = dados.cidade or cidade
            dados.estado = dados.estado or estado
            dados.online = dados.online or online
            gratuito, preco = _preco(no)
            if dados.gratuito is None:
                dados.gratuito = gratuito
            dados.preco_info = dados.preco_info or preco

    # Só tenta a Sympla se o JSON-LD não deu data: ele continua sendo a fonte
    # certa quando existe (Eventbrite, Meetup, Even3), e o `__NEXT_DATA__` é
    # dado de hidratação, não um formato pensado para ser lido por fora.
    if not dados.data_inicio:
        sympla = _evento_da_sympla(html_ or "")
        if sympla:
            dados.titulo = dados.titulo or _texto(sympla.get("name"), 300)
            dados.resumo = dados.resumo or _texto(sympla.get("strippedDetail") or sympla.get("detail"), 2000)
            dados.data_inicio = dados.data_inicio or _data(sympla.get("startDate"))
            dados.data_fim = dados.data_fim or _data(sympla.get("endDate"))
            endereco = sympla.get("eventsAddress")
            if isinstance(endereco, dict):
                dados.local = dados.local or _texto(endereco.get("name"), 200)
                dados.cidade = dados.cidade or _texto(endereco.get("city"), 120)
                dados.estado = dados.estado or _sigla_do_estado(_texto(endereco.get("state"), 40))
            # Presença da chave, e não um booleano: é assim que a Sympla marca
            # evento online na página mesma sem publicar nada em JSON-LD.
            if sympla.get("onlineInfo"):
                dados.online = True
            imagens = sympla.get("images")
            if isinstance(imagens, dict):
                dados.imagem = dados.imagem or _imagem(
                    imagens.get("logoCover") or imagens.get("logoLarge") or imagens.get("logoUrl"), url
                )

    marcas = _open_graph(html_ or "")
    dados.imagem = dados.imagem or _imagem(marcas.get("og:image"), url)
    dados.titulo = dados.titulo or _texto(marcas.get("og:title"), 300)
    dados.resumo = dados.resumo or _texto(marcas.get("og:description"), 2000)
    return dados


def icone_do_site(url: str) -> Optional[str]:
    """O ícone do site, para o card não ficar sem imagem nenhuma.

    Vem do serviço de favicon do Google a partir do domínio: existe para
    qualquer site, inclusive os que não publicam `og:image`.
    """
    dominio = urlparse(url).hostname
    if not dominio:
        return None
    return f"https://www.google.com/s2/favicons?domain={dominio}&sz=128"
