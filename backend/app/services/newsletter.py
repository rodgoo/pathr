"""Newsletter do admin: notícias reais de tecnologia, por tema, no e-mail dele.

## O que é um "tópico"

Duas partes, e as duas se acumulam:

- **tecnologias** (`topics`): linguagens e assuntos — Python, Rust, Kubernetes,
  "inteligência artificial". Texto livre, até `MAX_TEMAS`;
- **ângulos** (`angles`): o que ele quer saber sobre cada uma — `noticias`
  (em geral), `novidades` (lançamentos), `trabalhos` (vagas e mercado) e
  `polemicas` (controvérsias).

A busca é o produto das duas listas: Rust + novidades + trabalhos são duas
combinações. O teto é `MAX_CONSULTAS`, porque cada busca vai a duas fontes e a
cota de Tavily/Brave é de todo o app.

## Ecossistema, e não a palavra pura

"Java + Empregos" não procura só "Java vagas": a vaga que o admin quer ver
diz Spring Boot, Kotlin, JVM, Quarkus. Cada tecnologia se expande em alguns
termos do ecossistema (mapa curado abaixo; para texto livre, a IA propõe
TERMOS DE BUSCA — nunca conteúdo —, com cache), e cada termo faz a própria
busca com o mesmo ângulo. As matérias de uma combinação são intercaladas entre
os termos, para os dois primeiros itens de "Java + Empregos" não serem ambos
do termo "Java". O item guarda por qual termo veio (`termo`) e o e-mail diz.

O custo é contido por um orçamento de `MAX_BUSCAS` por edição, gasto em
camadas: primeiro a busca base de TODAS as combinações, depois o 1º termo do
ecossistema de cada uma, e assim por diante. Estourou, o resto fica de fora —
e nenhuma combinação perde a busca base.

## De onde vem o conteúdo

De busca de NOTÍCIAS na web, e de nada mais: Tavily (`topic: "news"`) e Brave
News. Cada item é o que a fonte devolveu — título, link, veículo e o trecho
que ela mesma publicou. A IA não escreve, não resume e não reordena nada
aqui: um resumo gerado sobre um trecho de busca é onde nasce o fato que a
matéria não diz, e esta é uma newsletter, não um exercício de estilo. Sem
nenhuma chave de busca configurada a edição sai vazia — e vazia não é enviada.

## Quando sai

O admin escolhe a frequência e o horário (no fuso dele):

- `diaria`, `dias_uteis` e `fim_de_semana` são atalhos para um conjunto de
  dias da semana;
- `semanal` e `personalizada` usam os dias que ele marcou (0 = segunda);
- `mensal` usa um dia do mês de 1 a 28 — 29, 30 e 31 não existem em todo mês,
  e a edição pularia meses.

Quem chama é o cron horário (routers/newsletter.py). A decisão é "o horário
já passou hoje e a edição de hoje ainda não saiu", e não "agora é exatamente
8h": um disparo atrasado ou uma máquina que acordou tarde ainda entrega.

## O que não se repete

`last_sent_on` trava a segunda edição do mesmo dia. Link que já saiu numa
edição recente não volta, nem aparece duas vezes na mesma edição. E quando a
busca não acha nada novo, `last_attempt_at` segura as próximas tentativas por
algumas horas, para um dia seco não virar uma busca por hora na cota.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from supabase import Client

from app.config import settings
from app.services import email as emails
from app.services import evento_da_pagina
from app.services import saida as saida_http

logger = logging.getLogger("pathr.newsletter")

TAVILY = "https://api.tavily.com/search"
BRAVE_NEWS = "https://api.search.brave.com/res/v1/news/search"

_TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_TIMEOUT_FOTO = httpx.Timeout(7.0, connect=4.0)
_UA = f"PathR/1.0 (+{settings.frontend_url})"
_CONCORRENCIA = 4
_CONCORRENCIA_FOTOS = 6
MAX_FOTOS_DA_PAGINA = 30

FREQUENCIAS = ("diaria", "dias_uteis", "fim_de_semana", "semanal", "mensal", "personalizada")
_DIAS_DO_ATALHO: dict[str, tuple[int, ...]] = {
    "diaria": (0, 1, 2, 3, 4, 5, 6),
    "dias_uteis": (0, 1, 2, 3, 4),
    "fim_de_semana": (5, 6),
}

# O ângulo vira palavras de busca. Em português E em inglês de propósito: a
# notícia de tecnologia nasce, na maior parte, em inglês, e uma busca só em
# português devolveria a metade do que existe.
ANGULOS: dict[str, dict[str, str]] = {
    "noticias": {"rotulo": "Notícias", "busca": ""},
    "novidades": {"rotulo": "Novidades", "busca": "novidades lançamento release"},
    "trabalhos": {"rotulo": "Empregos", "busca": "vagas emprego mercado de trabalho hiring jobs"},
    "polemicas": {"rotulo": "Polêmicas", "busca": "polêmica controvérsia criticism controversy"},
}
ANGULO_PADRAO = "noticias"

MAX_TEMAS = 8
MAX_CONSULTAS = 24
MAX_ITENS_POR_CONSULTA = 5
# Orçamento de buscas por edição (cada uma vai a Tavily E Brave) e quantos
# termos do ecossistema cada combinação pode gastar dele.
MAX_BUSCAS = 40
ECOSSISTEMA_POR_COMBINACAO = 3

# O ecossistema de cada tecnologia: o que aparece nas vagas e nas notícias ao
# lado do nome dela. Curado à mão porque é o que decide a qualidade da busca —
# e para o que não está aqui a IA propõe os termos (`expandir_ecossistema`).
# Chaves em minúsculas; sem termo ambíguo sozinho ("Rails", "Go").
ECOSSISTEMAS: dict[str, tuple[str, ...]] = {
    "java": ("Spring Boot", "JVM", "Kotlin", "Quarkus", "Jakarta EE", "Hibernate"),
    "kotlin": ("Android", "Jetpack Compose", "Ktor", "Spring Boot"),
    "python": ("Django", "FastAPI", "pandas", "PyTorch", "Flask"),
    "javascript": ("Node.js", "React", "TypeScript", "Vue.js", "Next.js"),
    "typescript": ("Node.js", "React", "Angular", "Next.js", "Deno"),
    "node": ("Node.js", "NestJS", "Express", "Bun", "Deno"),
    "react": ("Next.js", "React Native", "Redux", "Vite"),
    "angular": ("RxJS", "NgRx", "TypeScript", "Nx"),
    "vue": ("Nuxt", "Pinia", "Vite", "TypeScript"),
    "c#": (".NET", "ASP.NET Core", "Azure", "Blazor", "Entity Framework"),
    ".net": ("ASP.NET Core", "C#", "Azure", "Blazor"),
    "go": ("Golang", "Kubernetes", "gRPC", "microsserviços"),
    "golang": ("Kubernetes", "gRPC", "microsserviços", "Docker"),
    "rust": ("Cargo", "Tokio", "WebAssembly", "Rust embarcado"),
    "php": ("Laravel", "Symfony", "WordPress", "Composer"),
    "ruby": ("Ruby on Rails", "Hotwire", "Sidekiq"),
    "swift": ("SwiftUI", "iOS", "Xcode", "Combine"),
    "c++": ("CMake", "Qt", "Unreal Engine", "C++20"),
    "sql": ("PostgreSQL", "MySQL", "SQL Server", "dados analytics"),
    "postgres": ("PostgreSQL", "Supabase", "pgvector", "banco de dados"),
    "docker": ("Kubernetes", "containers", "Docker Compose", "Podman"),
    "kubernetes": ("Docker", "Helm", "Istio", "Terraform", "platform engineering"),
    "devops": ("CI/CD", "Terraform", "Kubernetes", "GitHub Actions", "SRE"),
    "aws": ("Lambda", "EKS", "S3", "Terraform", "cloud"),
    "azure": ("Azure DevOps", "AKS", ".NET", "cloud"),
    "ia": ("LLM", "OpenAI", "machine learning", "agentes de IA", "RAG"),
    "inteligência artificial": ("LLM", "OpenAI", "machine learning", "agentes de IA", "RAG"),
    "machine learning": ("PyTorch", "TensorFlow", "MLOps", "LLM"),
    "segurança": ("cibersegurança", "OWASP", "vulnerabilidades CVE", "DevSecOps"),
    "dados": ("engenharia de dados", "Spark", "dbt", "Airflow", "data warehouse"),
}
# O nome com que o tema vai à busca quando a palavra pura é ambígua.
_APELIDO_NA_BUSCA = {"go": "Golang", "c": "linguagem C", "r": "linguagem R", "node": "Node.js", "ia": "inteligência artificial"}

_cache_ecossistema: dict[str, tuple[str, ...]] = {}
# Quanto tempo uma busca que não achou nada novo segura a próxima tentativa.
_ESPERA_APOS_VAZIA = timedelta(hours=3)
# Quantas edições para trás entram na lista de "já enviado".
_EDICOES_LIDAS = 40
_TRECHO_MAX = 280

PADRAO: dict[str, Any] = {
    "enabled": False,
    "topics": [],
    "angles": [ANGULO_PADRAO],
    "frequency": "semanal",
    "weekdays": [0],
    "month_day": 1,
    "send_hour": 8,
    "items_per_topic": 2,
    "last_sent_on": None,
    "last_attempt_at": None,
}


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------


def dias_da_semana(config: dict[str, Any]) -> set[int]:
    """Os dias da semana (0 = segunda) em que a edição sai. `mensal` não usa."""
    frequencia = config.get("frequency")
    if frequencia in _DIAS_DO_ATALHO:
        return set(_DIAS_DO_ATALHO[frequencia])
    return {int(d) for d in (config.get("weekdays") or []) if str(d).isdigit() and 0 <= int(d) <= 6}


def e_dia_de_envio(config: dict[str, Any], dia: date) -> bool:
    if config.get("frequency") == "mensal":
        return dia.day == int(config.get("month_day") or 1)
    return dia.weekday() in dias_da_semana(config)


def _como_data(valor: Any) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _como_instante(valor: Any) -> Optional[datetime]:
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    try:
        instante = datetime.fromisoformat(str(valor).replace("Z", "+00:00")) if valor else None
    except ValueError:
        return None
    if instante and not instante.tzinfo:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante


def esta_devida(config: dict[str, Any], agora_local: datetime, agora_utc: datetime) -> bool:
    """A edição programada deve sair agora?

    Hora: `>=` e não `==`, pelo motivo do cabeçalho. A trava é a edição do dia
    (`last_sent_on`), não o relógio.
    """
    if not config.get("enabled") or not config.get("topics"):
        return False
    if not e_dia_de_envio(config, agora_local.date()):
        return False
    if agora_local.hour < int(config.get("send_hour") or 0):
        return False
    if _como_data(config.get("last_sent_on")) == agora_local.date():
        return False
    ultima = _como_instante(config.get("last_attempt_at"))
    if ultima and agora_utc - ultima < _ESPERA_APOS_VAZIA:
        return False
    return True


def proximo_envio(config: dict[str, Any], agora_local: datetime) -> Optional[date]:
    """O próximo dia de envio, a partir de hoje — para a tela dizer "próxima: ter, 14/10"."""
    if not config.get("enabled") or not config.get("topics"):
        return None
    ja_saiu_hoje = _como_data(config.get("last_sent_on")) == agora_local.date()
    passou_da_hora = agora_local.hour >= int(config.get("send_hour") or 0)
    inicio = agora_local.date() + timedelta(days=1 if (ja_saiu_hoje or passou_da_hora) else 0)
    for passo in range(0, 62):
        dia = inicio + timedelta(days=passo)
        if e_dia_de_envio(config, dia):
            return dia
    return None


def fuso_do(user: dict[str, Any]) -> ZoneInfo:
    try:
        return ZoneInfo(str(user.get("timezone_name") or "America/Sao_Paulo"))
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Sao_Paulo")


def janela_em_dias(config: dict[str, Any], hoje: date) -> int:
    """Quantos dias para trás a busca olha: desde a última edição, com um dia
    de folga, entre 1 e 31. Sem edição anterior, uma edição "normal" do ritmo."""
    ultima = _como_data(config.get("last_sent_on"))
    if ultima:
        return max(1, min(31, (hoje - ultima).days + 1))
    return {"diaria": 2, "dias_uteis": 3, "fim_de_semana": 3, "mensal": 31}.get(
        str(config.get("frequency")), 7
    )


# ---------------------------------------------------------------------------
# Temas e ângulos
# ---------------------------------------------------------------------------


def fontes_configuradas() -> dict[str, bool]:
    return {"tavily": bool(settings.tavily_api_key.strip()), "brave": bool(settings.brave_api_key.strip())}


def normalizar_tema(tema: str) -> str:
    return re.sub(r"\s+", " ", str(tema or "")).strip()[:60]


def normalizar_temas(temas: list[str]) -> list[str]:
    """Sem vazio, sem repetido (ignorando caixa), na ordem dada, até o teto."""
    vistos: set[str] = set()
    saida: list[str] = []
    for tema in temas:
        limpo = normalizar_tema(tema)
        if limpo and limpo.lower() not in vistos:
            vistos.add(limpo.lower())
            saida.append(limpo)
    return saida[:MAX_TEMAS]


def normalizar_angulos(angulos: list[str]) -> list[str]:
    """Só os conhecidos, sem repetir, na ordem do catálogo. Vazio vira o padrão:
    um tema sem ângulo nenhum não buscaria nada."""
    escolhidos = {str(a) for a in angulos}
    ordenados = [a for a in ANGULOS if a in escolhidos]
    return ordenados or [ANGULO_PADRAO]


def consulta_para(tema: str, angulo: str) -> str:
    extra = ANGULOS.get(angulo, ANGULOS[ANGULO_PADRAO])["busca"]
    nome = _APELIDO_NA_BUSCA.get(tema.lower(), tema)
    return f"{nome} {extra}".strip()


def ecossistema_conhecido(tema: str) -> tuple[str, ...]:
    """Os termos que se sabe SEM chamar ninguém: o mapa curado, ou o que a IA
    já propôs nesta execução. Para a tela mostrar "inclui: Spring Boot, JVM…"."""
    chave = tema.lower()
    return ECOSSISTEMAS.get(chave) or _cache_ecossistema.get(chave, ())


_AI_SISTEMA_ECOSSISTEMA = """Você ajuda a montar BUSCAS de notícias e vagas de tecnologia.
Dado o nome de uma tecnologia, liste de 3 a 5 termos do ecossistema dela: os
frameworks, runtimes e ferramentas que aparecem ao lado do nome em vagas e
notícias. Cada termo precisa funcionar sozinho numa busca (sem ser uma palavra
comum ambígua). Responda só os termos; não explique nem descreva."""

_AI_SCHEMA_ECOSSISTEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {"termos": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["termos"],
}


async def expandir_ecossistema(tema: str) -> tuple[str, ...]:
    """O ecossistema de uma tecnologia que o mapa não conhece.

    A IA devolve TERMOS DE BUSCA e mais nada: o que ela diz não chega ao
    e-mail, só decide o que se procura. Falha (cota, rede, resposta torta) não
    é erro — a combinação segue só com a busca base. O resultado, mesmo vazio,
    fica em cache: a mesma tecnologia não gasta uma chamada por edição.
    """
    chave = tema.lower()
    conhecido = ecossistema_conhecido(tema)
    if conhecido or chave in _cache_ecossistema:
        return conhecido
    try:
        from app.ai_providers import generate_json

        resultado = await generate_json(
            _AI_SISTEMA_ECOSSISTEMA, f"Tecnologia: {tema}", _AI_SCHEMA_ECOSSISTEMA, traduzir_saida=False
        )
        brutos = (resultado.content or {}).get("termos") or []
    except Exception as exc:  # noqa: BLE001 — a cota diária chega como HTTPException 429
        logger.warning("ecossistema de %r indisponível: %s", tema, exc)
        return ()
    termos = tuple(
        dict.fromkeys(
            normalizar_tema(str(t)) for t in brutos if isinstance(t, str) and 2 <= len(normalizar_tema(str(t))) <= 40
        )
    )[:5]
    _cache_ecossistema[chave] = termos
    return termos


def quantas_consultas(temas: list[str], angulos: list[str]) -> int:
    return len(normalizar_temas(temas)) * len(normalizar_angulos(angulos))


def rotulo_da_combinacao(tema: str, angulo: str) -> str:
    """"<Tecnologia> + <Ângulo>" (ex.: "Java + Empregos"): o nome que a tela e a
    etiqueta do e-mail dão a uma busca."""
    return f"{tema} + {ANGULOS.get(angulo, ANGULOS[ANGULO_PADRAO])['rotulo']}"


def combinacoes(temas: list[str], angulos: list[str]) -> list[dict[str, Any]]:
    """Todas as combinações que a configuração dispara, na ordem em que rodam.
    É o que a tela mostra antes de salvar: o rótulo, a busca base e os termos
    do ecossistema que entram junto."""
    return [
        {
            "topico": t,
            "categoria": a,
            "rotulo": rotulo_da_combinacao(t, a),
            "consulta": consulta_para(t, a),
            "ecossistema": list(ecossistema_conhecido(t)[:ECOSSISTEMA_POR_COMBINACAO]),
        }
        for t in normalizar_temas(temas)
        for a in normalizar_angulos(angulos)
    ][:MAX_CONSULTAS]


# ---------------------------------------------------------------------------
# Busca de notícias
# ---------------------------------------------------------------------------


def chave_da_url(url: str) -> str:
    """O mesmo link, escrito de jeitos diferentes, vira uma chave só: sem
    fragmento, sem `utm_*`, sem barra no fim, host em minúsculas."""
    partes = urlparse(url.strip())
    consulta = urlencode(
        [(k, v) for k, v in parse_qsl(partes.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    )
    return urlunparse(
        (partes.scheme.lower(), partes.netloc.lower().removeprefix("www."), partes.path.rstrip("/"), "", consulta, "")
    )


def _url_valida(url: str) -> bool:
    partes = urlparse(url)
    return partes.scheme in ("http", "https") and bool(partes.netloc)


def _limpar_trecho(texto: str) -> str:
    """Tira tag e entidade do trecho da busca e corta numa palavra inteira."""
    limpo = html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) <= _TRECHO_MAX:
        return limpo
    return limpo[:_TRECHO_MAX].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"


def _veiculo(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def _data_iso(valor: Any) -> Optional[str]:
    if not valor:
        return None
    texto = str(valor)
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(texto).date().isoformat()
    except (TypeError, ValueError):
        return None


def _imagem_valida(valor: Any) -> Optional[str]:
    """A foto da matéria: só https. `http` é bloqueado por boa parte dos
    clientes de e-mail e, na tela, viraria conteúdo misto; `data:` e o resto
    não são endereço de foto de notícia."""
    endereco = str(valor or "").strip()
    partes = urlparse(endereco)
    if partes.scheme != "https" or not partes.netloc or len(endereco) > 1000:
        return None
    return endereco


def _item(
    tema: str,
    angulo: str,
    termo: str,
    titulo: Any,
    url: Any,
    trecho: Any,
    publicado: Any,
    imagem: Any = None,
) -> Optional[dict[str, Any]]:
    titulo = re.sub(r"\s+", " ", html.unescape(str(titulo or ""))).strip()
    url = str(url or "").strip()
    if not titulo or not _url_valida(url):
        return None
    return {
        "titulo": titulo[:240],
        "url": url,
        "fonte": _veiculo(url),
        "resumo": _limpar_trecho(str(trecho or "")),
        "imagem": _imagem_valida(imagem),
        "publicado_em": _data_iso(publicado),
        "topico": tema,
        "categoria": angulo,
        # Por qual termo do ecossistema a busca achou ("Spring Boot" para uma
        # matéria de "Java + Empregos"). Igual ao tema quando veio da busca base.
        "termo": termo,
    }


async def _tavily(cliente: httpx.AsyncClient, consulta: str, dias: int) -> list[tuple[Any, ...]]:
    if not settings.tavily_api_key.strip():
        return []
    resposta = await cliente.post(
        TAVILY,
        json={
            "api_key": settings.tavily_api_key.strip(),
            "query": consulta,
            "topic": "news",
            "days": dias,
            "max_results": 10,
            "search_depth": "basic",
        },
    )
    resposta.raise_for_status()
    return [
        (r.get("title"), r.get("url"), r.get("content"), r.get("published_date"))
        for r in (resposta.json().get("results") or [])
    ]


def _freshness(dias: int) -> str:
    return "pd" if dias <= 1 else "pw" if dias <= 7 else "pm"


async def _brave(cliente: httpx.AsyncClient, consulta: str, dias: int) -> list[tuple[Any, ...]]:
    if not settings.brave_api_key.strip():
        return []
    resposta = await cliente.get(
        BRAVE_NEWS,
        params={"q": consulta, "count": 15, "freshness": _freshness(dias)},
        headers={"X-Subscription-Token": settings.brave_api_key.strip(), "Accept": "application/json"},
    )
    resposta.raise_for_status()
    return [
        (
            r.get("title"),
            r.get("url"),
            r.get("description"),
            r.get("page_age"),
            # O Brave News entrega a miniatura junto; o Tavily não — para as
            # dele a foto vem da própria página (`_imagem_da_pagina`).
            (r.get("thumbnail") or {}).get("src"),
        )
        for r in (resposta.json().get("results") or [])
    ]


async def buscar_consulta(
    cliente: httpx.AsyncClient, tema: str, angulo: str, termo: str, dias: int
) -> list[dict[str, Any]]:
    """O que as duas fontes acharam para um termo + ângulo, sem repetir link.

    `termo` é o próprio tema (busca base) ou um termo do ecossistema dele; o
    item sai sempre sob o `tema`, que é o que o admin escolheu.

    Uma fonte fora do ar não derruba a outra, nem as demais buscas: falha vira
    aviso no log e a edição sai com o que veio.
    """
    consulta = consulta_para(termo, angulo)
    achados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for fonte in (_tavily, _brave):
        try:
            resultado = await fonte(cliente, consulta, dias)
        except httpx.HTTPError as exc:
            logger.warning("busca de notícias falhou (%s, %r): %s", fonte.__name__, consulta, exc)
            continue
        for titulo, url, trecho, publicado, *resto in resultado:
            item = _item(tema, angulo, termo, titulo, url, trecho, publicado, resto[0] if resto else None)
            if item and chave_da_url(item["url"]) not in vistos:
                vistos.add(chave_da_url(item["url"]))
                achados.append(item)
    return achados


def urls_ja_enviadas(supabase: Client, user_id: str) -> set[str]:
    linhas = (
        supabase.table("pathr_newsletter_issue").select("items").eq("user_id", user_id)
        .order("created_at", desc=True).limit(_EDICOES_LIDAS).execute().data or []
    )
    return {
        chave_da_url(str(item.get("url") or ""))
        for linha in linhas
        for item in (linha.get("items") or [])
        if isinstance(item, dict) and item.get("url")
    }


async def procurar(
    temas: list[str],
    angulos: list[str],
    dias: int,
    ja_enviadas: set[str],
    por_consulta: int = 2,
) -> list[dict[str, Any]]:
    """Notícias de cada tema × ângulo, em profundidade pelo ecossistema, sem o
    que já foi enviado e sem o mesmo link duas vezes.

    Cada combinação ganha até `por_consulta` matérias, tiradas de TODAS as
    buscas dela (a base e os termos do ecossistema) em rodízio — a primeira
    de cada termo antes da segunda de qualquer um. O orçamento `MAX_BUSCAS` é
    gasto em camadas (ver o cabeçalho do módulo).
    """
    temas = normalizar_temas(temas)
    angulos = normalizar_angulos(angulos)
    por_consulta = max(1, min(MAX_ITENS_POR_CONSULTA, int(por_consulta)))
    pares = [(t, a) for t in temas for a in angulos][:MAX_CONSULTAS]

    # O ecossistema de cada tecnologia, uma vez por tecnologia (a IA, quando
    # entra, é por tema e não por par).
    ecossistema = {t: (await expandir_ecossistema(t))[:ECOSSISTEMA_POR_COMBINACAO] for t in temas}

    # Camadas: 0 = busca base de todos os pares; k = o k-ésimo termo do
    # ecossistema de cada par. O orçamento corta de trás para frente.
    buscas: list[tuple[str, str, str]] = []  # (tema, ângulo, termo)
    for camada in range(ECOSSISTEMA_POR_COMBINACAO + 1):
        for tema, angulo in pares:
            termo = tema if camada == 0 else (ecossistema[tema][camada - 1 : camada] or [None])[0]
            if termo and len(buscas) < MAX_BUSCAS:
                buscas.append((tema, angulo, termo))

    vez = asyncio.Semaphore(_CONCORRENCIA)

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as cliente:

        async def uma(tema: str, angulo: str, termo: str) -> list[dict[str, Any]]:
            async with vez:
                return await buscar_consulta(cliente, tema, angulo, termo, dias)

        resultados = await asyncio.gather(*(uma(*b) for b in buscas))

    por_par: dict[tuple[str, str], list[list[dict[str, Any]]]] = {}
    for (tema, angulo, _termo), itens in zip(buscas, resultados):
        por_par.setdefault((tema, angulo), []).append(itens)

    usados = set(ja_enviadas)
    saida: list[dict[str, Any]] = []
    for par in pares:
        listas = por_par.get(par, [])
        escolhidos = 0
        # Rodízio entre as buscas do par: base, termo 1, termo 2, base (2º)…
        for posicao in range(max((len(l) for l in listas), default=0)):
            for lista in listas:
                if posicao >= len(lista) or escolhidos >= por_consulta:
                    continue
                item = lista[posicao]
                chave = chave_da_url(item["url"])
                if chave in usados:
                    continue
                usados.add(chave)
                saida.append(item)
                escolhidos += 1
    await _completar_fotos(saida)
    return saida


async def _imagem_da_pagina(cliente: httpx.AsyncClient, url: str) -> Optional[str]:
    """A foto que a PRÓPRIA matéria declara (`og:image` ou JSON-LD).

    Passa por `saida.baixar`, a guarda anti-SSRF do app: o endereço veio de uma
    busca de terceiros, e pedi-lo direto deixaria quem controla a página fazer
    o servidor bater onde quiser. Falha de qualquer tipo é "sem foto" — a
    matéria sai igual, só que sem imagem.
    """
    try:
        pagina = await saida_http.baixar(cliente, url)
        if not pagina:
            return None
        return _imagem_valida(evento_da_pagina.extrair(pagina, url).imagem)
    except Exception as exc:  # noqa: BLE001
        logger.debug("sem foto para %s: %s", url, exc)
        return None


async def _completar_fotos(itens: list[dict[str, Any]]) -> None:
    """Foto para as matérias escolhidas que a busca não trouxe com ela.

    Só para as ESCOLHIDAS (no máximo `MAX_FOTOS_DA_PAGINA`), e não para todos
    os candidatos: uma edição são poucas dezenas de matérias, e cada foto é
    uma página baixada.
    """
    faltam = [i for i in itens if not i.get("imagem")][:MAX_FOTOS_DA_PAGINA]
    if not faltam:
        return
    vez = asyncio.Semaphore(_CONCORRENCIA_FOTOS)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT_FOTO, headers={"User-Agent": _UA}, follow_redirects=False
    ) as cliente:

        async def uma(item: dict[str, Any]) -> None:
            async with vez:
                item["imagem"] = await _imagem_da_pagina(cliente, item["url"])

        await asyncio.gather(*(uma(i) for i in faltam))


# ---------------------------------------------------------------------------
# Edição: montar, enviar, registrar
# ---------------------------------------------------------------------------


def _lista_em_texto(nomes: list[str]) -> str:
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def assunto_da_edicao(itens: list[dict[str, Any]]) -> str:
    """O assunto diz o que veio: "7 notícias: Rust, Kubernetes e IA"."""
    temas: list[str] = []
    for item in itens:
        if item["topico"] not in temas:
            temas.append(item["topico"])
    plural = "notícia" if len(itens) == 1 else "notícias"
    resto = len(temas) - 3
    nomes = temas[:3] + ([f"mais {resto}"] if resto > 0 else [])
    return f"{len(itens)} {plural}: {_lista_em_texto(nomes)}"


def agrupar(itens: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Por tecnologia, na ordem em que apareceram. O ângulo vai como etiqueta
    em cada item, e não como segundo nível: três títulos sob "Rust" leem
    melhor que três subtítulos com um título cada."""
    grupos: dict[str, list[dict[str, Any]]] = {}
    for item in itens:
        grupos.setdefault(item["topico"], []).append(item)
    return list(grupos.items())


