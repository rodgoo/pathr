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
"""

from __future__ import annotations

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
    texto = re.sub(r"\s+", " ", str(valor or "")).strip()
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
        (estado[:2].upper() if estado else None),
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


def extrair(html: str, url: str) -> DadosDaPagina:
    """Lê a página uma vez e devolve o que ela afirma sobre o evento."""
    dados = DadosDaPagina()

    for bloco in _blocos_json(html or ""):
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

    marcas = _open_graph(html or "")
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
