"""Geração de texto por IA com rotação automática entre provedores.

Portado do Notter (backend/app/ai_providers.py de lá), pelo mesmo motivo que
o levou a existir: uma cota de tier gratuito estourada derruba TODA função
de IA do app pelo resto do dia, mesmo com a chave e a integração intactas.
Aqui isso apagaria a leitura de currículo, a geração de roadmap, os quizzes e
o módulo de idioma de uma vez. `generate_json()` tenta uma lista de
candidatos em ordem e cai para o próximo numa falha, então o app só fica
indisponível se TODOS os provedores configurados falharem ao mesmo tempo.

Três coisas fazem a rotação valer quando a cota realmente acaba, em vez de
rotacionar só dentro de uma requisição:

1. **Múltiplas chaves por provedor.** Todo `*_API_KEY` aceita lista separada
   por vírgula, então `GEMINI_API_KEY=k1,k2,k3` vira três candidatos
   ("Gemini", "Gemini #2", "Gemini #3") com três cotas independentes. Com uma
   chave só, nada muda.

2. **Cooldown (circuit breaker) persistido.** Um candidato que respondeu
   429/402 é pulado por um tempo nas requisições seguintes, em vez de ser
   tentado primeiro toda vez. Fica na tabela `pathr_ai_provider_cooldown`
   porque o processo reinicia e a cota diária não: sem persistir, o primeiro
   pedido depois de cada restart torna a bater na chave esgotada. Erro de
   autenticação (chave errada, modelo inexistente) espera mais; falha de rede
   espera quase nada.

   A tabela vive no banco do próprio PathR e as chaves são da conta dele,
   então o que o cooldown registra é a cota deste app — nunca a de outro.

3. **Nunca desiste cedo.** Candidato em cooldown é rebaixado para o fim da
   fila, nunca removido. Se todos os saudáveis falharem, os resfriados ainda
   são tentados antes de a requisição ser declarada perdida — um cooldown
   obsoleto não consegue ser a causa de uma indisponibilidade.

`generate_json_with_media()` é o caminho da leitura de currículo: manda o PDF
inteiro para o modelo em vez de só o texto extraído, o que preserva o layout
de duas colunas e as tabelas de skills que a extração de texto embaralha.

Todo provedor é opcional (sem chave = ignorado em silêncio). Um clone novo
funciona com uma única chave configurada:
  - Gemini      https://aistudio.google.com/apikey     (tier gratuito)
  - Groq        https://console.groq.com/keys          (tier gratuito)
  - Mistral     https://console.mistral.ai/api-keys    (tier gratuito)
  - Cerebras    https://cloud.cerebras.ai              (tier gratuito)
  - OpenRouter  https://openrouter.ai/keys             (cobra por uso)

O OpenRouter já teve slugs ":free" e não tem mais os que este app usava — o
antigo `openai/gpt-oss-20b:free` saiu do catálogo e passou a responder 404 em
toda tentativa, gastando um candidato da rotação sem nunca poder dar certo.

Saída estruturada: o Gemini recebe o `responseSchema` nativo dele; os outros
são APIs OpenAI-compatible e recebem `response_format: {"type":
"json_object"}` — que garante JSON válido, não um formato específico. O texto
do prompt já descreve o formato desejado, e todo chamador aqui revalida o
resultado antes de confiar nele.
"""

import asyncio
import base64
import json
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx
from starlette.concurrency import run_in_threadpool

from app.config import settings

# Um currículo de duas páginas mandado como PDF é uma requisição bem maior que
# um chat de texto; 45s dá folga sem deixar a rotação inteira estourar o
# timeout do cliente no pior caso de vários candidatos em sequência.
_TIMEOUT = 45

# O teto da rotação INTEIRA, e não de um candidato só.
#
# 45s é por candidato, e os candidatos são tentados em sequência: com duas
# chaves de Gemini e mais um provedor configurado, três candidatos lentos
# somam 135s. O proxy da borda encerra a conexão bem antes disso, e o que a
# pessoa recebe depois de esperar é um 502 sem explicação nenhuma — a rota
# nunca chegou a responder. Com o teto, a última coisa que acontece dentro da
# janela é a NOSSA resposta, dizendo o que falhou.
#
# 50s é escolhido para caber com folga na janela de 60s que os proxies usam
# como padrão. Quem tem borda mais generosa pode subir por env.
_BUDGET = max(1, int(getattr(settings, "ai_budget_seconds", 0) or 50))

