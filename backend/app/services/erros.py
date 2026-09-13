"""O registro dos erros do servidor que a varredura diária conta.

Cada exceção não tratada vira uma linha em `pathr_error_event`. Três cuidados:

1. **A rota é o molde, não o endereço.** `/relatos/{relato_id}` e não
   `/relatos/6f1c…`: com o id, o mesmo defeito viraria cem erros diferentes, e
   o id é de alguém.
2. **A mensagem sai redigida.** Texto de exceção costuma carregar o valor que
   causou o problema — e-mail, token, consulta com dado de outra pessoa.
3. **Registrar nunca derruba nada.** Se o banco estiver fora (e às vezes é
   justamente esse o erro), a falha do registro fica só no log.
"""

import hashlib
import logging
import re
import traceback
from typing import Any

logger = logging.getLogger("pathr.erros")

_MAX_MENSAGEM = 300

_REDACOES = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "<jwt>"),
    (re.compile(r"\b[A-Za-z0-9_-]{32,}\b"), "<token>"),
    (re.compile(r"\d{5,}"), "<n>"),
)


def redigir(texto: str) -> str:
    for padrao, marcador in _REDACOES:
        texto = padrao.sub(marcador, texto)
    texto = " ".join(texto.split())
    return texto[:_MAX_MENSAGEM]


def local_da_falha(exc: BaseException) -> str | None:
    """O quadro mais fundo que é código NOSSO (app/…), como `arquivo:linha`.

    O último quadro de todos costuma ser da biblioteca (httpx, postgrest), e
    isso não diz onde consertar.
    """
    nosso = None
    for quadro in traceback.extract_tb(exc.__traceback__):
        caminho = quadro.filename.replace("\\", "/")
        if "/app/" in caminho and "/site-packages/" not in caminho:
            # rsplit, e não split: no contêiner o código mora em /app/app/…,
            # e cortar na PRIMEIRA ocorrência daria "app/app/routers/…".
            nosso = f"app/{caminho.rsplit('/app/', 1)[1]}:{quadro.lineno}"
    return nosso


def rota_molde(scope: dict[str, Any]) -> str:
    rota = scope.get("route")
    molde = getattr(rota, "path", None)
    return str(molde) if molde else "(rota desconhecida)"


def impressao(tipo: str, rota: str, local: str | None) -> str:
    return hashlib.sha1(f"{tipo}|{rota}|{local or ''}".encode()).hexdigest()[:16]


def registrar(supabase_factory, metodo: str, scope: dict[str, Any], exc: BaseException) -> None:
    try:
        tipo = type(exc).__name__
        rota = rota_molde(scope)
        local = local_da_falha(exc)
        supabase_factory().table("pathr_error_event").insert(
            {
                "fingerprint": impressao(tipo, rota, local),
                "method": metodo,
                "route": rota,
                "error_type": tipo,
                "message": redigir(str(exc)) or None,
                "location": local,
            }
        ).execute()
    except Exception:  # noqa: BLE001
        logger.warning("não consegui registrar o erro", exc_info=True)


def agrupar(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Um item por defeito (impressão digital), com quantas vezes aconteceu."""
    grupos: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        chave = linha.get("fingerprint") or ""
        quando = str(linha.get("occurred_at") or "")
        grupo = grupos.get(chave)
        if grupo is None:
            grupos[chave] = {
                "fingerprint": chave,
                "tipo": linha.get("error_type"),
                "metodo": linha.get("method"),
                "rota": linha.get("route"),
                "local": linha.get("location"),
                "mensagem": linha.get("message"),
                "ocorrencias": 1,
                "primeira": quando,
                "ultima": quando,
            }
        else:
            grupo["ocorrencias"] += 1
            grupo["primeira"] = min(grupo["primeira"], quando)
            grupo["ultima"] = max(grupo["ultima"], quando)
    return sorted(grupos.values(), key=lambda g: (-g["ocorrencias"], g["rota"] or ""))
