"""A chave que a extensão do navegador usa para falar com a API.

## Por que não o cookie de sessão

A extensão roda em `chrome-extension://…`, outra origem. Mandar o cookie para
lá exigiria afrouxar `SameSite`, e um cookie que atravessa origem é exatamente
a peça que torna CSRF possível — trocaríamos um problema de comodidade por um
de segurança em todo o resto do app.

Então a extensão tem credencial própria: uma chave criada na tela de
Candidaturas, colada nela uma vez e guardada no `chrome.storage` local.

## O que fica no banco

Só o sha256 da chave, como senha. Quem ler a tabela não consegue usar nada, e
a chave em claro aparece uma única vez, na resposta da criação. Perdeu, cria
outra e revoga a antiga — não existe "ver de novo".

Não há `bcrypt` aqui de propósito: a chave são 256 bits de aleatório, não uma
senha escolhida por gente. Ataque de dicionário não se aplica, e o hash rápido
é o certo para algo conferido a cada chamada.

## O alcance da chave

Ela NÃO é uma sessão. Serve para as rotas de `/extensao` e nada mais: ler o
banco de respostas, baixar o currículo, devolver resposta nova. Com ela não se
troca senha, não se apaga conta, não se lê e-mail — o estrago de um vazamento
é o que a extensão já faria, e acaba quando a pessoa revoga.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client

logger = logging.getLogger(__name__)

# O prefixo serve para reconhecimento: colada no lugar errado, dá para ver o
# que é; e um varredor de segredos consegue procurar por ele.
PREFIXO = "pathr_ext_"
MAXIMO_POR_PESSOA = 5


def _hash(chave: str) -> str:
    return hashlib.sha256(chave.strip().encode("utf-8")).hexdigest()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def para_api(linha: dict[str, Any]) -> dict[str, Any]:
    """A chave como a tela a mostra — sem o hash, que não interessa a ninguém."""
    return {
        "id": str(linha.get("id")),
        "nome": linha.get("name") or "Extensão",
        "criada_em": linha.get("created_at"),
        "usada_em": linha.get("last_used_at"),
    }


def listar(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    """As chaves vivas da pessoa, da mais nova para a mais velha."""
    try:
        linhas = (
            supabase.table("pathr_extension_token")
            .select("*")
            .eq("user_id", user_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        logger.warning("não consegui listar as chaves da extensão", exc_info=True)
        return []
    return [para_api(linha) for linha in linhas]


def criar(supabase: Client, user_id: str, nome: str = "Extensão") -> tuple[str, dict[str, Any]]:
    """Cria uma chave e devolve `(chave em claro, linha para a tela)`.

    A chave em claro existe só aqui e na resposta: depois dela, nem o servidor
    consegue reconstruí-la.
    """
    vivas = listar(supabase, user_id)
    if len(vivas) >= MAXIMO_POR_PESSOA:
        # Teto para quem esquece de revogar: chave antiga esquecida é chave que
        # continua valendo, e ninguém audita cinquenta linhas.
        raise ValueError("Você já tem chaves demais. Revogue uma antes de criar outra.")

    chave = PREFIXO + secrets.token_urlsafe(32)
    linha = {
        "user_id": user_id,
        "token_hash": _hash(chave),
        "name": " ".join(str(nome or "Extensão").split())[:80] or "Extensão",
    }
    gravada = supabase.table("pathr_extension_token").insert(linha).execute().data[0]
    return chave, para_api(gravada)


def revogar(supabase: Client, user_id: str, chave_id: str) -> bool:
    """Desliga uma chave. `user_id` no filtro: ninguém revoga a chave de outro."""
    linhas = (
        supabase.table("pathr_extension_token")
        .update({"revoked_at": _agora()})
        .eq("id", chave_id)
        .eq("user_id", user_id)
        .is_("revoked_at", "null")
        .execute()
        .data
        or []
    )
    return bool(linhas)


def dono(supabase: Client, chave: Optional[str]) -> Optional[dict[str, Any]]:
    """De quem é esta chave — ou `None` se não vale mais.

    Marca `last_used_at` de passagem: é com isso que a tela mostra "usada há
    dois dias", e é assim que a pessoa reconhece a chave de um navegador que
    não usa mais. Falhar essa marcação não pode derrubar a chamada — é
    informação de conforto, não de autorização.
    """
    if not chave or not chave.startswith(PREFIXO):
        return None

    try:
        linhas = (
            supabase.table("pathr_extension_token")
            .select("id,user_id,revoked_at")
            .eq("token_hash", _hash(chave))
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        logger.warning("não consegui conferir a chave da extensão", exc_info=True)
        return None
    if not linhas or linhas[0].get("revoked_at"):
        return None

    user_id = str(linhas[0]["user_id"])
    try:
        pessoas = (
            supabase.table("pathr_user").select("*").eq("id", user_id).limit(1).execute().data or []
        )
    except Exception:  # noqa: BLE001
        logger.warning("não consegui carregar o dono da chave", exc_info=True)
        return None
    if not pessoas:
        return None

    try:
        supabase.table("pathr_extension_token").update({"last_used_at": _agora()}).eq(
            "id", str(linhas[0]["id"])
        ).execute()
    except Exception:  # noqa: BLE001
        logger.debug("não marquei o uso da chave", exc_info=True)

    return pessoas[0]