# Abaixo disto não vale começar uma tentativa: o candidato não teria tempo de
# responder, e a tentativa só gastaria o resto do orçamento sem chance de dar
# certo.
_MIN_ATTEMPT = 5

# Quanto tempo um candidato fica fora da ordem preferida depois de cada tipo
# de falha. Cota é o caso comum (tier gratuito acabou): longo o bastante para
# o app parar de gastar uma ida e volta por requisição, curto o bastante para
# um limite por hora se recuperar sozinho. Erro de auth/config não se conserta
# sozinho, então espera mais. Falha de rede quase não é penalizada.
_QUOTA_COOLDOWN = timedelta(minutes=30)
_AUTH_COOLDOWN = timedelta(hours=1)
_TRANSIENT_COOLDOWN = timedelta(seconds=45)
# Teto para um Retry-After vindo do provedor — um servidor pedindo um dia de
# espera deixaria o candidato de escanteio muito além do ponto em que tentar
# de novo é barato.
_MAX_COOLDOWN = timedelta(hours=6)


class AiProviderError(Exception):
    """Todos os provedores configurados falharam. `.detail` é uma mensagem
    segura para mostrar ao usuário — nunca vaza corpo de erro do provedor."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


QUOTA = "quota"
AUTH = "auth"
TRANSIENT = "transient"

_COOLDOWN_BY_KIND = {QUOTA: _QUOTA_COOLDOWN, AUTH: _AUTH_COOLDOWN, TRANSIENT: _TRANSIENT_COOLDOWN}


class _CandidateFailed(Exception):
    """Um candidato (provedor + chave) falhou. `kind` decide quanto tempo ele
    fica fora da rotação; `detail` é o motivo em pt-BR."""

    def __init__(self, kind: str, detail: str, retry_after: Optional[timedelta] = None):
        self.kind = kind
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(detail)


@dataclass
class _Cooldown:
    until: datetime
    reason: str


# nome -> cooldown. Espelho em memória da tabela pathr_ai_provider_cooldown.
# Toda a lógica de rotação lê e escreve só aqui, sem rede; a sincronização com
# o banco acontece nas bordas.
_cooldowns: dict[str, _Cooldown] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Persistência do cooldown e do consumo
# --------------------------------------------------------------------------
#
# Três invariantes que este bloco não pode quebrar:
#
# 1. Nunca virar fonte de verdade — candidato em cooldown é rebaixado, nunca
#    removido, então um registro obsoleto não derruba a IA.
# 2. Nunca falhar a chamada de IA — toda leitura/escrita é best-effort; se o
#    Supabase estiver fora, a rotação segue com o estado em memória.
# 3. Nunca bloquear o event loop — supabase-py é síncrono e as funções de
#    rotação são async, então as chamadas passam por run_in_threadpool.

# De quanto em quanto tempo o espelho em memória é reconciliado com o banco.
# Só vale para leitura; a escrita é imediata. 20s é curto perto do menor
# cooldown real (45s) e evita uma consulta por chamada numa rajada.
_COOLDOWN_REFRESH_INTERVAL = timedelta(seconds=20)
_last_cooldown_refresh: Optional[datetime] = None

# Desligado pelos testes de rotação, que são declaradamente offline: sem esta
# chave eles gravariam cooldown de provedores fictícios no Supabase real.
_persistence_enabled = True


def _store():
    """O client do Supabase, importado tarde de propósito: manter este módulo
    importável sem ambiente configurado é o que deixa a suíte de rotação
    offline e rápida."""
    from app.database import get_supabase

    return get_supabase()


def _load_cooldowns() -> None:
    """Reconcilia o espelho em memória com a tabela. Síncrono — sempre chamado
    de dentro de um threadpool."""
    global _last_cooldown_refresh
    if not _persistence_enabled:
        return
    now = _now()
    if _last_cooldown_refresh and now - _last_cooldown_refresh < _COOLDOWN_REFRESH_INTERVAL:
        return
    try:
        rows = _store().table("pathr_ai_provider_cooldown").select("*").execute().data or []
    except Exception:  # noqa: BLE001 — best-effort, ver invariante 2
        return
    fresh: dict[str, _Cooldown] = {}
    for row in rows:
        until = _parse_ts(row.get("until"))
        if until and until > now:
            fresh[row["provider"]] = _Cooldown(until=until, reason=row.get("reason") or "")
    _cooldowns.clear()
    _cooldowns.update(fresh)
    _last_cooldown_refresh = now


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _persist_cooldown(name: str, cooldown: _Cooldown) -> None:
    if not _persistence_enabled:
        return
    try:
        _store().table("pathr_ai_provider_cooldown").upsert(
            {
                "provider": name,
                "until": cooldown.until.isoformat(),
                "reason": cooldown.reason,
                "updated_at": _now().isoformat(),
            },
            on_conflict="provider",
        ).execute()
    except Exception:  # noqa: BLE001
        pass


def _forget_cooldown(name: str) -> None:
    if not _persistence_enabled:
        return
    try:
        _store().table("pathr_ai_provider_cooldown").delete().eq("provider", name).execute()
    except Exception:  # noqa: BLE001
        pass


def _log_usage(name: str, tokens: int) -> None:
    """Soma tokens no dia corrente. Sem transação: uma corrida perde alguns
    tokens de contagem, o que é aceitável para um painel de custo e não vale
    o custo de serializar toda chamada de IA."""
    if not _persistence_enabled:
        return
    today = date.today().isoformat()
    try:
        store = _store()
        existing = (
            store.table("pathr_ai_provider_usage")
            .select("id,requests,tokens")
            .eq("provider", name)
            .eq("usage_date", today)
            .limit(1)
            .execute()
            .data
        )
        if existing:
            row = existing[0]
            store.table("pathr_ai_provider_usage").update(
                {
                    "requests": int(row.get("requests") or 0) + 1,
                    "tokens": int(row.get("tokens") or 0) + tokens,
                    "updated_at": _now().isoformat(),
                }
            ).eq("id", row["id"]).execute()
        else:
            store.table("pathr_ai_provider_usage").insert(
                {"provider": name, "usage_date": today, "requests": 1, "tokens": tokens}
            ).execute()
    except Exception:  # noqa: BLE001
        pass


async def _refresh_cooldowns_async() -> None:
    await run_in_threadpool(_load_cooldowns)


async def _log_usage_async(name: str, tokens: int) -> None:
    await run_in_threadpool(_log_usage, name, tokens)


# --------------------------------------------------------------------------
# Classificação de falha e bookkeeping do cooldown
# --------------------------------------------------------------------------


def _parse_retry_after(response: httpx.Response) -> Optional[timedelta]:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        seconds = int(float(raw.strip()))
    except ValueError:
        return None
    return min(timedelta(seconds=max(seconds, 0)), _MAX_COOLDOWN)


def _classify(response: httpx.Response) -> _CandidateFailed:
    """Traduz o status HTTP do provedor em uma decisão de rotação.

    O corpo do erro nunca sobe para o usuário: provedores costumam ecoar
    trechos do prompt (e, aqui, o currículo de alguém) nas mensagens de erro.
    """
    status = response.status_code
    retry_after = _parse_retry_after(response)
    if status in (402, 429):
        return _CandidateFailed(QUOTA, "limite de uso atingido", retry_after)
    if status in (400, 401, 403, 404):
        return _CandidateFailed(AUTH, f"chave ou modelo recusado (HTTP {status})", retry_after)
    return _CandidateFailed(TRANSIENT, f"indisponível agora (HTTP {status})", retry_after)


def _mark_unavailable(name: str, failure: _CandidateFailed) -> None:
    duration = failure.retry_after or _COOLDOWN_BY_KIND.get(failure.kind, _TRANSIENT_COOLDOWN)
    cooldown = _Cooldown(until=_now() + min(duration, _MAX_COOLDOWN), reason=failure.detail)
    _cooldowns[name] = cooldown
    _persist_cooldown(name, cooldown)


def _mark_available(name: str) -> None:
    if _cooldowns.pop(name, None) is not None:
        _forget_cooldown(name)


async def _mark_unavailable_async(name: str, failure: _CandidateFailed) -> None:
    await run_in_threadpool(_mark_unavailable, name, failure)


async def _mark_available_async(name: str) -> None:
    await run_in_threadpool(_mark_available, name)


def _cooldown_of(name: str) -> Optional[_Cooldown]:
    cooldown = _cooldowns.get(name)
    if cooldown is None:
        return None
    if cooldown.until <= _now():
        _cooldowns.pop(name, None)
        return None
    return cooldown


# --------------------------------------------------------------------------
# Chamadas aos provedores
# --------------------------------------------------------------------------

_GEMINI_MODEL = "gemini-flash-latest"
_GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent"

# Pedido "rápido": sem raciocínio antes de responder. O flash pensa por padrão,
# e numa conversa curta (o tutor do "Perguntar") esse tempo não chega à tela —
# é só espera. Uma ContextVar e não um parâmetro em cada candidato: a rotação
# passa os mesmos três argumentos a todos, e só o Gemini sabe desligar isto.
_rapido: ContextVar[bool] = ContextVar("pedido_rapido", default=False)


def _parsed_object(text: str) -> dict:
    """Todo chamador espera um OBJETO JSON. Um provedor que responde `null`,
    uma lista solta ou prosa passaria como sucesso e explodiria lá na frente —
    levantar aqui transforma isso em mais um motivo para rotacionar."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("resposta não é um objeto JSON")
    return parsed