def limpar_selecao(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Itens que o admin escolheu na tela, reduzidos ao formato da edição.

    Mesmo vindo do próprio admin o link vira botão num e-mail "do PathR":
    só http/https passa, e só os campos conhecidos.
    """
    saida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for bruto in itens:
        url = str(bruto.get("url") or "").strip()
        titulo = re.sub(r"\s+", " ", str(bruto.get("titulo") or "")).strip()
        if not titulo or not _url_valida(url) or chave_da_url(url) in vistos:
            continue
        vistos.add(chave_da_url(url))
        angulo = str(bruto.get("categoria") or "")
        saida.append(
            {
                "titulo": titulo[:240],
                "url": url,
                "fonte": str(bruto.get("fonte") or _veiculo(url))[:120],
                "resumo": _limpar_trecho(str(bruto.get("resumo") or "")),
                "imagem": _imagem_valida(bruto.get("imagem")),
                "publicado_em": _data_iso(bruto.get("publicado_em")),
                "topico": normalizar_tema(str(bruto.get("topico") or "")) or "Geral",
                "categoria": angulo if angulo in ANGULOS else ANGULO_PADRAO,
                "termo": normalizar_tema(str(bruto.get("termo") or "")),
            }
        )
    return saida


CHAVE_INTERRUPTOR = "newsletter_ativa"


def interruptor_ligado(supabase: Client) -> bool:
    """O botão geral da newsletter (painel de Operação), em `pathr_feature_flag`.

    Ligado por padrão: sem linha — ou com o banco fora do ar — a newsletter
    segue o que a configuração do admin diz. Só `ninguem` a pausa. Lido daqui,
    e não do router de Operação, para a newsletter não depender dele: a chave é
    o contrato entre os dois.
    """
    try:
        linhas = (
            supabase.table("pathr_feature_flag").select("state").eq("key", CHAVE_INTERRUPTOR)
            .limit(1).execute().data or []
        )
    except Exception:  # noqa: BLE001
        return True
    return not linhas or str(linhas[0].get("state")) != "ninguem"


def ler_config(supabase: Client, user_id: str) -> dict[str, Any]:
    linhas = supabase.table("pathr_newsletter_config").select("*").eq("user_id", user_id).limit(1).execute().data
    return {**PADRAO, **(linhas[0] if linhas else {}), "user_id": user_id}


def _marcar_tentativa(supabase: Client, user_id: str, agora_utc: datetime) -> None:
    supabase.table("pathr_newsletter_config").update(
        {"last_attempt_at": agora_utc.isoformat()}
    ).eq("user_id", user_id).execute()


async def enviar_edicao(
    supabase: Client,
    user: dict[str, Any],
    config: dict[str, Any],
    *,
    kind: str,
    itens: Optional[list[dict[str, Any]]] = None,
    agora_utc: Optional[datetime] = None,
) -> dict[str, Any]:
    """Monta (se não vieram itens) e envia UMA edição para o próprio admin.

    Devolve `{"enviado": bool, ...}`; nunca levanta por falta de notícia ou por
    falha do Brevo — o chamador (cron) precisa seguir para o próximo.
    """
    agora_utc = agora_utc or datetime.now(timezone.utc)
    user_id = str(user["id"])
    hoje = agora_utc.astimezone(fuso_do(user)).date()

    if itens is None:
        itens = await procurar(
            config.get("topics") or [],
            config.get("angles") or [],
            janela_em_dias(config, hoje),
            urls_ja_enviadas(supabase, user_id),
            int(config.get("items_per_topic") or 2),
        )
    if not itens:
        if kind == "agendada":
            _marcar_tentativa(supabase, user_id, agora_utc)
        return {"enviado": False, "motivo": "sem notícias novas para os temas escolhidos", "itens": 0}

    destino = str(user.get("email") or "")
    assunto = assunto_da_edicao(itens)
    saiu = bool(destino) and emails.send_newsletter(
        destino, str(user.get("name") or ""), assunto, agrupar(itens)
    )
    if not saiu:
        # Não trava o dia: falha do Brevo tem que poder ser tentada de novo.
        return {"enviado": False, "motivo": "o e-mail não saiu (Brevo)", "itens": len(itens)}

    supabase.table("pathr_newsletter_issue").insert(
        {"user_id": user_id, "subject": assunto, "kind": kind, "items": itens, "sent_on": hoje.isoformat()}
    ).execute()
    if kind == "agendada":
        supabase.table("pathr_newsletter_config").update(
            {"last_sent_on": hoje.isoformat(), "last_attempt_at": None}
        ).eq("user_id", user_id).execute()
    return {"enviado": True, "assunto": assunto, "itens": len(itens)}
