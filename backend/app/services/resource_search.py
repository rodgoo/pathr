"""Descoberta de material para a biblioteca: busca real primeiro, IA por último.

Até aqui `pathr_resource` era uma tabela que só se lia. O catálogo existia no
modelo, a Biblioteca sabia filtrar e a aba Material sabia recortar por tag —
mas nada nunca escreveu uma linha, então todo usuário via a mesma lista vazia.
Este módulo é quem preenche.

## Por que duas fontes, e nesta ordem

1. **Busca real** (YouTube Data API para vídeo, Tavily/Brave para artigo). O
   item existe porque um índice real o devolveu, com título, autor e data que
   vieram da fonte — não de um modelo tentando lembrar deles.
2. **IA como reserva**, só quando a busca não achou nada ou a chave não está
   configurada. Um LLM sabe recomendar a documentação canônica de um assunto,
   mas erra URL com frequência alta demais para ser fonte primária: ele
   compõe endereços plausíveis que nunca existiram.

A consequência prática dessa ordem é o `quality_score`: resultado de busca
entra acima de sugestão de IA, e a Biblioteca ordena por ele.

## Toda URL passa por validação antes de virar linha

Exceto as do YouTube, que chegam com um id devolvido pela própria API — pedir
a página de volta só confirmaria o que a API acabou de afirmar. Todo o resto
leva um HEAD (com GET de reserva, porque muito servidor responde 405 a HEAD) e
só entra no banco se responder. É o que separa "a IA sugeriu" de "o link abre".

## Cota é a restrição real, não custo

`search.list` da YouTube Data API custa 100 das 10.000 unidades diárias: ~99
buscas por dia para o app INTEIRO, todos os usuários somados. Por isso a
curadoria é por tag e não por usuário — uma busca por "Docker" serve todo mundo
que estuda Docker — e por isso existe `pathr_tag.curated_at`, que segura a
próxima busca da mesma tag por `_COOLDOWN`.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.ai_providers import AiProviderError, generate_json
from app.config import settings

logger = logging.getLogger("pathr.resource_search")

# Uma tag curada há menos que isto não é buscada de novo. Duas semanas porque
# conteúdo técnico bom não aparece toda semana, e a cota diária é o recurso
# escasso — ver o cabeçalho.
_COOLDOWN = timedelta(days=14)

# Timeout curto de propósito: isto roda dentro de uma requisição HTTP do
# usuário. Uma fonte lenta é uma fonte que fica de fora desta rodada, não uma
# tela que trava.
_TIMEOUT = 12.0

# Quantos itens cada fonte devolve por tag. O teto do que vai ao banco é a
# soma, e ele existe para a Biblioteca não virar uma lista de 40 links iguais
# sobre o mesmo assunto.
_MAX_VIDEOS = 5
_MAX_ARTICLES = 5
# Exercício é para resolver, não para colecionar: três bons bastam por tag.
_MAX_EXERCISES = 3
# Documentação boa é uma por assunto, não cinco páginas da mesma árvore.
_MAX_DOCS = 4
_MAX_AI = 4

# O piso de quem veio de busca real e o teto de quem veio da IA. Ficam lado a
# lado porque a relação entre os dois É a regra: a Biblioteca ordena por
# `quality_score`, então `_AI_SCORE < _SEARCH_FLOOR` é o que faz "busca real
# antes de sugestão de modelo" valer na tela, e não só no texto deste arquivo.
# Separá-los deixou o piso do artigo em 20 contra 38 da IA — o inverso do
# prometido, e invisível até um teste comparar os dois.
_SEARCH_FLOOR = 40
_AI_SCORE = 38
assert _AI_SCORE < _SEARCH_FLOOR

# Alguns servidores recusam requisição sem User-Agent de navegador. Não é
# disfarce: é o mínimo para a validação não reprovar um link que abre bem no
# navegador da pessoa.
_UA = "Mozilla/5.0 (compatible; PathRBot/1.0; +https://pathr.notter.com.br)"

_YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_YOUTUBE_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
_TAVILY_SEARCH = "https://api.tavily.com/search"
_BRAVE_SEARCH = "https://api.search.brave.com/res/v1/web/search"


@dataclass
class Candidate:
    """Um recurso encontrado, no formato que `pathr_resource` espera.

    Existe como dataclass e não como dict solto porque três fontes diferentes
    convergem para cá, e um campo esquecido por uma delas viraria um NULL numa
    coluna NOT NULL só na hora do insert.
    """

    kind: str
    title: str
    url: str
    provider: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_min: Optional[int] = None
    language: str = "pt"
    level: Optional[str] = None
    quality_score: int = 50
    published_at: Optional[date] = None
    # Preenchido pelo chamador — a fonte não sabe de qual tag veio a busca.
    tag_ids: list[str] = field(default_factory=list)
    # Só para log e teste: de onde veio. Não vai para o banco.
    source: str = "?"

    def to_row(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title[:300],
            "url": self.url,
            "provider": self.provider,
            "author": self.author,
            "description": (self.description or "")[:1000] or None,
            "thumbnail_url": self.thumbnail_url,
            "duration_min": self.duration_min,
            "language": self.language,
            "level": self.level,
            "is_free": True,
            "tag_ids": self.tag_ids,
            "quality_score": max(0, min(100, self.quality_score)),
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


# ---------------------------------------------------------------------------
# Entrada pública
# ---------------------------------------------------------------------------


def sources_enabled() -> dict[str, bool]:
    """Quais fontes têm chave. O router usa para explicar uma volta vazia."""
    return {
        "youtube": bool(settings.youtube_api_key.strip()),
        "artigos": bool(settings.tavily_api_key.strip() or settings.brave_api_key.strip()),
    }


def needs_curation(tag: dict[str, Any], now: Optional[datetime] = None) -> bool:
    """A tag está fora da carência (ou nunca foi curada)?

    Separado de `search_for_tag` para o chamador poder decidir ANTES de gastar
    qualquer chamada — inclusive para responder "nada a fazer" sem rede.
    """
    stamp = tag.get("curated_at")
    if not stamp:
        return True
    if isinstance(stamp, str):
        try:
            stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            # Carimbo ilegível é tratado como ausente: melhor buscar de novo do
            # que deixar a tag presa para sempre por um dado corrompido.
            return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - stamp >= _COOLDOWN


async def search_for_tag(tag: dict[str, Any]) -> list[Candidate]:
    """Todos os candidatos VÁLIDOS para uma tag, de todas as fontes ligadas.

    Não escreve nada e não conhece o banco — é o que torna esta função
    testável sem Supabase, e o que deixa o router decidir o que fazer com o
    resultado.
    """
    name = str(tag.get("name") or tag.get("slug") or "").strip()
    if not name:
        return []

    tag_id = str(tag["id"]) if tag.get("id") else None

    # As duas buscas são independentes: uma fonte fora do ar não pode levar a
    # outra junto, então `return_exceptions` e cada falha vira log, não 500.
    found = await asyncio.gather(
        _youtube(name),
        _articles(name),
        _documentacao(name),
        _exercicios(name),
        return_exceptions=True,
    )

    candidates: list[Candidate] = []
    for result in found:
        if isinstance(result, BaseException):
            logger.warning("fonte de busca falhou para %r: %s", name, result)
            continue
        candidates.extend(result)

    # A IA entra só para completar o que a busca não cobriu. Se as duas fontes
    # já trouxeram material, gastar uma chamada de LLM aqui seria pagar por um
    # resultado pior que o que já está na mão.
    if not candidates:
        try:
            candidates.extend(await _ai_fallback(name, tag.get("category")))
        except AiProviderError as exc:
            logger.warning("curadoria por IA indisponível para %r: %s", name, exc)

    validated = await _keep_reachable(candidates)

    for candidate in validated:
        if tag_id:
            candidate.tag_ids = [tag_id]

    validated.sort(key=lambda item: item.quality_score, reverse=True)
    return validated


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------


async def _youtube(subject: str) -> list[Candidate]:
    """Vídeos pela YouTube Data API v3.

    Duas chamadas por tag, e não uma: `search.list` devolve id e título mas
    NÃO devolve duração nem visualizações, que é justamente o que separa uma
    aula de 40 minutos de um short de 30 segundos. A segunda chamada
    (`videos.list`) custa 1 unidade contra as 100 da primeira, então o custo
    real de detalhar é desprezível perto de não detalhar.
    """
    key = settings.youtube_api_key.strip()
    if not key:
        return []

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as client:
        search = await client.get(
            _YOUTUBE_SEARCH,
            params={
                "key": key,
                "part": "snippet",
                "q": f"{subject} tutorial",
                "type": "video",
                "maxResults": _MAX_VIDEOS,
                "relevanceLanguage": "pt",
                # Exclui vídeo que o dono marcou como não incorporável: o app
                # abre o link em aba nova, e um resultado que não toca é ruído
                # na lista.
                "videoEmbeddable": "true",
                "safeSearch": "moderate",
            },
        )
        if search.status_code != 200:
            raise RuntimeError(f"YouTube search HTTP {search.status_code}: {search.text[:200]}")

        items = search.json().get("items") or []
        ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        if not ids:
            return []

        detail = await client.get(
            _YOUTUBE_VIDEOS,
            params={
                "key": key,
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(ids),
            },
        )
        if detail.status_code != 200:
            raise RuntimeError(f"YouTube videos HTTP {detail.status_code}: {detail.text[:200]}")

    out: list[Candidate] = []
    for item in detail.json().get("items") or []:
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        minutes = _iso8601_minutes((item.get("contentDetails") or {}).get("duration"))

        # Short não é material de estudo. O corte em 3 minutos é o mesmo que o
        # YouTube usa para separar Shorts do resto.
        if minutes is not None and minutes < 3:
            continue

        published = _parse_date(snippet.get("publishedAt"))
        out.append(
            Candidate(
                kind="video",
                title=snippet.get("title") or "Vídeo",
                url=f"https://www.youtube.com/watch?v={item['id']}",
                provider="youtube",
                author=snippet.get("channelTitle"),
                description=snippet.get("description"),
                thumbnail_url=((snippet.get("thumbnails") or {}).get("high") or {}).get("url"),
                duration_min=minutes,
                # O idioma que o canal declarou vale mais que qualquer
                # heurística. Quando não vem — é o caso mais comum — detecta
                # pelo título e pela descrição. O default "pt" de antes
                # carimbava como português todo vídeo sem declaração, e o
                # filtro "Português" virava uma lista de vídeos em inglês.
                language=(
                    snippet.get("defaultAudioLanguage")
                    or snippet.get("defaultLanguage")
                    or _guess_language(snippet.get("title"), snippet.get("description"))
                )[:2],
                quality_score=_score_video(stats, published),
                published_at=published,
                source="youtube",
            )
        )
    return out


def _score_video(stats: dict[str, Any], published: Optional[date]) -> int:
    """0..100 a partir de audiência, aprovação e idade.

    Audiência entra em log: a diferença entre 1k e 10k views diz muito sobre
    um vídeo, entre 1M e 10M quase nada. Idade pesa porque tutorial de
    framework envelhece mal — é o caso que o comentário de `quality_score` no
    modelo cita ("tutorial de 2015 sobre framework que mudou").
    """
    views = _as_int(stats.get("viewCount"))
    likes = _as_int(stats.get("likeCount"))

    # 0 views -> 0 ; 1k -> ~30 ; 100k -> ~50 ; 10M -> ~70
    audience = min(70.0, math.log10(views + 1) * 10) if views else 0.0
    # Proporção de likes por view, saturando em 5% (excelente no YouTube).
    approval = min(15.0, (likes / views) * 300) if views and likes else 0.0

    freshness = 15.0
    if published:
        years = (date.today() - published).days / 365.25
        # Perde 3 pontos por ano, some aos 5 anos.
        freshness = max(0.0, 15.0 - years * 3)

    return int(round(audience + approval + freshness))


# ---------------------------------------------------------------------------
# Artigos — Tavily ou Brave
# ---------------------------------------------------------------------------


async def _articles(subject: str) -> list[Candidate]:
    """Artigos pelo buscador configurado, nos DOIS idiomas.

    Duas consultas, e não uma. O catálogo é global e o filtro de idioma da
    Biblioteca corta na leitura — mas cortar só funciona se houver o que
    mostrar dos dois lados. Uma consulta só devolvia quase sempre inglês, e
    quem escolhia "Português" via a lista vazia: o filtro estava certo, o
    acervo é que não tinha material em português para filtrar.

    A consulta em português cita "português" de propósito. Sem isso o buscador
    responde em inglês mesmo com termos em português, porque é onde está o
    volume.

    Tavily ganha do Brave quando as duas chaves existem porque já devolve um
    resumo por resultado; com o Brave o `description` sai do trecho do índice,
    que costuma vir cortado no meio da frase.
    """
    if settings.tavily_api_key.strip():
        buscar = _tavily
    elif settings.brave_api_key.strip():
        buscar = _brave
    else:
        return []

    resultados = await asyncio.gather(
        buscar(f"{subject} tutorial guia em português", _MAX_ARTICLES),
        buscar(f"{subject} tutorial guide", _MAX_ARTICLES),
        return_exceptions=True,
    )
    saida: list[Candidate] = []
    for resultado in resultados:
        if isinstance(resultado, BaseException):
            logger.warning("busca de artigo falhou para %r: %s", subject, resultado)
            continue
        saida.extend(resultado)
    return saida


async def _buscar_varias(consultas: list[str], quantos: int) -> list[Candidate]:
    """Várias consultas no buscador configurado, em paralelo, somadas.

    Uma falha não derruba as outras: cada consulta é um idioma, e perder a
    inglesa não pode apagar o que a portuguesa trouxe.
    """
    if settings.tavily_api_key.strip():
        buscar = _tavily
    elif settings.brave_api_key.strip():
        buscar = _brave
    else:
        return []
    resultados = await asyncio.gather(
        *(buscar(consulta, quantos) for consulta in consultas), return_exceptions=True
    )
    saida: list[Candidate] = []
    for resultado in resultados:
        if isinstance(resultado, BaseException):
            logger.warning("consulta de busca falhou: %s", resultado)
            continue
        saida.extend(resultado)
    return saida


async def _documentacao(subject: str) -> list[Candidate]:
    """A documentação oficial, procurada como tal.

    A consulta de artigo ("tutorial guia") traz quem ESCREVE sobre o assunto,
    não a fonte. Numa medição com "Docker" ela devolveu quatro blogs e nenhuma
    linha de docs.docker.com — e o filtro "Documentação" da Biblioteca ficava
    permanentemente vazio.
    """
    # Duas consultas: a portuguesa acha a documentação traduzida onde ela
    # existe (MDN, docs.python.org/pt-br, React em pt-BR) e a inglesa garante a
    # fonte canônica. Só a inglesa deixava o filtro "Português" sem
    # documentação nenhuma, mesmo para projeto com tradução oficial.
    bruto = await _buscar_varias(
        [
            f"{subject} documentação oficial em português",
            f"{subject} official documentation reference",
        ],
        _MAX_DOCS,
    )
    # Só o que o endereço confirma ser documentação. O resto veio como artigo e
    # já entra pela outra consulta.
    return [item for item in bruto if item.kind in {"doc", "repo"}]


async def _exercicios(subject: str) -> list[Candidate]:
    """Onde PRATICAR o assunto, e não onde ler sobre ele.

    Consulta própria porque a busca de artigo ("tutorial guia") não devolve
    exercício: quem escreve tutorial e quem publica exercício otimizam para
    palavras diferentes. Classificar melhor não resolveria — o resultado
    simplesmente não vinha.

    O termo cita as plataformas de propósito. Uma busca por "exercícios de
    Docker" traz listas de blog com cinco perguntas; citar os sites que existem
    para isso traz a página onde se resolve.
    """
    # Em português primeiro: Beecrowd e Neps são brasileiros e têm enunciado em
    # português, que é o que o filtro "Português" pede. A inglesa cobre as
    # plataformas grandes, que só existem em inglês.
    bruto = await _buscar_varias(
        [
            f"{subject} exercícios em português beecrowd lista de exercícios",
            f"{subject} practice exercises exercism leetcode hackerrank codewars",
        ],
        _MAX_EXERCISES,
    )

    # Só o que a classificação reconheceu COMO exercício. O resto da busca é
    # artigo comum sobre o assunto, e ele já entra pela outra consulta —
    # deixá-lo aqui duplicaria a lista.
    return [item for item in bruto if item.kind == "exercise"]


async def _tavily(subject: str, quantos: int = _MAX_ARTICLES) -> list[Candidate]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as client:
        response = await client.post(
            _TAVILY_SEARCH,
            json={
                "api_key": settings.tavily_api_key.strip(),
                "query": f"{subject} tutorial guia",
                "max_results": quantos,
                "search_depth": "basic",
                "include_answer": False,
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Tavily HTTP {response.status_code}: {response.text[:200]}")

    out: list[Candidate] = []
    for rank, item in enumerate(response.json().get("results") or []):
        url = item.get("url")
        if not url or _is_video_host(url):
            continue
        out.append(
            Candidate(
                kind=_classifica(url),
                title=item.get("title") or url,
                url=url,
                provider=_provider_of(url),
                description=item.get("content"),
                language=_guess_language(item.get("title"), item.get("content")),
                quality_score=_score_article(rank, url),
                source="tavily",
            )
        )
    return out


async def _brave(subject: str, quantos: int = _MAX_ARTICLES) -> list[Candidate]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            _BRAVE_SEARCH,
            params={"q": f"{subject} tutorial guia", "count": quantos},
            headers={
                "X-Subscription-Token": settings.brave_api_key.strip(),
                "Accept": "application/json",
                "User-Agent": _UA,
            },
        )
    if response.status_code != 200:
        raise RuntimeError(f"Brave HTTP {response.status_code}: {response.text[:200]}")

    results = ((response.json().get("web") or {}).get("results")) or []
    out: list[Candidate] = []
    for rank, item in enumerate(results):
        url = item.get("url")
        if not url or _is_video_host(url):
            continue
        out.append(
            Candidate(
                kind=_classifica(url),
                title=item.get("title") or url,
                url=url,
                provider=_provider_of(url),
                description=_strip_tags(item.get("description")),
                language=_guess_language(item.get("title"), item.get("description")),
                quality_score=_score_article(rank, url),
                source="brave",
            )
        )
    return out


# Domínios onde conteúdo técnico costuma ser bom o bastante para começar por
# ele. Não é allowlist — nada é excluído por não estar aqui, só ordenado
# abaixo. Uma allowlist de verdade fecharia o app para o blog de quem escreve
# a melhor explicação de um assunto de nicho.
# Hosts de vídeo. O buscador web devolve páginas do YouTube entre os
# resultados de texto, e elas chegavam aqui como `kind="article"`: sem
# duração, sem o corte de Shorts, sem pontuação por audiência — e no filtro
# "Artigos" da Biblioteca. Vídeo é trabalho da YouTube Data API, que sabe
# medir vídeo; o que ela não devolveu para esta busca não fica melhor por vir
# de segunda mão como texto.
_VIDEO_HOSTS = {
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "vimeo.com",
    "dailymotion.com",
    "twitch.tv",
}


def _is_video_host(url: str) -> bool:
    return (urlparse(url).hostname or "").removeprefix("www.") in _VIDEO_HOSTS


# Sites cujo propósito é EXERCITAR, não explicar. Um item daqui não é artigo:
# a pessoa não lê, ela resolve — e misturá-lo com texto no mesmo filtro apaga a
# única diferença que importa na hora de estudar.
_EXERCICIO_HOSTS = {
    "exercism.org",
    "leetcode.com",
    "hackerrank.com",
    "codewars.com",
    "beecrowd.com.br",
    "judge.beecrowd.com",
    "neps.academy",
    "codingame.com",
    "adventofcode.com",
    "hackerearth.com",
    "edabit.com",
    "codechef.com",
    "sqlzoo.net",
    "pgexercises.com",
    "regex101.com",
    "frontendmentor.io",
    "codepen.io",
}

# Sinais de que a página É a documentação, e não alguém escrevendo sobre ela.
# O host tem prioridade; o caminho (/docs/, /reference/) pega o resto.
_DOC_HOSTS_PREFIXOS = ("docs.", "developer.", "doc.", "learn.", "devdocs.")
_DOC_HOSTS_SUFIXOS = (".readthedocs.io", ".readthedocs.org")
_DOC_CAMINHOS = ("/docs/", "/doc/", "/documentation/", "/reference/", "/api/", "/manual/")


def _classifica(url: str) -> str:
    """Que TIPO de material é este endereço.

    Existe porque a busca web devolvia tudo como `article`. Os filtros
    "Documentação" e "Exercícios" da Biblioteca nunca tinham o que mostrar —
    não porque a busca não achasse essas páginas, mas porque elas entravam
    rotuladas como artigo.

    Classifica pelo endereço e não pelo texto: `docs.python.org/3/library/` diz
    o que é sem precisar ler a página, e o título ("Tutorial") mentiria.
    """
    endereco = urlparse(url)
    host = (endereco.hostname or "").removeprefix("www.")
    caminho = (endereco.path or "").lower()

    if host in _EXERCICIO_HOSTS:
        return "exercise"
    # Host EXATO, e nao sufixo: `docs.github.com` termina em "github.com" e
    # e documentacao, nao repositorio. Medido em producao -- duas paginas do
    # GitHub Docs tinham entrado como "repo".
    if host in {"github.com", "gitlab.com", "bitbucket.org"}:
        return "repo"
    if (
        host.startswith(_DOC_HOSTS_PREFIXOS)
        or host.endswith(_DOC_HOSTS_SUFIXOS)
        or any(marca in caminho for marca in _DOC_CAMINHOS)
    ):
        return "doc"
    return "article"


_TRUSTED = {
    "developer.mozilla.org": 22,
    "docs.python.org": 22,
    "kubernetes.io": 20,
    "docs.docker.com": 20,
    "postgresql.org": 20,
    "react.dev": 20,
    "fastapi.tiangolo.com": 20,
    "docs.oracle.com": 16,
    "learn.microsoft.com": 16,
    "freecodecamp.org": 14,
    "github.com": 14,
    "stackoverflow.com": 14,
    "digitalocean.com": 12,
    "dev.to": 10,
    "medium.com": 8,
}


def _score_article(rank: int, url: str) -> int:
    """0..100 a partir da posição no buscador e da reputação do domínio.

    Fica abaixo do teto dos vídeos de propósito: um artigo não traz sinal de
    audiência, então a confiança nele é menor que a de um vídeo com 200 mil
    views e 98% de aprovação.
    """
    base = max(_SEARCH_FLOOR, 75 - rank * 5)
    host = (urlparse(url).hostname or "").removeprefix("www.")
    bonus = _TRUSTED.get(host, 0)
    if not bonus and host.endswith(".org"):
        bonus = 5
    return base + bonus


# ---------------------------------------------------------------------------
# Reserva por IA
# ---------------------------------------------------------------------------

_AI_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "recursos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "titulo": {"type": "STRING"},
                    "url": {"type": "STRING"},
                    "tipo": {"type": "STRING"},
                    "autor": {"type": "STRING"},
                    "descricao": {"type": "STRING"},
                    "idioma": {"type": "STRING"},
                    "nivel": {"type": "STRING"},
                },
                "required": ["titulo", "url", "tipo"],
            },
        }
    },
    "required": ["recursos"],
}

_AI_SYSTEM = """Você indica material de estudo para profissionais de tecnologia.