async def _call_gemini(
    system_prompt: str, user_prompt: str, schema: Optional[dict], api_key: str
) -> tuple[dict, int]:
    generation_config: dict[str, Any] = {"responseMimeType": "application/json"}
    if schema:
        generation_config["responseSchema"] = schema
    corpo = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
        "generationConfig": generation_config,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        if _rapido.get():
            rapido = {**corpo, "generationConfig": {**generation_config, "thinkingConfig": {"thinkingBudget": 0}}}
            response = await client.post(_GEMINI_URL, params={"key": api_key}, json=rapido)
            # Modelo que não aceita desligar o raciocínio responde 400: aí vai
            # o pedido normal, e a conversa só perde a pressa, não a resposta.
            if response.status_code == 400:
                response = await client.post(_GEMINI_URL, params={"key": api_key}, json=corpo)
        else:
            response = await client.post(_GEMINI_URL, params={"key": api_key}, json=corpo)
    if response.status_code != 200:
        raise _classify(response)
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    # usageMetadata é a contagem real reportada pelo próprio Gemini, não
    # estimativa nossa. Ausente em erro, daí o .get() com 0.
    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
    return _parsed_object(text), tokens


async def _call_gemini_with_media(
    system_prompt: str,
    user_prompt: str,
    media_bytes: bytes,
    mime_type: str,
    schema: Optional[dict],
    api_key: str,
) -> tuple[dict, int]:
    """Mesma requisição do texto, com uma parte `inlineData` a mais — é assim
    que o PDF do currículo chega inteiro ao modelo."""
    generation_config: dict[str, Any] = {"responseMimeType": "application/json"}
    if schema:
        generation_config["responseSchema"] = schema
    encoded = base64.b64encode(media_bytes).decode("ascii")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"},
                            {"inlineData": {"mimeType": mime_type, "data": encoded}},
                        ]
                    }
                ],
                "generationConfig": generation_config,
            },
        )
    if response.status_code != 200:
        raise _classify(response)
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
    return _parsed_object(text), tokens


