"""A base de conhecimento da conta: tudo o que a pessoa ainda não sabe.

## A regra

Nada se perde. Dúvida no "Perguntar", questão errada no quiz, lacuna numa
correção, palavra consultada no idioma, erro no treino: cada uma é a pessoa
dizendo — ou provando — "isto eu não sei". Tudo entra aqui, com de onde veio,
e fica **pendente** até voltar e ser acertado.

## Um tema, não um evento

Errar o mesmo conceito três vezes não cria três linhas: a linha que já existe
ganha `times_seen` e `last_seen_at`, e volta a pendente se já tinha sido
revisada. É a contagem que diz o que mais pesa — o que volta mais vezes vem
primeiro para quem pede assunto (atividades, quiz, busca de material).

## Quem lê

- `services/atividades.py` — a próxima atividade exercita o que está pendente
  no módulo;
- `routers/quizzes.py` — o quiz reescreve como questão o que está pendente
  nas tecnologias dele;
- `routers/library.py` — a busca de material do módulo procura também os
  temas pendentes que ainda não foram buscados.

Tudo aqui é best-effort: perder o registro de um sinal custa uma revisão;
derrubar a correção, a resposta ou a consulta da pessoa custa o trabalho dela.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from supabase import Client

from app.services.review import concept_key

logger = logging.getLogger(__name__)

FONTES = ("duvida", "quiz", "atividade", "explicacao", "palavra", "idioma")
TECNICAS = ("duvida", "quiz", "atividade", "explicacao")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _texto(valor: Any, limite: int) -> str:
    return " ".join(str(valor or "").split())[:limite]


def registrar(
    supabase: Client,
    user_id: str,
    fonte: str,
    conceito: Any,
    *,
    detalhe: Any = None,
    tag_id: Optional[str] = None,
    node_id: Optional[str] = None,
    ref_id: Optional[str] = None,
    idioma: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Registra um sinal de "não sei". Devolve a linha, ou None se não gravou."""
    conceito = _texto(conceito, 300)
    chave = concept_key(conceito)
    if not chave or fonte not in FONTES:
        return None
    try:
        existentes = [
            linha
            for linha in (
                supabase.table("pathr_knowledge_item").select("*")
                .eq("user_id", user_id).eq("concept_key", chave)
                .limit(20).execute().data or []
            )
            if (linha.get("language") or None) == (idioma or None)
        ]
        agora = _agora()
        if existentes:
            linha = existentes[0]
            mudancas: dict[str, Any] = {
                "times_seen": int(linha.get("times_seen") or 1) + 1,
                "last_seen_at": agora,
                "status": "pendente",
                "resolved_at": None,
            }
            # Quem veio sem tecnologia/módulo ganha os do sinal novo: a mesma
            # dúvida perguntada solta e depois errada num quiz de Git fica de Git.
            if tag_id and not linha.get("tag_id"):
                mudancas["tag_id"] = tag_id
            if node_id and not linha.get("node_id"):
                mudancas["node_id"] = node_id
            supabase.table("pathr_knowledge_item").update(mudancas).eq("id", str(linha["id"])).execute()
            return {**linha, **mudancas}
        return (
            supabase.table("pathr_knowledge_item")
            .insert({
                "user_id": user_id,
                "source": fonte,
                "concept": conceito,
                "concept_key": chave,
                "detail": _texto(detalhe, 1000) or None,
                "tag_id": tag_id,
                "node_id": node_id,
                "ref_id": _texto(ref_id, 64) or None,
                "language": idioma,
                "status": "pendente",
                "times_seen": 1,
                "last_seen_at": agora,
            })
            .execute()
            .data[0]
        )
    except Exception:  # noqa: BLE001
        logger.warning("base de conhecimento: não registrei um sinal de %s", fonte, exc_info=True)
        return None


def marcar_revisado(supabase: Client, user_id: str, conceito: Any, idioma: Optional[str] = None) -> None:
    """Acertou de novo o que estava pendente: sai da lista de pendências.

    Não apaga — a história de que a pessoa já tropeçou ali continua valendo,
    e um novo erro reabre a mesma linha.
    """
    chave = concept_key(_texto(conceito, 300))
    if not chave:
        return
    try:
        for linha in (
            supabase.table("pathr_knowledge_item").select("id,language,status")
            .eq("user_id", user_id).eq("concept_key", chave).limit(20).execute().data or []
        ):
            if (linha.get("language") or None) == (idioma or None) and linha.get("status") == "pendente":
                supabase.table("pathr_knowledge_item").update(
                    {"status": "revisado", "resolved_at": _agora()}
                ).eq("id", str(linha["id"])).execute()
    except Exception:  # noqa: BLE001
        logger.warning("base de conhecimento: não marquei como revisado", exc_info=True)


def pendentes(
    supabase: Client,
    user_id: str,
    *,
    tag_ids: Iterable[str] = (),
    node_id: Optional[str] = None,
    fontes: Iterable[str] = TECNICAS,
    so_nao_buscados: bool = False,
    limite: int = 6,
) -> list[dict[str, Any]]:
    """O que está pendente neste módulo ou nestas tecnologias, o que mais pesa primeiro.

    "Mais pesa" é o que voltou mais vezes e, empatado, o mais recente.
    """
    tags = {str(t) for t in tag_ids if t}
    fontes = set(fontes)
    try:
        linhas = (
            supabase.table("pathr_knowledge_item").select("*")
            .eq("user_id", user_id).eq("status", "pendente")
            .order("last_seen_at", desc=True).limit(200).execute().data
            or []
        )
    except Exception:  # noqa: BLE001
        return []
    escolhidas = [
        linha for linha in linhas
        if linha.get("source") in fontes
        and ((node_id and str(linha.get("node_id")) == str(node_id)) or str(linha.get("tag_id")) in tags)
        and not (so_nao_buscados and linha.get("searched_at"))
    ]
    escolhidas.sort(key=lambda l: (int(l.get("times_seen") or 1), str(l.get("last_seen_at") or "")), reverse=True)
    return escolhidas[:limite]


def marcar_buscado(supabase: Client, item_id: str) -> None:
    try:
        supabase.table("pathr_knowledge_item").update({"searched_at": _agora()}).eq("id", item_id).execute()
    except Exception:  # noqa: BLE001
        logger.warning("base de conhecimento: não marquei a busca", exc_info=True)
