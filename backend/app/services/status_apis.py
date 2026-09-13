"""O estado de cada integração externa, para a página de Configurações.

## O que se checa, e como

Uma integração pode estar configurada e quebrada (chave revogada, cota
estourada), ou nem configurada. A página diz as duas coisas e o que cada uma
sustenta no app — "DeepL fora" sozinho não diz a ninguém que a tradução de
palavra ficou mais lenta.

Checagem AO VIVO só onde ela não custa cota nem crédito:

- IAs: a lista de modelos (gratuita em todos os provedores), mais o cooldown
  e o uso do dia que o rodízio já registra.
- DeepL: `/v2/usage`, que ainda devolve os caracteres usados no mês.
- Brevo: `/v3/account`.
- Gupy e o banco: consultas mínimas.
- YouTube e Adzuna: uma chamada mínima (1 unidade de cota do YouTube; uma
  busca de 1 resultado na Adzuna), por isso o cache.

Tavily, Brave e Remotive NÃO são chamados só para checar: os dois primeiros
cobram crédito por busca, e a Remotive pede poucas chamadas por dia. Para eles
vale o resultado do último uso real (ver `vagas.ultimo_estado`).

## Nunca a chave

O relatório diz se há chave, quantas (o rodízio aceita várias) e o que o
provedor respondeu. O valor da chave não sai daqui, nem mascarado.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx

from app import ai_providers
from app.config import settings
from app.services import traducao, vagas

_TIMEOUT = httpx.Timeout(8.0, connect=5.0)

# O relatório inteiro vale por este tempo; "verificar agora" só refaz depois
# de `INTERVALO_MINIMO_S`. Sem isso, clicar dez vezes gastaria dez unidades de
# cota do YouTube e dez buscas da Adzuna.
VALIDADE_S = 5 * 60
INTERVALO_MINIMO_S = 60

OK, DEGRADADA, ERRO, SEM_CHAVE, SEM_VERIFICACAO = "ok", "degradada", "erro", "nao_configurada", "sem_verificacao"


@dataclass
class Status:
    id: str
    nome: str
    categoria: str
    para_que: str
    configurada: bool
    estado: str
    detalhe: str = ""
    latencia_ms: Optional[int] = None
    uso: Optional[dict[str, Any]] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def publico(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "categoria": self.categoria,
            "para_que": self.para_que,
            "configurada": self.configurada,
            "estado": self.estado,
            "detalhe": self.detalhe,
            "latencia_ms": self.latencia_ms,
            "uso": self.uso,
            **self.extra,
        }


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def descreve_http(codigo: int) -> tuple[str, str]:
    """O estado e a frase para uma resposta HTTP de verificação."""
    if 200 <= codigo < 300:
        return OK, "Respondendo normalmente."
    if codigo in (401, 403):
        return ERRO, f"Chave recusada pelo provedor (HTTP {codigo}). Confira se ela não foi revogada."
    if codigo == 429:
        return DEGRADADA, "Limite de uso atingido. Volta a funcionar quando a cota renovar."
    if codigo >= 500:
        return DEGRADADA, f"O provedor está instável (HTTP {codigo})."
    return ERRO, f"Resposta inesperada (HTTP {codigo})."


async def _medir(
    pedido: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]],
) -> tuple[Optional[httpx.Response], int, Optional[str]]:
    inicio = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cliente:
            resposta = await pedido(cliente)
        return resposta, round((time.monotonic() - inicio) * 1000), None
    except httpx.HTTPError as erro:
        return None, round((time.monotonic() - inicio) * 1000), type(erro).__name__


def _por_resposta(base: Status, resposta: Optional[httpx.Response], ms: int, falha: Optional[str]) -> Status:
    base.latencia_ms = ms
    if resposta is None:
        base.estado, base.detalhe = ERRO, f"Sem resposta do provedor ({falha})."
    else:
        base.estado, base.detalhe = descreve_http(resposta.status_code)
    return base


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------


def _banco() -> Status:
    from app.health import _schema_ready

    base = Status(
        "supabase", "Supabase (banco de dados)", "Base",
        "Guarda contas, planos, progresso e tudo o que o app registra.",
        bool(settings.supabase_url and settings.supabase_service_role_key), SEM_CHAVE,
    )
    if not base.configurada:
        base.detalhe = "SUPABASE_URL ou a chave secreta não configurada — o app não funciona sem o banco."
        return base
    inicio = time.monotonic()
    resultado = _schema_ready()
    base.latencia_ms = round((time.monotonic() - inicio) * 1000)
    base.estado = OK if resultado.get("ok") else ERRO
    base.detalhe = "Tabelas acessíveis." if resultado.get("ok") else "As tabelas centrais não responderam."
    return base


# ---------------------------------------------------------------------------
# IA
# ---------------------------------------------------------------------------

_IA_PARA_QUE = "Gera roadmap, quizzes, exercícios de idioma, explicações e a análise de vagas, em rodízio."
_PROVEDORES_DE_IA = ("Gemini", "Groq", "Mistral", "Cerebras", "OpenRouter")


def _uso_de_ia_hoje() -> dict[str, dict[str, int]]:
    try:
        linhas = (
            ai_providers._store()
            .table("pathr_ai_provider_usage")
            .select("provider,requests,tokens")
            .eq("usage_date", date.today().isoformat())
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return {}
    return {
        str(linha["provider"]): {"requisicoes": int(linha.get("requests") or 0), "tokens": int(linha.get("tokens") or 0)}
        for linha in linhas
    }


def _candidatos_de_ia() -> list[tuple[str, str, str, Callable[[httpx.AsyncClient], Awaitable[httpx.Response]]]]:
    """(rótulo do rodízio, provedor, modelo, verificação) — uma entrada por chave."""
    saida = []
    chaves = ai_providers._keys(settings.gemini_api_key)
    for indice, chave in enumerate(chaves):
        saida.append((
            ai_providers._named("Gemini", indice, len(chaves)), "Gemini", "gemini-flash-latest",
            lambda c, chave=chave: c.get(
                "https://generativelanguage.googleapis.com/v1beta/models", params={"key": chave, "pageSize": 1}
            ),
        ))
    for provedor, atributo, base_url, atributo_modelo, _extra in ai_providers._OPENAI_COMPATIBLE:
        chaves = ai_providers._keys(getattr(settings, atributo, "") or "")
        for indice, chave in enumerate(chaves):
            saida.append((
                ai_providers._named(provedor, indice, len(chaves)), provedor, getattr(settings, atributo_modelo),
                lambda c, chave=chave, base_url=base_url: c.get(
                    f"{base_url}/models", headers={"Authorization": f"Bearer {chave}"}
                ),
            ))
    return saida


async def _ias() -> list[Status]:
    try:
        pausas = {s["provider"]: s for s in ai_providers.provider_status()}
    except Exception:  # noqa: BLE001
        pausas = {}
    uso = _uso_de_ia_hoje()
    candidatos = _candidatos_de_ia()
    medidas = await asyncio.gather(*(_medir(verifica) for *_, verifica in candidatos))

    saida: list[Status] = []
    for (rotulo, _provedor, modelo, _), (resposta, ms, falha) in zip(candidatos, medidas):
        status = _por_resposta(
            Status(f"ia:{rotulo}", rotulo, "Inteligência artificial", _IA_PARA_QUE, True, OK, extra={"modelo": modelo}),
            resposta, ms, falha,
        )
        pausa = pausas.get(rotulo)
        if status.estado == OK and pausa and not pausa["available"]:
            status.estado = DEGRADADA
            status.detalhe = f"Em pausa no rodízio até {pausa['until']}: {pausa['reason']}."
        if rotulo in uso:
            status.uso = {"hoje": uso[rotulo]}
        saida.append(status)

    configurados = {provedor for _, provedor, _, _ in candidatos}
    for provedor in _PROVEDORES_DE_IA:
        if provedor not in configurados:
            saida.append(Status(
                f"ia:{provedor}", provedor, "Inteligência artificial", _IA_PARA_QUE, False, SEM_CHAVE,
                "Sem chave. O rodízio segue com os outros provedores.",
            ))
    return saida


# ---------------------------------------------------------------------------
# Tradução, e-mail, material
# ---------------------------------------------------------------------------


async def _deepl() -> Status:
    base = Status("deepl", "DeepL", "Idiomas", "Tradução de palavras e das frases dos exercícios de idioma.",
                  bool(settings.deepl_api_key.strip()), SEM_CHAVE)
    if not base.configurada:
        base.detalhe = "Sem chave. A tradução passa a vir só da IA, com mais erros em termos técnicos."
        return base
    resposta, ms, falha = await _medir(lambda c: c.get(
        f"{traducao._base()}/v2/usage",
        headers={"Authorization": f"DeepL-Auth-Key {settings.deepl_api_key.strip()}"},
    ))
    _por_resposta(base, resposta, ms, falha)
    if resposta is not None and resposta.status_code == 200:
        corpo = resposta.json()
        usados, limite = int(corpo.get("character_count") or 0), int(corpo.get("character_limit") or 0)
        base.uso = {"usados": usados, "limite": limite, "unidade": "caracteres no mês"}
        if limite and usados >= limite:
            base.estado, base.detalhe = DEGRADADA, "Cota do mês esgotada. A tradução volta a vir só da IA até renovar."
        elif limite and usados >= limite * 0.9:
            base.estado, base.detalhe = DEGRADADA, "Mais de 90% da cota do mês já foi usada."
    return base


async def _brevo() -> Status:
    base = Status("brevo", "Brevo", "E-mail", "Confirmação de conta, recuperação de senha e os avisos por e-mail.",
                  bool(settings.brevo_api_key.strip()), SEM_CHAVE)
    if not base.configurada:
        base.detalhe = "Sem chave. Nenhum e-mail sai — nem o de confirmar a conta."
        return base
    resposta, ms, falha = await _medir(lambda c: c.get(
        "https://api.brevo.com/v3/account",
        headers={"api-key": settings.brevo_api_key.strip(), "accept": "application/json"},
    ))
    _por_resposta(base, resposta, ms, falha)
    if resposta is not None and resposta.status_code == 200:
        planos = resposta.json().get("plan") or []
        creditos = next((p.get("credits") for p in planos if p.get("creditsType") == "sendLimit"), None)
        if creditos is not None:
            base.uso = {"restantes": int(creditos), "unidade": "envios restantes no plano"}
    if not settings.brevo_from_email.strip():
        base.estado, base.detalhe = ERRO, "Falta BREVO_FROM_EMAIL: sem remetente, o envio é recusado."
    return base


async def _youtube() -> Status:
    base = Status("youtube", "YouTube Data API", "Material de estudo", "Busca os vídeos da curadoria de material.",
                  bool(settings.youtube_api_key.strip()), SEM_CHAVE)
    if not base.configurada:
        base.detalhe = "Sem chave. A curadoria segue só com artigos e documentação."
        return base
    # i18nLanguages custa 1 unidade de cota; uma busca custaria 100.
    resposta, ms, falha = await _medir(lambda c: c.get(
        "https://www.googleapis.com/youtube/v3/i18nLanguages",
        params={"part": "snippet", "hl": "pt", "key": settings.youtube_api_key.strip()},
    ))
    _por_resposta(base, resposta, ms, falha)
    if resposta is not None and resposta.status_code == 403 and "quota" in resposta.text.lower():
        base.estado, base.detalhe = DEGRADADA, "Cota diária do YouTube esgotada. Renova à meia-noite do horário do Pacífico."
    return base


def _pelo_ultimo_uso(base: Status, fonte: str) -> Status:
    ultimo = vagas.ultimo_estado.get(fonte)
    if not ultimo:
        base.estado = SEM_VERIFICACAO
        base.detalhe = (
            "Não é chamada só para checar (gasta crédito ou pede moderação). "
            "O estado aparece depois da primeira busca de vagas ou de material."
        )
        return base
    estado, quando = ultimo
    base.estado = OK if estado == "ok" else ERRO
    base.detalhe = ("Funcionou" if estado == "ok" else "Falhou") + " no último uso."
    base.extra["ultimo_uso_em"] = quando.isoformat()
    return base


def _buscador(id_: str, nome: str, configurada: bool, outro_ativo: bool) -> Status:
    base = Status(id_, nome, "Material de estudo", "Busca artigos para a curadoria e vagas em sites de emprego.",
                  configurada, SEM_CHAVE)
    if not configurada:
        base.detalhe = "Sem chave." + (
            " O outro buscador cobre." if outro_ativo else " Artigos e vagas de sites de emprego ficam de fora."
        )
        return base
    return _pelo_ultimo_uso(base, "busca")


# ---------------------------------------------------------------------------
# Vagas
# ---------------------------------------------------------------------------


async def _gupy() -> Status:
    base = Status("gupy", "Gupy", "Vagas", "Vagas do Brasil, incluindo remotas. Não precisa de chave.", True, OK)
    resposta, ms, falha = await _medir(lambda c: c.get(vagas.GUPY, params={"jobName": "desenvolvedor", "limit": 1}))
    return _por_resposta(base, resposta, ms, falha)


async def _adzuna() -> Status:
    base = Status("adzuna", "Adzuna", "Vagas", "Vagas do Brasil agregadas de vários sites.",
                  vagas.fontes_disponiveis()["adzuna"], SEM_CHAVE)
    if not base.configurada:
        base.detalhe = "Sem ADZUNA_APP_ID e ADZUNA_APP_KEY. As vagas seguem pelas outras fontes."
        return base
    resposta, ms, falha = await _medir(lambda c: c.get(vagas.ADZUNA, params={
        "app_id": settings.adzuna_app_id.strip(),
        "app_key": settings.adzuna_app_key.strip(),
        "what": "desenvolvedor",
        "results_per_page": 1,
        "content-type": "application/json",
    }))
    return _por_resposta(base, resposta, ms, falha)


def _remotive() -> Status:
    base = Status("remotive", "Remotive", "Vagas", "Vagas remotas internacionais. Não precisa de chave.", True, OK)
    return _pelo_ultimo_uso(base, "remotive")


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

_relatorio: Optional[dict[str, Any]] = None
_feito_em: float = 0.0
_trava: Optional[asyncio.Lock] = None


def limpar_cache() -> None:
    global _relatorio, _feito_em, _trava
    _relatorio, _feito_em, _trava = None, 0.0, None


def resumo(itens: list[dict[str, Any]]) -> dict[str, int]:
    contagem = {OK: 0, DEGRADADA: 0, ERRO: 0, SEM_CHAVE: 0, SEM_VERIFICACAO: 0}
    for item in itens:
        contagem[item["estado"]] = contagem.get(item["estado"], 0) + 1
    return contagem


async def _montar() -> dict[str, Any]:
    tavily = bool(settings.tavily_api_key.strip())
    brave = bool(settings.brave_api_key.strip())
    ias, deepl, brevo, youtube, gupy, adzuna = await asyncio.gather(
        _ias(), _deepl(), _brevo(), _youtube(), _gupy(), _adzuna()
    )
    itens: list[Status] = [
        await asyncio.to_thread(_banco),
        *ias,
        deepl,
        brevo,
        youtube,
        _buscador("tavily", "Tavily", tavily, brave),
        _buscador("brave", "Brave Search", brave, tavily),
        gupy,
        _remotive(),
        adzuna,
    ]
    publicos = [item.publico() for item in itens]
    return {"itens": publicos, "resumo": resumo(publicos), "verificado_em": _agora().isoformat()}


async def relatorio(atualizar: bool = False) -> dict[str, Any]:
    global _relatorio, _feito_em, _trava
    if _trava is None:
        _trava = asyncio.Lock()
    async with _trava:
        idade = time.monotonic() - _feito_em
        refazer = _relatorio is None or idade >= VALIDADE_S or (atualizar and idade >= INTERVALO_MINIMO_S)
        if refazer:
            _relatorio = await _montar()
            _feito_em = time.monotonic()
        restante = max(0, round(INTERVALO_MINIMO_S - (time.monotonic() - _feito_em)))
        return {**_relatorio, "pode_atualizar_em_s": restante}