def _schema_contract(schema: Optional[dict]) -> str:
    """O schema do Gemini escrito como texto, para quem não aceita schema.

    `response_format: json_object` garante JSON VÁLIDO, não JSON no formato
    combinado — e a diferença derrubou a leitura de currículo em produção: o
    modelo devolveu `{"anos_experiencia": 2.5, "competencias": [...]}`, com a
    lista de tecnologias sob um nome que ninguém lê. O JSON era perfeito, o
    currículo entrou vazio, e nada falhou em lugar nenhum.

    Revalidar a resposta (como o resume_parser faz) não resolve isso: não há
    como recuperar uma chave que o modelo decidiu chamar de outra coisa. O
    nome precisa ir no pedido.

    Renderiza só o FORMATO, não as regras — estas continuam no prompt de cada
    chamador, que é onde fazem sentido.
    """
    if not schema:
        return ""
    return (
        "\n\nFORMATO DA RESPOSTA — um objeto JSON com EXATAMENTE estas chaves, "
        "com estes nomes, sem trocar por sinônimos:\n"
        f"{_render_shape(schema, 0)}\n"
        'Chave sem informação vem vazia ("" ou []), nunca omitida nem renomeada.'
    )


def _render_shape(node: dict, depth: int) -> str:
    """Um nó do schema como pseudo-JSON legível. Recursivo porque os schemas
    deste app aninham objeto dentro de array (questões, fases, tecnologias)."""
    tipo = str(node.get("type", "STRING")).upper()
    recuo = "  " * (depth + 1)

    if tipo == "OBJECT":
        propriedades = node.get("properties") or {}
        if not propriedades:
            return "{}"
        linhas = [
            f'{recuo}"{nome}": {_render_shape(filho, depth + 1)}'
            for nome, filho in propriedades.items()
        ]
        return "{\n" + ",\n".join(linhas) + "\n" + "  " * depth + "}"

    if tipo == "ARRAY":
        return "[" + _render_shape(node.get("items") or {}, depth) + "]"

    return {
        "STRING": "string",
        "INTEGER": "inteiro",
        "NUMBER": "número",
        "BOOLEAN": "booleano",
    }.get(tipo, "string")


