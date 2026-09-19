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

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.config import settings
from app.services import evento_da_pagina, geo, saida

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

# Quantos candidatos a busca entrega por varredura, e quantas páginas se lê
# ao mesmo tempo. O teto antigo era 12 — pouco para uma capital, e a causa
# de 'faltam eventos que existem'. Seis páginas de uma vez é rápido sem
# parecer ataque para o site do catálogo.
_MAXIMO_POR_VARREDURA = 40
_CONCORRENCIA = 6
# O raio que define 'perto': o mesmo padrão da tela de Vagas.
_RAIO_DA_BUSCA_KM = 80.0

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
    onde = f"{cidade} {uf}".strip()
    # Várias consultas, e não uma: "eventos de tecnologia em X" traz o que a
    # busca considerar próximo desse texto, e some com o meetup de Python e o
    # workshop de dados que não usam a palavra "tecnologia". Cada consulta
    # pesca de um jeito; a união é o que faz a lista deixar de parecer curta.
    consultas = [
        f"eventos de tecnologia em {onde}",
        f"meetup programação desenvolvedores {onde}",
        f"workshop dados inteligência artificial {onde}",
        f"congresso TI startups {onde}",
    ]
    encontrados: list[EventoBruto] = []
    vistos: set[str] = set()
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        for consulta in consultas:
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


async def _montar(
    cliente: httpx.AsyncClient,
    bruto: EventoBruto,
    cidade_buscada: str,
    uf_buscada: str,
    perto: set[str],
) -> Optional[dict[str, Any]]:
    """Os campos do evento, lidos da PÁGINA dele — ou `None` se ela não serve.

    Descarta, nesta ordem: página que não abre, página sem data explícita,
    evento que já passou, e evento de outra região. Cada descarte é melhor do
    que a alternativa que existia antes — gravar um palpite.
    """
    html = await saida.baixar(cliente, bruto.url)
    if not html:
        return None

    pagina = evento_da_pagina.extrair(html, bruto.url)

    # Sem data dita pela página, o evento não entra. Era exatamente aqui que
    # nascia o "todo evento é hoje": o código antigo caía em `date.today()`.
    if not pagina.data_inicio:
        logger.debug("sem data na página, descartado: %s", bruto.url)
        return None
    if pagina.data_inicio < date.today().isoformat():
        return None

    lugar = _regiao(pagina, bruto, cidade_buscada, uf_buscada, perto)
    if lugar is None:
        logger.debug("fora da região buscada, descartado: %s", bruto.url)
        return None
    cidade, uf = lugar

    titulo = (pagina.titulo or bruto.titulo).strip()
    resumo = (pagina.resumo or bruto.trecho).strip()
    if not titulo:
        return None

    inscricao_inicio: Optional[str] = None
    inscricao_fim: Optional[str] = None
    if pagina.data_inicio:
        inscricao_inicio, inscricao_fim = await _completar_inscricao(titulo, cidade)

    return {
        "title": titulo[:300],
        "summary": resumo[:2000],
        "venue": pagina.local,
        "city": cidade[:120] if cidade else None,
        "state": (uf or "")[:2].upper() or None,
        "event_start": pagina.data_inicio,
        "event_end": pagina.data_fim,
        "is_free": pagina.gratuito,
        "price_info": pagina.preco_info,
        "registration_start": inscricao_inicio,
        "registration_end": inscricao_fim,
        "ticket_url": bruto.url,
        # A foto do cartaz quando a página publica uma; o ícone do site quando
        # não — um card sem imagem nenhuma some no meio dos outros.
        "image_url": pagina.imagem or evento_da_pagina.icone_do_site(bruto.url),
        "source": "busca",
        "source_url": bruto.url,
    }


