"""Tradução para português pelo DeepL, com o modelo de IA como reserva.

## Onde entra

- Na consulta de palavra do módulo de idioma: a tradução da palavra, com a
  frase em que ela apareceu como contexto.
- No treino diário: a tradução das frases de montar, ditado e fala.

Nos dois lugares o modelo de IA já escrevia uma tradução. O DeepL passa a ser
a fonte principal porque traduz frase com mais naturalidade — e quando ele
falha, a do modelo continua na tela. Tradução nunca é motivo para um exercício
ou uma consulta dar erro.

## Termos de programação ficam em inglês

"Front end", "back end", "worktree", "branch", "merge", "deploy"… são o
vocabulário do trabalho, e ninguém num time brasileiro diz "árvore de
trabalho", "fusão" ou "implantação". Sem ajuda, o DeepL traduz todos eles —
medido: "We deleted the old branches after the merge" virava "Apagamos os
ramos antigos após a fusão".

O remédio é o glossário do DeepL, cada termo mapeado para ele mesmo. A lista
mora em `TERMOS_UNIVERSAIS`, e é a MESMA que vai nos prompts do modelo: a
tradução de reserva preserva os mesmos termos, e as duas fontes não divergem.

## Os cuidados, todos medidos com a chave real

1. **Um glossário só, com vários idiomas dentro.** O plano Free permite um
   glossário na conta ("Too many glossaries" ao criar o segundo). A API v3
   aceita vários pares num glossário só — um dicionário por idioma de origem —,
   e foi assim que espanhol, francês e alemão também passaram a preservar os
   termos ("O deploy falhou após o último merge").

2. **Frase cheia de termos pode voltar sem tradução.** Com três termos do
   glossário numa frase, o DeepL às vezes conclui que ela já está no idioma
   de destino e devolve inglês — e não igual à entrada, REESCRITO: "The deploy
   failed…" voltou "The deployment failed…", e numa delas "until Monday" voltou
   "until Tuesday". Comparar com a entrada não pegaria nenhuma. Por isso a
   saída passa por `parece_portugues`: não parece, vale a tradução do modelo.

3. **Tags para "não traduzir" pioraram.** Marcar os termos fez o DeepL tratá-los
   como caixas opacas e inventar verbos em volta: "Eu já acessei merged".

4. **O glossário muda com a lista.** O nome carrega o hash das entradas; se
   `TERMOS_UNIVERSAIS` mudar, o glossário antigo é apagado — liberando a vaga
   única — e um novo é criado.

## Plano Free e cota

Chave terminada em ":fx" é do plano Free e usa api-free.deepl.com. A cota é de
um milhão de caracteres por mês; frases de treino têm de 5 a 14 palavras, e o
cache em memória evita pagar duas vezes pela mesma consulta de palavra.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import OrderedDict
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("pathr.traducao")

_TIMEOUT = 8
_ALVO = "PT-BR"

# Os códigos do catálogo (services/languages.py) no formato do DeepL.
# "pt" fica de fora: traduzir português para português não ajuda ninguém.
_ORIGEM = {"en": "EN", "es": "ES", "fr": "FR", "de": "DE", "it": "IT", "ja": "JA", "zh": "ZH", "ko": "KO"}

# O vocabulário de trabalho que fica em inglês em qualquer tradução. Plural e
# grafias com e sem hífen entram separados: o glossário casa texto, não raiz.
# Palavras que o português já tem e o time usa ("repositório", "biblioteca",
# "banco de dados") ficam de fora — elas SÃO traduzidas no dia a dia.
TERMOS_UNIVERSAIS: tuple[str, ...] = (
    "front end", "front-end", "frontend", "back end", "back-end", "backend",
    "full stack", "full-stack", "fullstack",
    "worktree", "worktrees", "branch", "branches", "merge", "merges",
    "pull request", "pull requests", "merge request", "merge requests",
    "commit", "commits", "rebase", "checkout", "cherry-pick", "stash",
    "deploy", "deploys", "deployment", "build", "builds", "release", "releases",
    "rollback", "hotfix", "hotfixes", "staging", "pipeline", "pipelines", "CI/CD",
    "framework", "frameworks", "endpoint", "endpoints", "API", "APIs",
    "query", "queries", "cache", "debug", "bug", "bugs", "log", "logs",
    "backlog", "code review", "sprint", "sprints", "standup", "stand-up", "daily",
    "feature flag", "feature flags", "script", "scripts", "container", "containers",
    "cluster", "clusters", "webhook", "webhooks", "token", "tokens", "payload",
    "stack", "sandbox", "repo", "repos", "Docker", "Kubernetes", "Git", "GitHub",
)

_CACHE_MAXIMO = 500
_cache: "OrderedDict[tuple[str, str, str], str]" = OrderedDict()
# None = ainda não procurado; "" = procurado e indisponível (não tentar de novo
# neste processo — cada tentativa custaria duas idas ao DeepL por tradução).
_glossario: Optional[str] = None


def disponivel() -> bool:
    return bool((settings.deepl_api_key or "").strip())


def _base() -> str:
    chave = settings.deepl_api_key.strip()
    return "https://api-free.deepl.com" if chave.endswith(":fx") else "https://api.deepl.com"


def _cabecalhos() -> dict[str, str]:
    return {"Authorization": f"DeepL-Auth-Key {settings.deepl_api_key.strip()}"}


def _entradas() -> str:
    return "\n".join(f"{termo}\t{termo}" for termo in TERMOS_UNIVERSAIS)


def nome_do_glossario() -> str:
    """O nome carrega o hash das entradas: mudar a lista muda o nome."""
    return "pathr-termos-" + hashlib.sha256(_entradas().encode()).hexdigest()[:10]


async def _id_do_glossario(cliente: httpx.AsyncClient) -> Optional[str]:
    """O glossário multilíngue: reaproveita o atual, troca o de lista velha.

    Procurado pelo nome para sobreviver a restart sem criar outro. Sem
    glossário se não der — traduzir sem ele é pior no jargão, e a detecção de
    `parece_portugues` continua valendo, mas é melhor que não traduzir.
    """
    global _glossario
    if _glossario is not None:
        return _glossario or None
    nome = nome_do_glossario()
    try:
        existentes = await cliente.get(f"{_base()}/v3/glossaries", headers=_cabecalhos())
        existentes.raise_for_status()
        for glossario in existentes.json().get("glossaries", []):
            if glossario.get("name") == nome:
                _glossario = glossario["glossary_id"]
                return _glossario
            if str(glossario.get("name", "")).startswith("pathr-termos-"):
                # Lista antiga ocupando a vaga única do plano Free.
                await cliente.delete(
                    f"{_base()}/v3/glossaries/{glossario['glossary_id']}", headers=_cabecalhos()
                )
        criado = await cliente.post(
            f"{_base()}/v3/glossaries",
            headers=_cabecalhos(),
            json={
                "name": nome,
                "dictionaries": [
                    {"source_lang": codigo, "target_lang": "pt", "entries": _entradas(), "entries_format": "tsv"}
                    for codigo in _ORIGEM
                ],
            },
        )
        criado.raise_for_status()
        _glossario = criado.json()["glossary_id"]
        return _glossario
    except (httpx.HTTPError, KeyError, ValueError):
        logger.warning("glossário do DeepL indisponível; traduzindo sem ele", exc_info=True)
        _glossario = ""
        return None


# ---------------------------------------------------------------------------
# A saída é português?
# ---------------------------------------------------------------------------

# Palavras funcionais que só um dos idiomas usa. As comuns aos dois ("de",
# "a", "que", "para") não entram: não distinguem nada.
_PT = frozenset(
    "o os do da dos das no na nos nas um uma uns umas e é não você vocês "
    "após até então isso esse essa este esta muito também mais já foi são "
    "pelo pela com em ao aos seu sua nosso nossa meu minha".split()
)
_OUTROS = frozenset(
    # inglês
    "the of and is are was were be been this that these those it its our your "
    "my their has have had will would could should with after before because "
    "until from which does did "
    # espanhol
    "el los las del y pero muy también después está están hice hizo ayer "
    # francês
    "le les des du et est sont avec pour nous vous dans pas une "
    # alemão
    "der die das und ist sind nicht mit nach vor wir ich ein eine "
    # italiano
    "il gli della delle è sono non con dopo abbiamo".split()
)
_ESCRITA_ASIATICA = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_PALAVRA = re.compile(r"[^\W\d_]+", re.UNICODE)
_TERMOS_MINUSCULOS = frozenset(palavra.lower() for termo in TERMOS_UNIVERSAIS for palavra in termo.split())


def parece_portugues(texto: str) -> bool:
    """A tradução saiu em português, ou o DeepL devolveu o idioma de origem?

    Conta palavras funcionais que só um dos lados usa, ignorando os termos
    técnicos (que ficam em inglês de propósito e não podem fazer uma frase
    portuguesa parecer inglesa). Japonês, chinês e coreano são detectados pela
    escrita: se sobrou kana, hanzi ou hangul, não traduziu.
    """
    if _ESCRITA_ASIATICA.search(texto):
        return False
    palavras = [p for p in (w.lower() for w in _PALAVRA.findall(texto)) if p not in _TERMOS_MINUSCULOS]
    pt = sum(1 for p in palavras if p in _PT)
    outros = sum(1 for p in palavras if p in _OUTROS)
    if pt == 0 and outros == 0:
        # Frase curta demais para julgar ("Olá!"): aceita.
        return True
    return pt >= outros


async def traduzir(
    textos: list[str], idioma: str, *, contexto: Optional[str] = None
) -> Optional[list[Optional[str]]]:
    """Traduz para português do Brasil. Uma saída por entrada, na mesma ordem.

    Devolve None se o DeepL não puder ser usado nesta chamada (sem chave,
    idioma fora, rede, cota) — e, dentro da lista, None para cada texto que não
    voltou em português. Nos dois casos quem chama mantém a tradução que já
    tinha.
    """
    origem = _ORIGEM.get((idioma or "").lower())
    limpos = [(texto or "").strip() for texto in textos]
    if not disponivel() or not origem or not any(limpos):
        return None

    chave_contexto = (contexto or "").strip()[:600]
    saida: list[Optional[str]] = [None] * len(limpos)
    faltam: list[int] = []
    for i, texto in enumerate(limpos):
        chave = (origem, texto, chave_contexto)
        if texto and chave in _cache:
            _cache.move_to_end(chave)
            saida[i] = _cache[chave]
        elif texto:
            faltam.append(i)
    if not faltam:
        return saida

    corpo: dict = {"text": [limpos[i] for i in faltam], "source_lang": origem, "target_lang": _ALVO}
    if chave_contexto:
        # O contexto orienta a acepção e não é traduzido: foi o que fez
        # "book", em "book a meeting room", sair "reservar" e não "livro".
        corpo["context"] = chave_contexto
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cliente:
            glossario = await _id_do_glossario(cliente)
            if glossario:
                corpo["glossary_id"] = glossario
            resposta = await cliente.post(f"{_base()}/v2/translate", headers=_cabecalhos(), json=corpo)
            resposta.raise_for_status()
            traducoes = [t.get("text", "") for t in resposta.json().get("translations", [])]
    except (httpx.HTTPError, ValueError):
        logger.warning("DeepL indisponível agora", exc_info=True)
        return None
    if len(traducoes) != len(faltam):
        return None

    for posicao, i in enumerate(faltam):
        traduzida = traducoes[posicao].strip()
        if not traduzida or not parece_portugues(traduzida):
            continue
        saida[i] = traduzida
        _cache[(origem, limpos[i], chave_contexto)] = traduzida
        if len(_cache) > _CACHE_MAXIMO:
            _cache.popitem(last=False)
    return saida