async def _call_openai_compatible(
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    schema: Optional[dict] = None,
    extra: Optional[dict] = None,
) -> tuple[dict, int]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    # O contrato vai no fim da mensagem do usuário, e não no
                    # system: é a última coisa que o modelo lê antes de
                    # responder, que é onde instrução de formato pega melhor.
                    {"role": "user", "content": user_prompt + _schema_contract(schema)},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": _MAX_TOKENS,
                **(extra or {}),
            },
        )
    if response.status_code != 200:
        raise _classify(response)
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return _parsed_object(text), tokens


# --------------------------------------------------------------------------
# Candidatos e rotação
# --------------------------------------------------------------------------


@dataclass
class _Candidate:
    """Um provedor + uma chave. Duas chaves do mesmo provedor são dois
    candidatos, com cotas e cooldowns independentes."""

    name: str
    call: Callable[..., Awaitable[Any]]


def _keys(raw: str) -> list[str]:
    """`GEMINI_API_KEY=k1,k2` vira ["k1", "k2"]. Uma chave só vira lista de um
    item, então nada muda para quem configurou uma."""
    return [key.strip() for key in raw.replace(";", ",").replace("\n", ",").split(",") if key.strip()]


def _named(provider: str, index: int, total: int) -> str:
    return provider if total == 1 else f"{provider} #{index + 1}"


def _sentence(reason: str) -> str:
    """"limite de uso atingido" vira "Limite de uso atingido". str.capitalize()
    não serve: ele minúsculiza o resto e estragaria "(HTTP 400)"."""
    return reason[:1].upper() + reason[1:] if reason else reason


# Teto de tokens da resposta. Nada limitava o tamanho da geração, e um modelo
# de raciocínio sem teto pensa até onde o contexto deixar — com contextos de um
# milhão de tokens por aí, "sem teto" e "pendurado" são a mesma coisa vistos do
# lado de cá. O valor cobre com folga o maior pedido real (o roadmap fechou em
# 6.275 tokens de saída) sem cortar a resposta no meio, que quebraria o JSON.
_MAX_TOKENS = 8000

# Parâmetros extras por provedor, além do corpo comum.
#
# O OpenRouter é o único que precisa: o gpt-oss é modelo de raciocínio e, no
# pedido do roadmap, 2.948 dos 6.275 tokens de saída eram raciocínio que a
# gente descarta — quase metade do tempo de espera gasto em algo que nunca
# chega à tela. Desligar não é opção ("Reasoning is mandatory for this
# endpoint", HTTP 400), mas baixar o esforço é.
#
# `sort: throughput` porque o OpenRouter é um roteador: ele escolhe entre
# vários provedores de upstream por trás do mesmo nome de modelo, e sem pedir
# nada ele pode cair num lento. Foi o que fez a mesma chamada ora responder em
# 2s, ora passar de um minuto.
_EXTRA_OPENROUTER = {"reasoning": {"effort": "low"}, "provider": {"sort": "throughput"}}