def _regiao(
    pagina: "evento_da_pagina.DadosDaPagina",
    bruto: EventoBruto,
    cidade_buscada: str,
    uf_buscada: str,
    perto: set[str],
) -> Optional[tuple[str, str]]:
    """Onde o evento acontece — ou `None` se não é por aqui.

    Antes, a cidade do evento caía para a cidade BUSCADA quando a página não
    dizia nada: um evento de São Paulo virava "Vitória" por omissão, e a tela
    anunciava como se fosse perto. Agora a cidade precisa ser afirmada pela
    página (e estar no raio) ou pelo menos citada no título/trecho.
    """
    if pagina.online:
        return None  # a aba é de eventos PERTO de você; online é outra coisa

    if pagina.cidade:
        if geo.normaliza(pagina.cidade) in perto:
            return pagina.cidade, (pagina.estado or uf_buscada)
        return None

    procurada = geo.normaliza(cidade_buscada)
    texto = geo.normaliza(f"{bruto.titulo} {bruto.trecho} {pagina.local or ''}")
    if procurada and procurada in texto:
        return cidade_buscada, uf_buscada
    return None


_AI_SYSTEM_TECNOLOGIA = """Você separa eventos de TECNOLOGIA dos demais, a partir do título e do
trecho de cada um.

Conta como tecnologia: programação, dados, inteligência artificial, infra e
nuvem, segurança da informação, produto e design digital, startups e inovação
quando o assunto é tecnologia.

NÃO conta, mesmo que a palavra "tecnologia" ou "inovação" apareça no texto:
setor automotivo, agro, construção, saúde, moda, gastronomia, música, esporte,
religião, concurso público, feira de negócios de outro setor. Uma feira de
carros que fala em "inovação e tecnologia automotiva" é evento automotivo.

Na dúvida, responda false: uma lista curta e certa vale mais que uma longa com
lixo no meio."""

_AI_SCHEMA_TECNOLOGIA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "itens": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "indice": {"type": "INTEGER"},
                    "tecnologia": {"type": "BOOLEAN"},
                },
                "required": ["indice", "tecnologia"],
            },
        }
    },
    "required": ["itens"],
}


async def somente_tecnologia(brutos: list[EventoBruto]) -> list[EventoBruto]:
    """Filtra a lista, deixando só o que é evento de tecnologia.

    Em UMA chamada para a lista inteira, e não uma por evento: é mais rápido,
    mais barato, e o modelo compara os candidatos entre si — o que ajuda
    justamente nos casos de borda ("feira automotiva que fala em inovação").

    Se a IA estiver fora, devolve a lista inteira: melhor mostrar demais do que
    a aba vazia; o resto do pipeline ainda exige data e região.
    """
    if not brutos:
        return []
    listado = "\n".join(f"{i}. {b.titulo} — {b.trecho[:300]}" for i, b in enumerate(brutos))
    try:
        resultado = await generate_json(
            _AI_SYSTEM_TECNOLOGIA, f"Eventos:\n{listado}", _AI_SCHEMA_TECNOLOGIA
        )
    except AiProviderError as exc:
        logger.warning("classificação de tecnologia indisponível: %s", exc)
        return brutos

    itens = (resultado.content or {}).get("itens") or []
    aprovados = {
        int(item["indice"])
        for item in itens
        if isinstance(item, dict) and item.get("tecnologia") is True and str(item.get("indice", "")).isdigit()
    }
    return [b for i, b in enumerate(brutos) if i in aprovados]


# ---------------------------------------------------------------------------
# A varredura de uma região
# ---------------------------------------------------------------------------


def precisa_buscar(supabase: Client, cidade: Optional[str], uf: Optional[str]) -> bool:
    """Para a rota saber se vale agendar uma varredura — sem fazer nenhuma."""
    if not cidade or not uf:
        return False
    return _precisa_buscar(supabase, cidade, uf)


def _precisa_buscar(supabase: Client, cidade: str, uf: str) -> bool:
    """A região foi varrida há pouco?

    A marca é a varredura em si (`pathr_news_scan`), e não a existência de
    eventos gravados: região onde a busca não achava nada continuava "nunca
    buscada" e era varrida DE NOVO a cada abertura da tela — busca e IA
    inteiras, por nada. Era o "Buscando eventos…" que não terminava.
    """
    limite = (datetime.now(timezone.utc) - timedelta(seconds=_VALIDADE_S)).isoformat()
    try:
        recentes = (
            supabase.table("pathr_news_scan").select("id")
            .eq("city", cidade).eq("state", uf).gte("scanned_at", limite).limit(1).execute().data
            or []
        )
    except Exception:  # noqa: BLE001
        # Na dúvida NÃO varre: falha de leitura não pode virar enxurrada de
        # buscas a cada abertura.
        logger.warning("não consegui ler a marca de varredura", exc_info=True)
        return False
    return not recentes


