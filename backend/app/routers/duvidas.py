"""O "Perguntar": conversas curtas com o tutor, no contexto da tela.

- `POST /duvidas` — abre uma dúvida (contexto + pergunta) e devolve a conversa
  já com a explicação.
- `POST /duvidas/{id}/mensagens` — continua a conversa.
- `POST /duvidas/{id}/entendeu` — a resposta ao "ficou claro?". "Ainda não"
  pede outra explicação, de outro jeito.
- `GET  /duvidas?contexto_tipo=&contexto_ref=` — as últimas dúvidas daquele
  contexto, para a conversa não sumir ao reabrir a tela.

Toda dúvida entra na base de conhecimento da conta — inclusive quando a IA
falha: a pergunta foi feita, e isso já diz o que a pessoa não sabe.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError
from app.database import get_supabase
from app.deps import get_current_user
from app.services import conhecimento, duvidas

router = APIRouter(prefix="/duvidas", tags=["dúvidas"])

# Uma conversa é dúvida rápida. Passou disso, é assunto para estudo, não chat.
_MAX_FALAS = 40
_FECHAMENTO = (
    "Ótimo! Esse tema fica guardado na sua base de conhecimento e volta nas "
    "atividades e nos quizzes da sua trilha, para fixar."
)

TipoDeContexto = Literal["laboratorio", "atividade", "quiz", "material", "modulo", "geral"]


class Abrir(BaseModel):
    contexto_tipo: TipoDeContexto = "geral"
    contexto_ref: Optional[str] = Field(default=None, max_length=64)
    trecho: Optional[str] = Field(default=None, max_length=1500)
    pergunta: str = Field(min_length=3, max_length=2000)


class Falar(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class Retorno(BaseModel):
    entendeu: bool


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mensagens(supabase: Client, thread_id: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_doubt_message").select("*")
        .eq("thread_id", thread_id).order("created_at").limit(_MAX_FALAS + 5).execute().data
        or []
    )


def _publica(thread: dict[str, Any], mensagens: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(thread["id"]),
        "contexto_tipo": thread.get("context_kind"),
        "contexto_titulo": thread.get("context_title"),
        "conceito": thread.get("concept"),
        "status": thread.get("status"),
        "entendeu": thread.get("understood"),
        "criada_em": thread.get("created_at"),
        "mensagens": [
            {
                "id": str(m["id"]),
                "papel": "pessoa" if m.get("role") == "user" else "tutor",
                "texto": m.get("content") or "",
                "criada_em": m.get("created_at"),
            }
            for m in mensagens
        ],
    }


def _falar(supabase: Client, thread_id: str, user_id: str, role: str, conteudo: str) -> dict[str, Any]:
    return (
        supabase.table("pathr_doubt_message")
        .insert({"thread_id": thread_id, "user_id": user_id, "role": role, "content": conteudo})
        .execute()
        .data[0]
    )


def _da_pessoa(supabase: Client, user_id: str, thread_id: str) -> dict[str, Any]:
    nao_achou = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dúvida não encontrada.")
    try:
        uuid.UUID(thread_id)
    except ValueError:
        raise nao_achou
    linhas = (
        supabase.table("pathr_doubt_thread").select("*")
        .eq("id", thread_id).eq("user_id", user_id).limit(1).execute().data
        or []
    )
    if not linhas:
        raise nao_achou
    return linhas[0]


def _registrar(supabase: Client, user_id: str, thread: dict[str, Any], conceito: str, detalhe: str) -> None:
    conhecimento.registrar(
        supabase, user_id, "duvida", conceito or detalhe[:120],
        detalhe=detalhe, tag_id=thread.get("tag_id"), node_id=thread.get("node_id"), ref_id=str(thread["id"]),
    )


async def _explicar(supabase: Client, user_id: str, thread: dict[str, Any]) -> dict[str, Any]:
    """Pede a explicação para a conversa como está e grava a fala do tutor."""
    try:
        contexto = duvidas.resolver_contexto(supabase, user_id, thread["context_kind"], thread.get("context_ref"))
        texto_do_contexto = contexto.texto
    except HTTPException:
        # O conteúdo sumiu (exemplo apagado, trilha refeita): a conversa segue
        # com o que se sabe dele.
        texto_do_contexto = f"Conteúdo: {thread.get('context_title') or 'dúvida de estudo'}"
    resposta, conceito, _modelo = await duvidas.responder(
        texto_do_contexto, thread.get("context_excerpt"), _mensagens(supabase, str(thread["id"]))
    )
    _falar(supabase, str(thread["id"]), user_id, "assistant", resposta)
    mudancas = {"updated_at": _agora(), "status": "aberta"}
    if conceito and not thread.get("concept"):
        mudancas["concept"] = conceito
    supabase.table("pathr_doubt_thread").update(mudancas).eq("id", str(thread["id"])).execute()
    return {**thread, **mudancas}


@router.get("")
def listar(
    contexto_tipo: TipoDeContexto = "geral",
    contexto_ref: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    consulta = (
        supabase.table("pathr_doubt_thread").select("*")
        .eq("user_id", user_id).eq("context_kind", contexto_tipo)
    )
    if contexto_ref:
        consulta = consulta.eq("context_ref", contexto_ref[:64])
    threads = consulta.order("created_at", desc=True).limit(5).execute().data or []
    return [_publica(t, _mensagens(supabase, str(t["id"]))) for t in threads]


@router.post("", status_code=status.HTTP_201_CREATED)
async def abrir(
    payload: Abrir,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    contexto = duvidas.resolver_contexto(supabase, user_id, payload.contexto_tipo, payload.contexto_ref)
    pergunta = payload.pergunta.strip()
    thread = (
        supabase.table("pathr_doubt_thread")
        .insert({
            "user_id": user_id,
            "context_kind": payload.contexto_tipo,
            "context_ref": payload.contexto_ref if payload.contexto_tipo != "geral" else None,
            "context_title": contexto.titulo,
            "context_excerpt": (payload.trecho or "").strip()[:1500] or None,
            "node_id": contexto.node_id,
            "tag_id": contexto.tag_id,
        })
        .execute()
        .data[0]
    )
    _falar(supabase, str(thread["id"]), user_id, "user", pergunta)
    try:
        thread = await _explicar(supabase, user_id, thread)
    except AiProviderError:
        # A IA falhou, a dúvida não: ela entra na base mesmo sem explicação.
        _registrar(supabase, user_id, thread, "", pergunta)
        raise
    _registrar(supabase, user_id, thread, thread.get("concept") or "", pergunta)
    return _publica(thread, _mensagens(supabase, str(thread["id"])))


@router.post("/{thread_id}/mensagens")
async def continuar(
    thread_id: str,
    payload: Falar,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    thread = _da_pessoa(supabase, user_id, thread_id)
    if len(_mensagens(supabase, thread_id)) >= _MAX_FALAS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta conversa ficou longa. Abra uma nova dúvida para seguir.",
        )
    texto = payload.texto.strip()
    _falar(supabase, thread_id, user_id, "user", texto)
    _registrar(supabase, user_id, thread, thread.get("concept") or "", texto)
    thread = await _explicar(supabase, user_id, thread)
    return _publica(thread, _mensagens(supabase, thread_id))


@router.post("/{thread_id}/entendeu")
async def entendeu(
    thread_id: str,
    payload: Retorno,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    thread = _da_pessoa(supabase, user_id, thread_id)
    if payload.entendeu:
        # Entendeu a explicação — mas entender não é dominar: o tema continua
        # pendente na base até voltar numa atividade ou quiz e ser acertado.
        mudancas = {"status": "entendida", "understood": True, "resolved_at": _agora(), "updated_at": _agora()}
        supabase.table("pathr_doubt_thread").update(mudancas).eq("id", thread_id).execute()
        _falar(supabase, thread_id, user_id, "assistant", _FECHAMENTO)
        return _publica({**thread, **mudancas}, _mensagens(supabase, thread_id))

    # Não entendeu: o tema pesa mais na base, e vem outra explicação.
    supabase.table("pathr_doubt_thread").update({"understood": False}).eq("id", thread_id).execute()
    _falar(supabase, thread_id, user_id, "user", "Ainda não entendi.")
    _registrar(supabase, user_id, thread, thread.get("concept") or "", "Não entendeu a explicação.")
    thread = await _explicar(supabase, user_id, {**thread, "understood": False})
    return _publica(thread, _mensagens(supabase, thread_id))