# rótulo -> (atributo com a(s) chave(s), base URL OpenAI-compatible, atributo
# com o modelo, corpo extra). O Gemini não está aqui: tem formato próprio de
# requisição.
#
# A ORDEM é a ordem de tentativa dos saudáveis, e ela importa: o orçamento da
# rotação é gasto do primeiro para o último, então quem responde mais rápido
# vem antes. Os tempos são medidos com o pedido do roadmap em produção.
_OPENAI_COMPATIBLE = [
    ("Groq", "groq_api_key", "https://api.groq.com/openai/v1", "groq_model", {}),
    ("Mistral", "mistral_api_key", "https://api.mistral.ai/v1", "mistral_model", {}),
    ("Cerebras", "cerebras_api_key", "https://api.cerebras.ai/v1", "cerebras_model", {}),
    (
        "OpenRouter",
        "openrouter_api_key",
        "https://openrouter.ai/api/v1",
        "openrouter_model",
        _EXTRA_OPENROUTER,
    ),
]


def _text_candidates() -> list[_Candidate]:
    candidates: list[_Candidate] = []

    gemini_keys = _keys(settings.gemini_api_key)
    for index, key in enumerate(gemini_keys):
        candidates.append(
            _Candidate(
                _named("Gemini", index, len(gemini_keys)),
                # captura por argumento default: sem isso toda lambda fecharia
                # sobre o último valor do laço e todas usariam a mesma chave.
                lambda sp, up, schema, key=key: _call_gemini(sp, up, schema, key),
            )
        )

    for provider, key_attr, base_url, model_attr, extra in _OPENAI_COMPATIBLE:
        keys = _keys(getattr(settings, key_attr, "") or "")
        model = getattr(settings, model_attr)
        for index, key in enumerate(keys):
            candidates.append(
                _Candidate(
                    _named(provider, index, len(keys)),
                    # O schema chega aqui também. Ele era descartado (`_schema`)
                    # porque estes provedores não aceitam schema na requisição —
                    # mas aceitam no texto, e sem ele cada modelo inventa os
                    # próprios nomes de chave.
                    lambda sp, up, schema, key=key, base_url=base_url, model=model, extra=extra: (
                        _call_openai_compatible(base_url, model, sp, up, key, schema, extra)
                    ),
                )
            )
    return candidates


def _media_candidates(media_bytes: bytes, mime_type: str) -> list[_Candidate]:
    """Só Gemini. Nenhum dos fallbacks OpenAI-compatible tem, nas
    configurações deste app, um modelo com visão confirmada — então este
    caminho fica deliberadamente mais estreito em vez de chutar."""
    candidates: list[_Candidate] = []
    gemini_keys = _keys(settings.gemini_api_key)
    for index, key in enumerate(gemini_keys):
        candidates.append(
            _Candidate(
                _named("Gemini", index, len(gemini_keys)),
                lambda sp, up, schema, key=key: _call_gemini_with_media(
                    sp, up, media_bytes, mime_type, schema, key
                ),
            )
        )
    return candidates


def _attempt_order(candidates: list[_Candidate]) -> list[_Candidate]:
    """Saudáveis primeiro, na ordem configurada; depois os em cooldown, o que
    recupera antes na frente. Resfriado é rebaixado, nunca removido."""
    ready = [c for c in candidates if _cooldown_of(c.name) is None]
    cooling = [(c, _cooldowns[c.name].until) for c in candidates if _cooldown_of(c.name) is not None]
    cooling.sort(key=lambda pair: pair[1])
    return ready + [candidate for candidate, _ in cooling]


def _as_failure(exc: Exception) -> Optional[_CandidateFailed]:
    """Normaliza toda forma de um candidato falhar em uma decisão de rotação.
    Devolve None para o que não reconhece — isso é bug no nosso código, não
    problema do provedor, e não pode ser engolido como "tenta o próximo"."""
    if isinstance(exc, _CandidateFailed):
        return exc
    if isinstance(exc, (httpx.TimeoutException, httpx.RequestError, TimeoutError)):
        # `TimeoutError` é o que `asyncio.wait_for` levanta quando o orçamento
        # da rotação acaba durante a tentativa — do ponto de vista do
        # candidato é a mesma coisa que não ter respondido a tempo.
        return _CandidateFailed(TRANSIENT, "não respondeu a tempo")
    if isinstance(exc, (KeyError, IndexError, ValueError)):
        # ValueError cobre json.JSONDecodeError: o provedor respondeu algo
        # inutilizável. Cooldown curto — costuma ser o modelo tendo um mau
        # momento, não a conta.
        return _CandidateFailed(TRANSIENT, "resposta em formato inesperado")
    return None