def _marcar_varredura(supabase: Client, cidade: str, uf: str, achados: int) -> None:
    try:
        supabase.table("pathr_news_scan").upsert(
            {
                "city": cidade,
                "state": uf,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "found": achados,
            },
            on_conflict="city,state",
        ).execute()
    except Exception:  # noqa: BLE001
        logger.warning("não consegui marcar a varredura de %s/%s", cidade, uf, exc_info=True)


def _gravar(supabase: Client, campos: dict[str, Any]) -> bool:
    try:
        supabase.table("pathr_news_event").upsert(
            {**campos, "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="source_url",
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("gravação do evento %r falhou: %s", campos.get("source_url"), exc)
        return False


async def atualizar_regiao(supabase: Client, cidade: str, uf: str) -> int:
    """Varre a região e grava o que achar. Devolve quantos entraram.

    ## Por que grava um a um

    Antes, tudo era montado em memória e gravado no fim: uma falha no meio — ou
    a pessoa fechando a aba — jogava fora o trabalho inteiro, e a abertura
    seguinte recomeçava do zero. Agora cada evento pronto é gravado na hora.

    ## Por que a marca vem primeiro

    `_marcar_varredura` é chamada ANTES de varrer: assim duas telas abertas ao
    mesmo tempo não disparam duas varreduras da mesma região, e uma falha no
    meio não deixa a região marcada como "nunca vista" — que é o que fazia a
    busca reiniciar sem fim.
    """
    if not cidade or not uf or not _precisa_buscar(supabase, cidade, uf):
        return 0

    _marcar_varredura(supabase, cidade, uf, 0)

    brutos = await buscar_bruto(cidade, uf)
    if not brutos:
        return 0

    candidatos = await somente_tecnologia(brutos[:_MAXIMO_POR_VARREDURA])
    if not candidatos:
        return 0

    centro = geo.achar(cidade, uf)
    perto = (
        {geo.normaliza(c.nome) for c, _ in geo.no_raio(centro, _RAIO_DA_BUSCA_KM)}
        if centro
        else {geo.normaliza(cidade)}
    )

    vez = asyncio.Semaphore(_CONCORRENCIA)

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": _UA}, follow_redirects=False
    ) as cliente:

        async def um(bruto: EventoBruto) -> bool:
            async with vez:
                campos = await _montar(cliente, bruto, cidade, uf, perto)
            if not campos:
                return False
            # `to_thread` porque o cliente do Supabase é síncrono: gravar
            # direto aqui pararia o laço de eventos, e as outras páginas
            # ficariam esperando a escrita de uma.
            return await asyncio.to_thread(_gravar, supabase, campos)

        resultados = await asyncio.gather(*(um(b) for b in candidatos), return_exceptions=True)

    entraram = 0
    for resultado in resultados:
        if isinstance(resultado, Exception):
            logger.warning("evento falhou na varredura: %s", resultado)
        elif resultado:
            entraram += 1

    _marcar_varredura(supabase, cidade, uf, entraram)
    logger.info("varredura de %s/%s: %d de %d entraram", cidade, uf, entraram, len(candidatos))
    return entraram


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
        "imagem": evento.get("image_url"),
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
            proximas = {geo.normaliza(c.nome) for c, _ in geo.no_raio(centro, raio_km)}
            # Só cidade dentro do raio. Antes valia também "mesmo estado" e
            # "sem cidade" — e o estado inteiro não é "perto de você": um
            # evento a 400 km aparecia como se fosse na esquina, junto com
            # todo evento cuja cidade o pipeline não soube dizer.
            linhas = [l for l in linhas if geo.normaliza(str(l.get("city") or "")) in proximas]

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
