"""Notícias: eventos de tecnologia perto da pessoa.

## De onde vêm os eventos

Igual à vaga (services/vagas.py): sem site próprio de eventos, então a busca
sai para várias fontes — Tavily e Brave, restritas aos catálogos de evento
mais usados no Brasil (Sympla, Eventbrite, Meetup, Even3) e, sem isso, uma
busca aberta por "eventos de tecnologia em <cidade>". Cada fonte que responde
é uma fonte a mais no resultado; nenhuma delas sozinha cobre a cidade inteira.

Do resultado da busca (título + trecho) a IA organiza os campos que a tela
precisa. Ela NUNCA inventa: quando o trecho não diz se é gratuito, ou quando
não diz o prazo de inscrição, o campo volta vazio — é a extração que decide
"não sei", não o texto do prompt que sugere um valor plausível.

## O prazo de inscrição, em duas tentativas

O texto da busca já traz o prazo, na maioria dos eventos grandes ("inscrições
de 3/3 a 28/3"). Quando NÃO traz, uma segunda pergunta à IA, focada só nisso,
tenta achar — e só ela, e não a extração geral, porque um evento sem prazo
óbvio no primeiro texto pode ainda ter um whitepaper ou uma segunda página que
a IA "lembra" com mais detalhe. Falhando as duas, os campos ficam `null` no
banco: é a tela (e não o servidor) que decide mostrar "Datas de inscrição
ainda não foram definidas" — o texto fixo, exatamente como pedido, nunca uma
frase gerada.

## Por que não WebSocket/scraping de página

Baixar a página de cada resultado (como o modo leitura faz, services/reader.py)
multiplicaria por 10-20 o tempo de uma busca só para ler um texto que a própria
busca já trouxe resumido. `vagas.py` já decidiu por título+trecho sem baixar a
página; aqui o motivo e o precedente são os mesmos.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.config import settings
from app.services import geo

logger = logging.getLogger("pathr.noticias")

_TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_UA = "PathR/1.0 (+https://pathr.notter.com.br)"

TAVILY = "https://api.tavily.com/search"
BRAVE = "https://api.search.brave.com/res/v1/web/search"

# Os catálogos de evento em que confiamos primeiro — antes de abrir a busca
# para qualquer site. Even3 é comum em congresso técnico/acadêmico brasileiro.
SITES_DE_EVENTO = ("sympla.com.br", "eventbrite.com.br", "eventbrite.com", "meetup.com", "even3.com.br")

# Evento não muda de hora em hora; uma busca por cidade a cada tantas horas
# evita bater na cota de Tavily/Brave a cada abertura da tela.
_VALIDADE_S = 12 * 3600

# Texto fixo, literal — nunca gerado pela IA. É o que a tela mostra quando as
# duas tentativas (o texto da busca, depois a pergunta focada) não acham o
# prazo de inscrição.
SEM_PRAZO_DE_INSCRICAO = "Datas de inscrição ainda não foram definidas"


@dataclass
class EventoBruto:
    url: str
    titulo: str
    trecho: str


# ---------------------------------------------------------------------------
# Busca em várias fontes
# ---------------------------------------------------------------------------


async def _tavily(cliente: httpx.AsyncClient, consulta: str) -> list[EventoBruto]:
    if not settings.tavily_api_key.strip():
        return []
    resposta = await cliente.post(
        TAVILY,
        json={
            "api_key": settings.tavily_api_key.strip(),
            "query": consulta,
            "max_results": 15,
            "search_depth": "basic",
            "include_domains": list(SITES_DE_EVENTO),
        },
    )
    resposta.raise_for_status()
    return [
        EventoBruto(str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("content") or ""))
        for item in resposta.json().get("results") or []
    ]


async def _brave(cliente: httpx.AsyncClient, consulta: str) -> list[EventoBruto]:
    if not settings.brave_api_key.strip():
        return []
    sites = " OR ".join(f"site:{s}" for s in SITES_DE_EVENTO)
    resposta = await cliente.get(
        BRAVE,
        params={"q": f"{consulta} ({sites})", "count": 20},
        headers={"X-Subscription-Token": settings.brave_api_key.strip(), "Accept": "application/json"},
    )
    resposta.raise_for_status()
    return [
        EventoBruto(str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("description") or ""))
        for item in ((resposta.json().get("web") or {}).get("results")) or []
    ]


async def buscar_bruto(cidade: str, uf: str) -> list[EventoBruto]:
    """Os eventos que as fontes configuradas encontraram, sem duplicar por URL.

    Sem nenhuma fonte configurada (sem chave de Tavily nem Brave), devolve
    vazio — a tela mostra "nenhum evento encontrado ainda", não erro: é a
    mesma decisão que `vagas.py` toma para a busca em sites.
    """
    consulta = f"eventos de tecnologia em {cidade} {uf}".strip()
    encontrados: list[EventoBruto] = []
    vistos: set[str] = set()
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        for buscar in (_tavily, _brave):
            try:
                resultado = await buscar(cliente, consulta)
            except httpx.HTTPError as exc:
                logger.warning("busca de eventos falhou (%s): %s", buscar.__name__, exc)
                continue
            for item in resultado:
                chave = item.url.strip().lower().rstrip("/")
                if not chave or chave in vistos:
                    continue
                vistos.add(chave)
                encontrados.append(item)
    return encontrados


# ---------------------------------------------------------------------------
# Organização dos campos pela IA — nunca inventa, só o que o texto diz
# ---------------------------------------------------------------------------

_AI_SYSTEM = """Você organiza dados de eventos de tecnologia a partir do título e do trecho
que uma busca na web trouxe sobre a página do evento.