async def _run_rotation(
    candidates: list[_Candidate],
    invoke: Callable[[_Candidate], Awaitable[Any]],
    on_success: Optional[Callable[[_Candidate, Any], Awaitable[None]]] = None,
    budget: float = _BUDGET,
    per_attempt: Optional[float] = None,
) -> tuple[Any, list[str]]:
    """Tenta cada candidato em ordem, registra por que cada um falhou e
    devolve o primeiro sucesso. Não levanta em falha de provedor — devolve
    (None, falhas) para o chamador escolher a própria mensagem.

    A rotação inteira cabe em `budget` segundos: cada tentativa recebe o que
    sobrou, e quando não sobra o bastante a rotação para. Ver `_BUDGET`.
    """
    failures: list[str] = []
    # O relógio monotônico, e não o de parede: um ajuste de horário no meio da
    # rotação encurtaria ou esticaria o orçamento sem que nada tivesse mudado.
    fim = time.monotonic() + budget
    ordem = _attempt_order(candidates)
    for posicao, candidate in enumerate(ordem):
        restante = fim - time.monotonic()
        if restante < _MIN_ATTEMPT:
            # Parar aqui é o que transforma um 502 mudo em uma resposta. Os
            # candidatos que sobraram entram na mensagem: sem isso, "todos
            # falharam" seria mentira sobre quem nem chegou a ser tentado.
            nao_tentados = len(ordem) - posicao
            failures.append(
                f"{nao_tentados} candidato(s) sem tempo de serem tentados "
                f"dentro de {budget}s"
            )
            break
        # Teto por tentativa, quando quem chama pede. Sem ele cada tentativa
        # recebe TODO o tempo que sobrou, e um provedor lento sozinho esgota o
        # orçamento: medido em produção no treino de idioma, o Gemini ficou
        # 50s sem responder e os outros quatro provedores nem foram tentados —
        # a pessoa esperou 56s por dois exercícios. Opcional porque a leitura
        # de currículo manda o PDF inteiro e pode precisar do tempo todo.
        limite = min(restante, per_attempt) if per_attempt else restante
        try:
            result = await asyncio.wait_for(invoke(candidate), timeout=limite)
        except Exception as exc:  # noqa: BLE001 — relançado abaixo se não for falha de provedor
            failure = _as_failure(exc)
            if failure is None:
                raise
            await _mark_unavailable_async(candidate.name, failure)
            failures.append(f"{candidate.name}: {failure.detail}")
        else:
            await _mark_available_async(candidate.name)
            if on_success is not None:
                await on_success(candidate, result)
            return result, failures
    return None, failures


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------


@dataclass
class AiResult:
    """O que voltou, e de quem — `pathr_ai_job` audita as duas coisas."""

    content: dict
    provider: str
    model: str
    tokens: int
    latency_ms: int


_NO_PROVIDER = (
    "Nenhum provedor de IA configurado — adicione GEMINI_API_KEY (ou GROQ_API_KEY/"
    "OPENROUTER_API_KEY/MISTRAL_API_KEY/CEREBRAS_API_KEY) no .env.local."
)


def _model_for(provider_name: str) -> str:
    """O modelo por trás de um rótulo de candidato, para a auditoria.
    "Gemini #2" e "Gemini" usam o mesmo modelo, chaves diferentes."""
    base = provider_name.split(" #")[0]
    if base == "Gemini":
        return _GEMINI_MODEL
    for provider, _key_attr, _base_url, model_attr, _extra in _OPENAI_COMPATIBLE:
        if provider == base:
            return getattr(settings, model_attr, "")
    return ""