Regras, nesta ordem de importância:

1. Só indique endereço que você tem certeza que existe HOJE. Prefira a
   documentação oficial do projeto, o repositório no GitHub e sites de
   referência estáveis (MDN, docs.python.org, kubernetes.io). NUNCA invente um
   caminho dentro de um domínio real: um link quebrado é pior que um item a
   menos, e todo endereço será verificado antes de ser usado.
2. Nada de post individual de blog, vídeo de YouTube ou artigo de Medium — as
   URLs deles são instáveis e você não tem como confirmá-las. Fique na raiz da
   documentação e em páginas de referência.
3. `tipo` é um de: doc, repo, book, article.
4. Português quando existir material bom; inglês quando for a única opção
   séria. Marque em `idioma` com "pt" ou "en".
"""


async def _ai_fallback(subject: str, category: Optional[str]) -> list[Candidate]:
    """Sugestões do LLM — só quando a busca real não trouxe nada.

    O prompt empurra o modelo para documentação e repositório justamente
    porque são os endereços que ele acerta: a raiz da doc de uma biblioteca é
    estável e memorizável, enquanto o link de um post de blog de 2021 é o tipo
    de coisa que ele reconstrói errado com confiança total.
    """
    contexto = f" (categoria: {category})" if category else ""
    prompt = (
        f"Indique até {_MAX_AI} materiais para quem está estudando "
        f"{subject}{contexto}. Priorize a documentação oficial."
    )
    result = await generate_json(_AI_SYSTEM, prompt, _AI_SCHEMA)

    out: list[Candidate] = []
    for item in (result.data or {}).get("recursos") or []:
        url = str(item.get("url") or "").strip()
        # O prompt já proíbe vídeo, mas confiar só no prompt é confiar no
        # modelo obedecer — e ele é a fonte menos confiável das três.
        if not url.startswith(("http://", "https://")) or _is_video_host(url):
            continue
        kind = str(item.get("tipo") or "doc").lower()
        # "course" saiu do vocabulário: a Biblioteca deixou de ter esse filtro
        # porque um link para uma plataforma de curso não é material que o app
        # consiga acompanhar — ele não sabe se a pessoa assistiu, nem o que ela
        # aprendeu. Um curso indicado assim vira documentação ou artigo.
        if kind == "course":
            kind = "doc"
        if kind not in {"doc", "repo", "book", "article", "exercise"}:
            kind = "doc"
        out.append(
            Candidate(
                kind=kind,
                title=str(item.get("titulo") or url),
                url=url,
                provider=_provider_of(url),
                author=item.get("autor"),
                description=item.get("descricao"),
                language=str(item.get("idioma") or "pt")[:2],
                level=item.get("nivel"),
                # Teto baixo por construção: passou no HEAD, mas ninguém além
                # do modelo garantiu que o conteúdo é bom. Entra na lista
                # abaixo de qualquer resultado de busca real.
                quality_score=_AI_SCORE,
                source="ia",
            )
        )
    return out[:_MAX_AI]


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


async def _keep_reachable(candidates: list[Candidate]) -> list[Candidate]:
    """Descarta o que não responde, e o que está duplicado na própria leva.

    O YouTube passa direto: a URL foi montada a partir de um id que a API
    acabou de devolver, então pedir a página de volta gastaria uma requisição
    para confirmar o que já é certo.
    """
    seen: set[str] = set()
    unique: list[Candidate] = []
    for candidate in candidates:
        key = candidate.url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    # Concorrência limitada: 8 é o suficiente para a validação não dominar o
    # tempo da requisição, e baixo o bastante para não parecer varredura para
    # quem recebe.
    gate = asyncio.Semaphore(8)

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": _UA}
    ) as client:

        async def check(candidate: Candidate) -> Optional[Candidate]:
            if candidate.provider == "youtube":
                return candidate
            async with gate:
                return candidate if await _reachable(client, candidate.url) else None

        checked = await asyncio.gather(*(check(item) for item in unique))

    return [item for item in checked if item is not None]


async def _reachable(client: httpx.AsyncClient, url: str) -> bool:
    """A URL responde? HEAD primeiro, GET quando o servidor recusa HEAD.

    Muito servidor responde 405 (ou 403, ou 501) a HEAD mesmo servindo a
    página normalmente por GET. Tratar isso como link quebrado descartaria
    material bom, então a segunda tentativa existe — mas com `stream`, para
    fechar a conexão assim que o status chega, sem baixar a página inteira.
    """
    try:
        head = await client.head(url)
        if head.status_code < 400:
            return True
        if head.status_code not in (403, 405, 501):
            return False
    except httpx.HTTPError:
        # Timeout ou conexão derrubada: ainda vale tentar o GET, porque alguns
        # servidores simplesmente não atendem HEAD.
        pass

    try:
        async with client.stream("GET", url) as response:
            return response.status_code < 400
    except httpx.HTTPError as exc:
        logger.debug("link descartado %s: %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

_ISO8601 = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
_TAGS = re.compile(r"<[^>]+>")

# Palavras curtas que só aparecem em português. Não é detecção de idioma de
# verdade — é o suficiente para separar "pt" de "en" num título técnico, onde
# os nomes próprios (Docker, React) são iguais nos dois.
# Palavras funcionais de cada idioma. A decisão é por CONTAGEM, e não pela
# presença de uma palavra: "How to use Docker para iniciantes" tem "para" e é
# inglês, e a regra antiga ("achou uma palavra portuguesa? é português")
# etiquetava conteúdo inglês como pt — que é exatamente o que fazia o filtro
# "Português" devolver artigo em inglês.
#
# Palavras funcionais e não vocabulário técnico de propósito: "Docker",
# "React" e "deploy" aparecem igual nos dois idiomas e não separam nada.
_STOP_PT = {
    "a", "ao", "aos", "as", "até", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "essa", "esse", "está", "eu", "foi", "isso", "já", "mais",
    "mas", "na", "nas", "no", "nos", "não", "o", "os", "ou", "para", "pela",
    "pelo", "por", "porque", "quando", "que", "se", "sem", "ser", "seu", "sobre",
    "são", "também", "tem", "ter", "um", "uma", "você", "guia", "aprenda",
    "passo", "iniciantes", "início", "prática", "completo", "curso", "aula",
}
_STOP_EN = {
    "a", "about", "an", "and", "are", "as", "at", "be", "but", "by", "can",
    "complete", "for", "from", "get", "guide", "has", "have", "how", "in", "into",
    "is", "it", "learn", "make", "more", "not", "of", "on", "or", "should",
    "than", "that", "the", "then", "this", "to", "use", "using", "was", "what",
    "when", "where", "which", "will", "with", "would", "you", "your", "beginners",
    "tutorial", "step",
}


def _iso8601_minutes(duration: Optional[str]) -> Optional[int]:
    """PT1H2M10S -> 62. O YouTube só entrega duração neste formato."""
    if not duration:
        return None
    match = _ISO8601.fullmatch(duration)
    if not match:
        return None
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    total = hours * 60 + minutes + (1 if seconds >= 30 else 0)
    return total or None


def _parse_date(stamp: Optional[str]) -> Optional[date]:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _provider_of(url: str) -> Optional[str]:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return host or None


def _strip_tags(text: Optional[str]) -> Optional[str]:
    """O Brave devolve o trecho com <strong> em volta do termo buscado."""
    return _TAGS.sub("", text).strip() if text else None


def _guess_language(*parts: Optional[str]) -> str:
    """"pt" ou "en", por contagem de palavras funcionais.

    Conta OCORRÊNCIAS e não palavras distintas: um texto inglês com um "para"
    solto perde para os seus dez "the". As palavras comuns aos dois conjuntos
    ("a") se anulam sozinhas, porque somam dos dois lados.

    Empate cai em "en", e a assimetria é deliberada: quase todo conteúdo
    técnico é inglês, e o erro que a pessoa relata é o inverso — inglês
    aparecendo no filtro "Português". Na dúvida, o item fica fora do filtro
    mais restrito, e não dentro dele.
    """
    blob = " ".join(part for part in parts if part).lower()
    palavras = re.findall(r"[a-zà-ú]+", blob)
    if not palavras:
        return "en"
    pt = sum(1 for palavra in palavras if palavra in _STOP_PT)
    en = sum(1 for palavra in palavras if palavra in _STOP_EN)
    return "pt" if pt > en else "en"