Regras:
1. Preencha só o que está EXPLÍCITO no texto dado. Campo que o texto não diz
   volta `null` — nunca um valor plausível, nunca uma suposição.
2. `gratuito`: true se o texto diz claramente que é gratuito/sem custo; false
   se diz que tem ingresso pago; `null` se o texto não fala sobre preço.
3. Datas no formato AAAA-MM-DD. Sem ano explícito no texto, use o ano mais
   próximo no futuro a partir de hoje.
4. `inscricao_inicio`/`inscricao_fim`: só quando o texto falar de PRAZO ou
   ABERTURA de inscrição — não confundir com a data do evento em si.
"""

_AI_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "resumo": {"type": "STRING"},
        "cidade": {"type": "STRING"},
        "estado": {"type": "STRING"},
        "local": {"type": "STRING"},
        "data_inicio": {"type": "STRING"},
        "data_fim": {"type": "STRING"},
        "gratuito": {"type": "BOOLEAN"},
        "preco_info": {"type": "STRING"},
        "inscricao_inicio": {"type": "STRING"},
        "inscricao_fim": {"type": "STRING"},
    },
    "required": ["titulo", "resumo"],
}

_AI_SYSTEM_INSCRICAO = """Você tenta encontrar o prazo de inscrição de UM evento de tecnologia
específico, a partir do que você sabe sobre ele.

Regra única, mais importante que qualquer outra: só responda uma data se você
tem certeza real de que ela é o prazo de inscrição DESTE evento. Chutar uma
data "comum" para esse tipo de evento é pior do que admitir que não sabe —
retorne `null` nos dois campos sempre que não tiver certeza.
"""

_AI_SCHEMA_INSCRICAO: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "inscricao_inicio": {"type": "STRING"},
        "inscricao_fim": {"type": "STRING"},
    },
}

_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _data_valida(valor: Any) -> Optional[str]:
    texto = str(valor or "").strip()
    return texto if _DATA_ISO.match(texto) else None


def _texto_ou_none(valor: Any, limite: int) -> Optional[str]:
    texto = str(valor or "").strip()
    return texto[:limite] if texto else None


async def _completar_inscricao(titulo: str, cidade: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Segunda tentativa, só para o prazo de inscrição — ver o docstring do módulo."""
    onde = f" em {cidade}" if cidade else ""
    prompt = f'O evento é "{titulo}"{onde}. Você sabe o prazo (início e fim) das inscrições dele?'
    try:
        resultado = await generate_json(_AI_SYSTEM_INSCRICAO, prompt, _AI_SCHEMA_INSCRICAO)
    except AiProviderError:
        return None, None
    dados = resultado.content or {}
    return _data_valida(dados.get("inscricao_inicio")), _data_valida(dados.get("inscricao_fim"))