async def _rotate(candidates: list[_Candidate], system_prompt: str, user_prompt: str,
                  gemini_schema: Optional[dict], empty_message: str,
                  per_attempt: Optional[float] = None) -> AiResult:
    if not candidates:
        raise AiProviderError(empty_message)

    # A cota gratuita dos provedores é do app inteiro. Contar aqui, no ponto
    # por onde TODA chamada ao modelo passa, é o que impede uma rota nova de
    # esquecer o limite — e uma pessoa gerando quiz em laço de derrubar a IA
    # de todos. Ver services/limites.py.
    from app.database import get_supabase
    from app.services.limites import consumir_ia

    consumir_ia(get_supabase)

    winner: dict[str, Any] = {}

    async def record(candidate: _Candidate, result: tuple[dict, int]) -> None:
        _content, tokens = result
        winner["name"] = candidate.name
        winner["tokens"] = tokens
        await _log_usage_async(candidate.name, tokens)

    # Lê o cooldown gravado ANTES de decidir a ordem — é isto que faz uma cota
    # estourada continuar valendo depois de um restart do processo.
    await _refresh_cooldowns_async()
    started = _now()
    result, failures = await _run_rotation(
        candidates,
        lambda candidate: candidate.call(system_prompt, user_prompt, gemini_schema),
        on_success=record,
        per_attempt=per_attempt,
    )
    latency_ms = int((_now() - started).total_seconds() * 1000)

    if result is not None:
        content, _tokens = result
        name = winner.get("name", "")
        return AiResult(
            content=content,
            provider=name,
            model=_model_for(name),
            tokens=int(winner.get("tokens") or 0),
            latency_ms=latency_ms,
        )

    if len(candidates) == 1 and failures:
        # Um provedor só configurado — mantém a mensagem específica em vez do
        # "todos os provedores", que soaria estranho para um.
        raise AiProviderError(_sentence(failures[0].split(": ", 1)[1]))
    raise AiProviderError("Todos os provedores de IA falharam agora — " + "; ".join(failures) + ".")


async def generate_json(
    system_prompt: str,
    user_prompt: str,
    gemini_schema: Optional[dict] = None,
    per_attempt_timeout: Optional[float] = None,
    rapido: bool = False,
) -> AiResult:
    """Tenta cada candidato configurado em ordem, rotacionando na falha.

    `rapido`: resposta sem raciocínio prévio, para conversa curta. Só o Gemini
    tem como desligar; os outros respondem como sempre.

    `gemini_schema` (o dialeto de schema do próprio Gemini) só é usado na
    chamada ao Gemini; os outros ficam com o modo JSON solto mais o texto do
    prompt, que já descreve o formato.

    `per_attempt_timeout` limita cada candidato, para que um lento não gaste o
    orçamento inteiro sozinho. Sem ele, cada tentativa usa o que sobrar.
    """
    marca = _rapido.set(rapido)
    try:
        return await _rotate(
            _text_candidates(), system_prompt, user_prompt, gemini_schema, _NO_PROVIDER,
            per_attempt=per_attempt_timeout,
        )
    finally:
        _rapido.reset(marca)


async def generate_json_with_media(
    system_prompt: str,
    user_prompt: str,
    media_bytes: bytes,
    mime_type: str,
    gemini_schema: Optional[dict] = None,
) -> AiResult:
    """Mesmo contrato do generate_json, mais um arquivo que o modelo realmente
    lê (PDF, imagem). É o caminho da leitura de currículo."""
    return await _rotate(
        _media_candidates(media_bytes, mime_type),
        system_prompt,
        user_prompt,
        gemini_schema,
        "Nenhum provedor de IA com visão configurado — adicione GEMINI_API_KEY no .env.local.",
    )


def provider_status() -> list[dict]:
    """Estado de cada candidato configurado, para o painel de operação.
    Nunca devolve a chave, só o rótulo."""
    _load_cooldowns()
    status: list[dict] = []
    for candidate in _text_candidates():
        cooldown = _cooldown_of(candidate.name)
        status.append(
            {
                "provider": candidate.name,
                "model": _model_for(candidate.name),
                "available": cooldown is None,
                "until": cooldown.until.isoformat() if cooldown else None,
                "reason": cooldown.reason if cooldown else None,
            }
        )
    return status


def configured_provider_count() -> int:
    return len(_text_candidates())
