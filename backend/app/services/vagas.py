"""Vagas reais, de fontes confiáveis, e o que falta para cada uma.

## As fontes, e por que só estas

- **Gupy** — a maior plataforma de recrutamento do Brasil. O portal público
  (portal.gupy.io) lê de uma API aberta, sem chave; é ela que usamos.
- **Remotive** — vagas remotas internacionais, API aberta. Os termos pedem
  poucas chamadas por dia, link de volta para a vaga na Remotive e crédito à
  fonte: por isso o cache longo e o nome da fonte em cada cartão.
- **Adzuna** — agregador com API oficial para o Brasil. Exige chave
  (gratuita); sem ela, a fonte fica de fora e a tela diz isso.
- **Busca em sites de vaga** (LinkedIn Jobs, Vagas.com, Programathor, Indeed,
  InfoJobs, Glassdoor) pelo Tavily ou Brave que o app já usa. Daqui só sai o
  LINK e o título que o buscador devolveu: não lemos nem copiamos a página, e
  só entra endereço com cara de vaga individual — página de busca não conta.

O LinkedIn não tem API de vagas para terceiros, e raspar o site viola os
termos dele. A vaga do LinkedIn aparece quando o buscador a encontra, como link.

## A compatibilidade

Determinística, sem IA: as tecnologias citadas no texto da vaga, casadas com o
catálogo de tags (nomes e apelidos), contra as competências da pessoa. Na
listagem isso roda para dezenas de vagas de uma vez — IA ali seria lenta e
cara. A análise de UMA vaga, pedida pela pessoa, usa IA para separar o que é
obrigatório do que é desejável (ver `analisar`).
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services import courses

logger = logging.getLogger("pathr.vagas")

_TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_UA = "PathR/1.0 (+https://pathr.notter.com.br)"

GUPY = "https://employability-portal.gupy.io/api/v1/jobs"
REMOTIVE = "https://remotive.com/api/remote-jobs"
ADZUNA = "https://api.adzuna.com/v1/api/jobs/br/search/1"
TAVILY = "https://api.tavily.com/search"
BRAVE = "https://api.search.brave.com/res/v1/web/search"

# Uma busca por termo e fonte a cada tantas horas. Vaga não muda de minuto em
# minuto, e as fontes abertas pedem moderação (a Remotive, explicitamente).
_VALIDADE_S = {"gupy": 3 * 3600, "remotive": 12 * 3600, "adzuna": 6 * 3600, "busca": 12 * 3600}

# Sites de vaga em que confiamos, com o formato do endereço de UMA vaga.
SITES_DE_VAGA: dict[str, re.Pattern[str]] = {
    "linkedin.com": re.compile(r"/jobs/view/"),
    "vagas.com.br": re.compile(r"/vagas/v\d+"),
    "programathor.com.br": re.compile(r"/jobs/\d+"),
    "indeed.com": re.compile(r"viewjob|/rc/clk|[?&]jk="),
    "infojobs.com.br": re.compile(r"/vaga-de-"),
    # "/Vaga/" no Glassdoor é página de LISTAGEM ("776 vagas de java"), não vaga.
    "glassdoor.com.br": re.compile(r"/job-listing/"),
}

NOME_DO_SITE = {
    "linkedin.com": "LinkedIn",
    "vagas.com.br": "Vagas.com",
    "programathor.com.br": "Programathor",
    "indeed.com": "Indeed",
    "infojobs.com.br": "InfoJobs",
    "glassdoor.com.br": "Glassdoor",
}

# Remotive publica vaga "remota" restrita a países. Só serve quem pode ser
# contratado daqui.
_LOCAL_QUE_ACEITA_BRASIL = re.compile(
    r"worldwide|anywhere|global|brazil|brasil|latam|latin america|south america|americas", re.I
)

# Categorias de tag que dizem o que a pessoa FAZ — são os termos da busca.
# "metodologia" e "idioma" descrevem, mas ninguém procura vaga de "Scrum".
_CATEGORIAS_DE_BUSCA = ("linguagem", "backend", "frontend", "mobile", "dados", "cloud", "devops", "ia", "banco")


@dataclass
class Vaga:
    id: str
    titulo: str
    empresa: Optional[str]
    url: str
    fonte: str
    local: Optional[str] = None
    remota: Optional[bool] = None
    publicada_em: Optional[str] = None
    descricao: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------


def texto_puro(bruto: str) -> str:
    """HTML de descrição de vaga para texto corrido."""
    sem_tags = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", bruto or "", flags=re.I)
    sem_tags = re.sub(r"<[^>]+>", " ", sem_tags)
    return re.sub(r"[ \t]{2,}", " ", html.unescape(sem_tags)).strip()


def _normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    sem_ponto_final = re.sub(r"\.(?![a-z0-9])", " ", sem_acento)
    return f" {re.sub(r'[^a-z0-9#+.]+', ' ', sem_ponto_final)} "


# Palavras comuns que também são nome ou apelido de tecnologia. Nelas, só vale
# o NOME escrito como a tecnologia se escreve ("REST", "Express", "Swift") —
# "the rest of the team" não é requisito de API REST. Apelidos ambíguos
# ("next", "pipeline", "test") simplesmente não contam.
_AMBIGUAS = {
    "rest", "express", "next", "swift", "spark", "rails", "flask", "go", "oracle", "jest",
    "vite", "pipeline", "test", "testes", "shell", "sh", "er", "ml", "iac", "pg", "c",
    "spring", "arquitetura", "modelagem", "security", "agile", "agil", "elastic", "rabbit",
}


def tags_citadas(texto: str, catalogo: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """As tags do catálogo que o texto cita, por slug.

    Casa por palavra inteira ("Java" não acende em "JavaScript"), sem acento e
    sem caixa — menos nas palavras ambíguas, que exigem a grafia da tecnologia.
    """
    alvo = _normaliza(texto)
    original = f" {texto} "
    achadas: dict[str, dict[str, Any]] = {}
    for tag in catalogo:
        nome = str(tag.get("name") or "")
        chaves = [(nome, True)] + [(str(a), False) for a in (tag.get("aliases") or []) if a]
        for escrita, e_nome in chaves:
            chave = _normaliza(escrita).strip()
            if not chave or (len(chave) < 3 and chave.isalnum() and chave not in _AMBIGUAS):
                continue
            if chave in _AMBIGUAS:
                if e_nome and re.search(rf"(?<![\w.#+]){re.escape(nome)}(?![\w#+])", original):
                    achadas[str(tag["slug"])] = tag
                    break
                continue
            if f" {chave} " in alvo:
                achadas[str(tag["slug"])] = tag
                break
    return achadas


# ---------------------------------------------------------------------------
# Compatibilidade
# ---------------------------------------------------------------------------

# 0 é "quero aprender"; de 2 para cima a pessoa já trabalha com aquilo.
_DOMINA = 2


def situacao(slug: str, minhas: dict[str, dict[str, Any]]) -> str:
    tag = minhas.get(slug)
    if not tag:
        return "falta"
    nivel = int(tag.get("proficiency") or 0)
    return "tem" if nivel >= _DOMINA else ("parcial" if nivel == 1 else "falta")


def compatibilidade(
    requisitos: Iterable[tuple[str, str, bool]], minhas: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """`requisitos` = (slug, nome, obrigatório). Obrigatório pesa o dobro."""
    tem, parcial, falta = [], [], []
    pontos = total = 0.0
    for slug, nome, obrigatorio in requisitos:
        peso = 2.0 if obrigatorio else 1.0
        estado = situacao(slug, minhas)
        total += peso
        if estado == "tem":
            tem.append(nome)
            pontos += peso
        elif estado == "parcial":
            parcial.append(nome)
            pontos += peso / 2
        else:
            falta.append(nome)
    return {
        "nota": round(100 * pontos / total) if total else None,
        "tem": tem,
        "parcial": parcial,
        "falta": falta,
    }


def termos_de_busca(minhas: Iterable[dict[str, Any]], objetivo: str = "") -> list[str]:
    """Até três tecnologias que descrevem o que a pessoa faz ou quer fazer.

    Metas primeiro, depois o que ela mais domina. Sem nenhuma tag de stack, o
    próprio objetivo vira o termo.
    """
    candidatas = [t for t in minhas if t.get("category") in _CATEGORIAS_DE_BUSCA]
    candidatas.sort(key=lambda t: (not t.get("is_target"), -int(t.get("proficiency") or 0), t.get("name") or ""))
    termos: list[str] = []
    for tag in candidatas:
        nome = str(tag.get("name") or "").strip()
        if nome and nome not in termos:
            termos.append(nome)
        if len(termos) == 3:
            break
    if not termos and objetivo.strip():
        termos.append(objetivo.strip()[:60])
    return termos


_NIVEIS_NO_TITULO = {
    "junior": re.compile(r"j[uú]nior|\bjr\b|trainee|est[aá]gi", re.I),
    "pleno": re.compile(r"\bpleno\b|\bpl\b|mid[- ]level", re.I),
    "senior": re.compile(r"s[eê]nior|\bsr\b|especialista|staff|principal|l[ií]der|\blead\b", re.I),
}


def nivel_do_titulo(titulo: str) -> Optional[str]:
    for nivel, padrao in _NIVEIS_NO_TITULO.items():
        if padrao.search(titulo):
            return nivel
    return None


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

_cache: dict[tuple[str, str], tuple[float, list[Vaga]]] = {}
# As vagas vistas por id, para a análise não precisar buscar a descrição de novo.
_por_id: dict[str, Vaga] = {}


def limpar_cache() -> None:
    _cache.clear()
    _por_id.clear()


def vaga_guardada(vaga_id: str) -> Optional[Vaga]:
    return _por_id.get(vaga_id)


async def _com_cache(fonte: str, termo: str, buscar: Callable[[str], Awaitable[list[Vaga]]]) -> list[Vaga]:
    chave = (fonte, termo.lower())
    guardado = _cache.get(chave)
    if guardado and time.monotonic() - guardado[0] < _VALIDADE_S[fonte]:
        return guardado[1]
    vagas = await buscar(termo)
    _cache[chave] = (time.monotonic(), vagas)
    for vaga in vagas:
        _por_id[vaga.id] = vaga
    return vagas


async def _gupy(termo: str) -> list[Vaga]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        resposta = await cliente.get(GUPY, params={"jobName": termo, "limit": 30})
    resposta.raise_for_status()
    vagas = []
    for item in resposta.json().get("data") or []:
        # O portal da Gupy mistura vagas da América Latina inteira.
        if str(item.get("country") or "Brasil") != "Brasil":
            continue
        remota =item.get("workplaceType") == "remote" or bool(item.get("isRemoteWork"))
        lugar = " - ".join(p for p in (item.get("city"), item.get("state")) if p)
        vagas.append(
            Vaga(
                id=f"gupy:{item['id']}",
                titulo=str(item.get("name") or "").strip(),
                empresa=item.get("careerPageName"),
                url=str(item.get("jobUrl") or ""),
                fonte="Gupy",
                local="Remoto" if remota else (lugar or item.get("country")),
                remota=remota,
                publicada_em=item.get("publishedDate"),
                descricao=texto_puro(str(item.get("description") or "")),
                extra={"estado": item.get("state")},
            )
        )
    return [v for v in vagas if v.titulo and v.url]


async def _remotive(termo: str) -> list[Vaga]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        resposta = await cliente.get(REMOTIVE, params={"search": termo, "limit": 30})
    resposta.raise_for_status()
    vagas = []
    for item in resposta.json().get("jobs") or []:
        local = str(item.get("candidate_required_location") or "")
        if local and not _LOCAL_QUE_ACEITA_BRASIL.search(local):
            continue
        vagas.append(
            Vaga(
                id=f"remotive:{item['id']}",
                titulo=str(item.get("title") or "").strip(),
                empresa=item.get("company_name"),
                url=str(item.get("url") or ""),
                fonte="Remotive",
                local=f"Remoto · {local}" if local else "Remoto",
                remota=True,
                publicada_em=item.get("publication_date"),
                descricao=texto_puro(str(item.get("description") or "")),
            )
        )
    return [v for v in vagas if v.titulo and v.url]


async def _adzuna(termo: str) -> list[Vaga]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        resposta = await cliente.get(
            ADZUNA,
            params={
                "app_id": settings.adzuna_app_id.strip(),
                "app_key": settings.adzuna_app_key.strip(),
                "what": termo,
                "results_per_page": 30,
                "content-type": "application/json",
            },
        )
    resposta.raise_for_status()
    vagas = []
    for item in resposta.json().get("results") or []:
        vagas.append(
            Vaga(
                id=f"adzuna:{item.get('id')}",
                titulo=texto_puro(str(item.get("title") or "")),
                empresa=(item.get("company") or {}).get("display_name"),
                url=str(item.get("redirect_url") or ""),
                fonte="Adzuna",
                local=(item.get("location") or {}).get("display_name"),
                remota=None,
                publicada_em=item.get("created"),
                # A Adzuna devolve só um trecho da descrição; a análise
                # completa lê a página.
                descricao=texto_puro(str(item.get("description") or "")),
            )
        )
    return [v for v in vagas if v.titulo and v.url]


_TITULO_DE_LISTAGEM = re.compile(r"^\s*[\d.]+\s+vagas?\b|\bvaga\(s\)|\bjobs?\s+(?:in|em)\b", re.I)


def site_de_vaga(url: str) -> Optional[str]:
    """O site confiável a que o endereço pertence, se ele for de UMA vaga."""
    partes = urlparse(url)
    host = (partes.hostname or "").lower()
    caminho = f"{partes.path}?{partes.query}"
    for dominio, padrao in SITES_DE_VAGA.items():
        if (host == dominio or host.endswith(f".{dominio}")) and padrao.search(caminho):
            return dominio
    return None


async def _busca_em_sites(termo: str) -> list[Vaga]:
    consulta = f"vaga {termo} Brasil"
    resultados: list[tuple[str, str, str]] = []  # (url, título, trecho)
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:
        if settings.tavily_api_key.strip():
            resposta = await cliente.post(
                TAVILY,
                json={
                    "api_key": settings.tavily_api_key.strip(),
                    "query": consulta,
                    "max_results": 15,
                    "search_depth": "basic",
                    "include_domains": list(SITES_DE_VAGA),
                },
            )
            resposta.raise_for_status()
            for item in resposta.json().get("results") or []:
                resultados.append((str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("content") or "")))
        elif settings.brave_api_key.strip():
            sites = " OR ".join(f"site:{d}" for d in SITES_DE_VAGA)
            resposta = await cliente.get(
                BRAVE,
                params={"q": f"{consulta} ({sites})", "count": 20},
                headers={"X-Subscription-Token": settings.brave_api_key.strip(), "Accept": "application/json"},
            )
            resposta.raise_for_status()
            for item in ((resposta.json().get("web") or {}).get("results")) or []:
                resultados.append((str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("description") or "")))

    vagas = []
    for url, titulo, trecho in resultados:
        dominio = site_de_vaga(url)
        # O título denuncia a listagem que o endereço não denunciou.
        if not dominio or _TITULO_DE_LISTAGEM.search(titulo):
            continue
        vagas.append(
            Vaga(
                id="busca:" + hashlib.sha1(url.encode()).hexdigest()[:16],
                titulo=texto_puro(titulo).split(" | ")[0].strip() or url,
                empresa=None,
                url=url,
                fonte=NOME_DO_SITE[dominio],
                descricao=texto_puro(trecho),
                extra={"so_link": True},
            )
        )
    return vagas


def fontes_disponiveis() -> dict[str, bool]:
    return {
        "gupy": True,
        "remotive": True,
        "adzuna": bool(settings.adzuna_app_id.strip() and settings.adzuna_app_key.strip()),
        "busca": bool(settings.tavily_api_key.strip() or settings.brave_api_key.strip()),
    }


def _buscador(fonte: str) -> Callable[[str], Awaitable[list[Vaga]]]:
    # Resolvido na hora da chamada, e não num dicionário no import: é o que
    # deixa o teste trocar uma fonte sem tocar a rede.
    return {"gupy": _gupy, "remotive": _remotive, "adzuna": _adzuna, "busca": _busca_em_sites}[fonte]


async def buscar(termos: list[str]) -> tuple[list[Vaga], dict[str, str]]:
    """Todas as fontes, todos os termos, ao mesmo tempo. Uma fonte fora do ar
    não derruba as outras: o estado de cada uma volta para a tela."""
    disponiveis = fontes_disponiveis()
    estado: dict[str, str] = {nome: ("ok" if ativa else "sem_chave") for nome, ativa in disponiveis.items()}
    pedidos = [(fonte, termo) for fonte, ativa in disponiveis.items() if ativa for termo in termos]
    respostas = await asyncio.gather(
        *(_com_cache(fonte, termo, _buscador(fonte)) for fonte, termo in pedidos),
        return_exceptions=True,
    )

    vistas: set[tuple[str, str]] = set()
    vagas: list[Vaga] = []
    for (fonte, _), resposta in zip(pedidos, respostas):
        if isinstance(resposta, BaseException):
            logger.warning("fonte de vagas %s falhou: %s", fonte, resposta)
            estado[fonte] = "erro"
            continue
        for vaga in resposta:
            # A mesma vaga aparece por dois termos ("Java" e "Spring Boot") e
            # às vezes em duas fontes.
            chave = (_normaliza(vaga.titulo).strip(), _normaliza(vaga.empresa or "").strip() or vaga.url)
            if chave in vistas:
                continue
            vistas.add(chave)
            vagas.append(vaga)
    return vagas, estado


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------


def _dias_desde(quando: Optional[str], agora: Optional[datetime] = None) -> Optional[int]:
    if not quando:
        return None
    try:
        data = datetime.fromisoformat(quando.replace("Z", "+00:00"))
    except ValueError:
        return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return max(0, ((agora or datetime.now(timezone.utc)) - data).days)


def para_tela(
    vagas: list[Vaga],
    catalogo: list[dict[str, Any]],
    minhas: dict[str, dict[str, Any]],
    senioridade: Optional[str] = None,
    estado_uf: Optional[str] = None,
    so_remotas: bool = False,
    limite: int = 60,
) -> list[dict[str, Any]]:
    linhas = []
    for vaga in vagas:
        if so_remotas and vaga.remota is not True:
            continue
        so_link = bool(vaga.extra.get("so_link"))
        # Resultado de busca traz só o trecho do buscador. Uma nota tirada dali
        # diria "100%" para uma vaga cujo anúncio ninguém leu.
        citadas = {} if so_link else tags_citadas(f"{vaga.titulo}\n{vaga.descricao}", catalogo)
        compat = compatibilidade(((s, t["name"], True) for s, t in citadas.items()), minhas)
        nivel = nivel_do_titulo(vaga.titulo)
        regiao = bool(estado_uf and (vaga.extra.get("estado") or "").upper() == estado_uf.upper())
        # Ordem: compatibilidade manda; nível certo, região e vaga recente
        # desempatam. Vaga só-link (sem descrição lida) vai para o fim.
        pontos = compat["nota"] if compat["nota"] is not None else -50
        if senioridade and nivel:
            pontos += 10 if nivel == senioridade else -15
        if regiao or vaga.remota:
            pontos += 5
        dias = _dias_desde(vaga.publicada_em)
        if dias is not None and dias > 30:
            pontos -= 10
        linhas.append(
            (
                pontos,
                {
                    "id": vaga.id,
                    "titulo": vaga.titulo,
                    "empresa": vaga.empresa,
                    "url": vaga.url,
                    "fonte": vaga.fonte,
                    "local": vaga.local,
                    "remota": vaga.remota,
                    "publicada_ha_dias": dias,
                    "nivel": nivel,
                    "na_sua_regiao": regiao,
                    "so_link": so_link,
                    "resumo": vaga.descricao[:280] or None,
                    "compatibilidade": compat,
                },
            )
        )
    linhas.sort(key=lambda par: -par[0])
    return [linha for _, linha in linhas[:limite]]


# ---------------------------------------------------------------------------
# Análise de uma vaga
# ---------------------------------------------------------------------------

ANALISE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "empresa": {"type": "STRING"},
        "senioridade": {"type": "STRING"},
        "resumo": {"type": "STRING"},
        "requisitos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"nome": {"type": "STRING"}, "obrigatorio": {"type": "BOOLEAN"}},
                "required": ["nome", "obrigatorio"],
            },
        },
    },
    "required": ["titulo", "requisitos"],
}

ANALISE_SYSTEM = "Você lê anúncios de vaga de tecnologia e extrai os requisitos. Responda só JSON."


def pedido_de_analise(texto: str) -> str:
    return (
        "Extraia deste anúncio de vaga:\n"
        "- titulo e empresa (vazio se não disser);\n"
        "- senioridade: junior, pleno, senior ou vazio;\n"
        "- resumo: uma frase em português do que a pessoa vai fazer;\n"
        "- requisitos: TECNOLOGIAS, ferramentas, práticas e idiomas pedidos, cada um com "
        "`obrigatorio` = true quando está em requisitos/obrigatório e false quando é "
        "diferencial/desejável/plus. Use o nome usual da tecnologia (\"Spring Boot\", "
        "\"PostgreSQL\", \"Inglês\"), um por item, no máximo 20. Não invente requisito que "
        "o anúncio não cita; soft skills ficam de fora.\n\n"
        f"ANÚNCIO:\n{texto[:12000]}"
    )


def _curso_resumido(curso: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": curso["id"],
        "titulo": curso["titulo"],
        "emissor": curso["emissor"],
        "url": curso["url"],
        "gratuito": curso["certificado"]["gratuito"],
    }


def analisar(
    requisitos_brutos: list[dict[str, Any]],
    texto: str,
    catalogo: list[dict[str, Any]],
    achar: Callable[[str], Optional[dict[str, Any]]],
    minhas: dict[str, dict[str, Any]],
    slugs_do_roadmap: set[str],
) -> dict[str, Any]:
    """Os requisitos da vaga contra o que a pessoa sabe, e o caminho para cada lacuna.

    `requisitos_brutos` vem da IA; vazio (IA fora), cai no casamento de tags
    do texto, com todos contando como obrigatórios — melhor cobrar a mais do
    que esconder uma lacuna.
    """
    requisitos: list[dict[str, Any]] = []
    vistos: set[str] = set()

    def acrescenta(nome: str, obrigatorio: bool, tag: Optional[dict[str, Any]]) -> None:
        chave = str(tag["slug"]) if tag else _normaliza(nome).strip()
        if not chave or chave in vistos:
            return
        vistos.add(chave)
        requisitos.append({"nome": tag["name"] if tag else nome, "obrigatorio": obrigatorio, "tag": tag})

    for bruto in requisitos_brutos:
        nome = str(bruto.get("nome") or "").strip()
        if not nome:
            continue
        tag = achar(nome) or next(iter(tags_citadas(nome, catalogo).values()), None)
        acrescenta(nome, bool(bruto.get("obrigatorio", True)), tag)
    if not requisitos:
        for tag in tags_citadas(texto, catalogo).values():
            acrescenta(str(tag["name"]), True, tag)

    avaliados = []
    lacunas = []
    for req in requisitos:
        tag = req["tag"]
        slug = str(tag["slug"]) if tag else None
        estado = situacao(slug, minhas) if slug else "desconhecido"
        minha = minhas.get(slug) if slug else None
        item = {
            "nome": req["nome"],
            "obrigatorio": req["obrigatorio"],
            "situacao": estado,
            "tag_id": str(tag["id"]) if tag and tag.get("id") else None,
            "user_tag_id": str(minha["id"]) if minha and minha.get("id") else None,
            "e_meta": bool(minha and minha.get("is_target")),
        }
        avaliados.append(item)
        if estado in ("falta", "parcial"):
            sugeridos = courses.recomendar([{"slug": slug, "name": req["nome"], "is_target": True}])
            lacunas.append(
                {
                    **item,
                    "no_roadmap": slug in slugs_do_roadmap,
                    "cursos": [_curso_resumido(c) for c in sugeridos[:3]],
                }
            )

    compat = compatibilidade(
        ((str(r["tag"]["slug"]), r["nome"], r["obrigatorio"]) for r in requisitos if r["tag"]), minhas
    )
    # Obrigatório primeiro: é o que barra a candidatura.
    lacunas.sort(key=lambda l: (not l["obrigatorio"], l["situacao"] != "falta", l["nome"]))
    return {"requisitos": avaliados, "lacunas": lacunas, "nota": compat["nota"]}