async def organizar(bruto: EventoBruto, cidade_buscada: str, uf_buscada: str) -> Optional[dict[str, Any]]:
    """Os campos do evento, extraídos do texto da busca — ou `None` se a IA
    não conseguiu nem separar um título e um resumo dali."""
    prompt = f"Título: {bruto.titulo}\nTrecho da busca: {bruto.trecho}\nEndereço: {bruto.url}"
    try:
        resultado = await generate_json(_AI_SYSTEM, prompt, _AI_SCHEMA)
    except AiProviderError as exc:
        logger.warning("organização por IA indisponível para %r: %s", bruto.url, exc)
        return None
    dados = resultado.content or {}
    titulo = str(dados.get("titulo") or bruto.titulo).strip()
    resumo = str(dados.get("resumo") or "").strip()
    if not titulo or not resumo:
        return None

    data_inicio = _data_valida(dados.get("data_inicio")) or date.today().isoformat()
    inscricao_inicio = _data_valida(dados.get("inscricao_inicio"))
    inscricao_fim = _data_valida(dados.get("inscricao_fim"))
    if inscricao_inicio is None and inscricao_fim is None:
        # Primeira tentativa (o texto da busca) não achou — a segunda,
        # focada só nisso, ainda pode. Falhando ela também, os campos ficam
        # `null` mesmo: a tela mostra o texto fixo, e não uma frase gerada.
        inscricao_inicio, inscricao_fim = await _completar_inscricao(
            titulo, dados.get("cidade") or cidade_buscada or None
        )

    return {
        "title": titulo[:300],
        "summary": resumo[:2000],
        "venue": _texto_ou_none(dados.get("local"), 200),
        "city": _texto_ou_none(dados.get("cidade") or cidade_buscada, 120),
        "state": _texto_ou_none(str(dados.get("estado") or uf_buscada or "").upper(), 2),
        "event_start": data_inicio,
        "event_end": _data_valida(dados.get("data_fim")),
        "is_free": dados.get("gratuito") if isinstance(dados.get("gratuito"), bool) else None,
        "price_info": _texto_ou_none(dados.get("preco_info"), 200),
        "registration_start": inscricao_inicio,
        "registration_end": inscricao_fim,
        "ticket_url": bruto.url,
        "source": "busca",
        "source_url": bruto.url,
    }


# ---------------------------------------------------------------------------
# Gravação e listagem
# ---------------------------------------------------------------------------


async def _reachable(client: httpx.AsyncClient, url: str) -> bool:
    """A mesma checagem de `resource_search._reachable`: HEAD primeiro, GET
    com `stream` se o servidor recusar HEAD — sem baixar a página inteira."""
    try:
        head = await client.head(url)
        if head.status_code < 400:
            return True
        if head.status_code not in (403, 405, 501):
            return False
    except httpx.HTTPError:
        pass
    try:
        async with client.stream("GET", url) as resposta:
            return resposta.status_code < 400
    except httpx.HTTPError:
        return False


def _precisa_buscar(supabase: Client, cidade: str, uf: str) -> bool:
    limite = (datetime.now(timezone.utc) - timedelta(seconds=_VALIDADE_S)).isoformat()
    recentes = (
        supabase.table("pathr_news_event").select("id")
        .eq("city", cidade).eq("state", uf).gte("updated_at", limite).limit(1).execute().data
        or []
    )
    return not recentes


async def atualizar_regiao(supabase: Client, cidade: str, uf: str) -> None:
    """Busca e grava, só se a região não foi buscada há pouco. Falha de uma
    fonte, ou da IA numa candidata, não derruba a busca inteira — cada evento
    é uma tentativa independente."""
    if not cidade or not uf or not _precisa_buscar(supabase, cidade, uf):
        return
    brutos = await buscar_bruto(cidade, uf)
    if not brutos:
        return

    organizados: list[dict[str, Any]] = []
    for item in brutos[:12]:
        campos = await organizar(item, cidade, uf)
        if campos:
            organizados.append(campos)

    if not organizados:
        return

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        vivos = [c for c in organizados if await _reachable(cliente, c["ticket_url"])]

    for campos in vivos:
        try:
            supabase.table("pathr_news_event").upsert(
                {**campos, "updated_at": datetime.now(timezone.utc).isoformat()},
                on_conflict="source_url",
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("gravação do evento %r falhou: %s", campos.get("source_url"), exc)


def _publica(evento: dict[str, Any], presencas: set[str]) -> dict[str, Any]:
    tem_prazo = evento.get("registration_start") or evento.get("registration_end")
    return {
        "id": str(evento["id"]),
        "titulo": evento.get("title"),
        "resumo": evento.get("summary"),
        "local": evento.get("venue"),
        "cidade": evento.get("city"),
        "estado": evento.get("state"),
        "data_inicio": evento.get("event_start"),
        "data_fim": evento.get("event_end"),
        "gratuito": evento.get("is_free"),
        "preco_info": evento.get("price_info"),
        "inscricao_inicio": evento.get("registration_start"),
        "inscricao_fim": evento.get("registration_end"),
        "inscricao_texto": None if tem_prazo else SEM_PRAZO_DE_INSCRICAO,
        "url_ingresso": evento.get("ticket_url"),
        "eu_vou": str(evento["id"]) in presencas,
    }


def listar_por_regiao(
    supabase: Client, user_id: str, cidade: Optional[str], uf: Optional[str], raio_km: float
) -> list[dict[str, Any]]:
    """Eventos futuros perto da cidade da pessoa. Sem cidade cadastrada,
    devolve os eventos futuros de qualquer lugar — melhor mostrar algo do que
    uma tela vazia por falta de endereço no perfil."""
    hoje = date.today().isoformat()
    linhas = (
        supabase.table("pathr_news_event").select("*")
        .gte("event_start", hoje).order("event_start").limit(200).execute().data
        or []
    )

    if cidade:
        centro = geo.achar(cidade, uf)
        if centro:
            proximas = {c.nome.lower() for c, _ in geo.no_raio(centro, raio_km)}
            linhas = [
                l for l in linhas
                if not l.get("city")
                or str(l["city"]).lower() in proximas
                or str(l.get("state") or "").upper() == (uf or "").upper()
            ]

    presencas = {
        str(p["event_id"])
        for p in (
            supabase.table("pathr_news_attendance").select("event_id")
            .eq("user_id", user_id).execute().data or []
        )
    }
    return [_publica(l, presencas) for l in linhas]


def confirmar_presenca(supabase: Client, user_id: str, event_id: str) -> None:
    try:
        supabase.table("pathr_news_attendance").insert(
            {"user_id": user_id, "event_id": event_id}
        ).execute()
    except Exception:  # noqa: BLE001
        pass  # já confirmado — o índice único recusou, e o resultado é o mesmo.


def cancelar_presenca(supabase: Client, user_id: str, event_id: str) -> None:
    supabase.table("pathr_news_attendance").delete().eq("user_id", user_id).eq("event_id", event_id).execute()


def eventos_que_vou(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    """Os próximos eventos que a pessoa confirmou — para o próprio perfil e,
    quando `show_attendance` está ligado, para o cartão que outras contas veem."""
    hoje = date.today().isoformat()
    presencas = (
        supabase.table("pathr_news_attendance").select("event_id").eq("user_id", user_id).execute().data or []
    )
    ids = [str(p["event_id"]) for p in presencas]
    if not ids:
        return []
    eventos = (
        supabase.table("pathr_news_event").select("*")
        .in_("id", ids).gte("event_start", hoje).order("event_start").limit(20).execute().data
        or []
    )
    return [
        {"id": str(e["id"]), "titulo": e.get("title"), "data_inicio": e.get("event_start"), "cidade": e.get("city")}
        for e in eventos
    ]


def gerar_ics(evento: dict[str, Any]) -> str:
    """Um `.ics` mínimo — sem biblioteca: o formato é texto simples e o app
    só precisa de um evento de dia inteiro, com título, local e descrição."""

    def _linha(campo: str, valor: str) -> str:
        # `\n`, vírgula e ponto-e-vírgula têm significado no formato iCalendar
        # e precisam ser escapados antes de entrar numa propriedade de texto.
        escapado = valor.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
        return f"{campo}:{escapado}"

    inicio = str(evento.get("data_inicio") or date.today().isoformat()).replace("-", "")
    fim = str(evento.get("data_fim") or evento.get("data_inicio") or date.today().isoformat()).replace("-", "")
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PathR//Noticias//PT",
        "BEGIN:VEVENT",
        f"UID:{evento['id']}@pathr.notter.com.br",
        f"DTSTAMP:{agora}",
        f"DTSTART;VALUE=DATE:{inicio}",
        f"DTEND;VALUE=DATE:{fim}",
        _linha("SUMMARY", str(evento.get("titulo") or "Evento")),
    ]
    if evento.get("local"):
        linhas.append(_linha("LOCATION", str(evento["local"])))
    if evento.get("resumo"):
        linhas.append(_linha("DESCRIPTION", str(evento["resumo"])))
    if evento.get("url_ingresso"):
        linhas.append(_linha("URL", str(evento["url_ingresso"])))
    linhas += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(linhas) + "\r\n"
