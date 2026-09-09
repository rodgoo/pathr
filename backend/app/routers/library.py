"""Biblioteca: material curado e o progresso do usuário nele.

`pathr_resource` é um catálogo GLOBAL, como as tags — um vídeo bom sobre JPA
serve para todo mundo que estuda JPA, e curar por usuário multiplicaria o
mesmo trabalho. O que é por pessoa mora em `pathr_user_resource`: salvo, em
andamento, concluído, nota, minutos gastos.

A curadoria é filtrada pelas tags do usuário, e é isso que faz a biblioteca
parecer pessoal sem ser duplicada.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services.progress import log_activity

router = APIRouter(prefix="/library", tags=["biblioteca"])


class ResourceProgress(BaseModel):
    status: str = Field(default="saved", pattern="^(saved|in_progress|done|dismissed)$")
    progress_pct: int = Field(default=0, ge=0, le=100)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    minutes_spent: int = Field(default=0, ge=0, le=600)
    notes: Optional[str] = Field(default=None, max_length=2000)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_tag_ids(supabase: Client, user_id: str) -> list[str]:
    rows = (
        supabase.table("pathr_user_tag")
        .select("tag_id")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    return [str(row["tag_id"]) for row in rows]


@router.get("")
def list_resources(
    q: str = "",
    kind: str = "",
    language: str = "",
    only_mine: bool = True,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Material curado, por padrão filtrado pelas tags do usuário.

    `only_mine=false` abre o catálogo inteiro — útil para procurar algo que
    ainda não está no plano.
    """
    user_id = str(current_user["id"])
    query = supabase.table("pathr_resource").select("*")

    if kind:
        query = query.eq("kind", kind)
    if language:
        query = query.eq("language", language)
    if q.strip():
        query = query.ilike("title", f"%{q.strip()}%")
    if only_mine:
        tag_ids = _user_tag_ids(supabase, user_id)
        if not tag_ids:
            return []
        # `overlaps` no uuid[] — o recurso serve se citar QUALQUER tag do
        # usuário. Exigir todas devolveria quase nada.
        query = query.overlaps("tag_ids", tag_ids)

    resources = (
        query.order("quality_score", desc=True).limit(max(1, min(limit, 100))).execute().data or []
    )
    if not resources:
        return []

    progress = (
        supabase.table("pathr_user_resource")
        .select("*")
        .eq("user_id", user_id)
        .in_("resource_id", [str(item["id"]) for item in resources])
        .execute()
        .data
        or []
    )
    by_resource = {str(row["resource_id"]): row for row in progress}

    return [
        {
            **resource,
            "user_status": (by_resource.get(str(resource["id"])) or {}).get("status"),
            "user_progress_pct": (by_resource.get(str(resource["id"])) or {}).get("progress_pct", 0),
            "user_rating": (by_resource.get(str(resource["id"])) or {}).get("rating"),
        }
        for resource in resources
    ]


@router.put("/{resource_id}/progress")
def set_progress(
    resource_id: str,
    payload: ResourceProgress,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Salva, retoma ou conclui um material."""
    user_id = str(current_user["id"])
    resource = (
        supabase.table("pathr_resource")
        .select("id,title,tag_ids,duration_min")
        .eq("id", resource_id)
        .limit(1)
        .execute()
        .data
    )
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado.")
    resource = resource[0]

    fields: dict[str, Any] = payload.model_dump(exclude_none=True)
    if payload.status == "done":
        fields["progress_pct"] = 100
        fields["completed_at"] = _now().isoformat()

    existing = (
        supabase.table("pathr_user_resource")
        .select("id,status")
        .eq("user_id", user_id)
        .eq("resource_id", resource_id)
        .limit(1)
        .execute()
        .data
    )
    was_done = bool(existing) and existing[0].get("status") == "done"

    if existing:
        row = (
            supabase.table("pathr_user_resource")
            .update(fields)
            .eq("id", existing[0]["id"])
            .execute()
            .data[0]
        )
    else:
        row = (
            supabase.table("pathr_user_resource")
            .insert({"user_id": user_id, "resource_id": resource_id, **fields})
            .execute()
            .data[0]
        )

    # Só registra atividade na PRIMEIRA conclusão: reabrir e marcar de novo
    # não deveria render XP e streak outra vez.
    if payload.status == "done" and not was_done:
        log_activity(
            supabase,
            user=current_user,
            kind="resource_done",
            title=resource.get("title") or "",
            ref_id=resource_id,
            minutes=payload.minutes_spent or int(resource.get("duration_min") or 0),
            tag_ids=[str(tag) for tag in (resource.get("tag_ids") or [])],
        )

    return row


@router.get("/mine")
def my_library(
    status_filter: str = "",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O que o usuário salvou ou começou, com os dados do material junto."""
    query = (
        supabase.table("pathr_user_resource")
        .select("*")
        .eq("user_id", str(current_user["id"]))
    )
    if status_filter:
        query = query.eq("status", status_filter)
    rows = query.order("created_at", desc=True).limit(200).execute().data or []
    if not rows:
        return []

    resources = (
        supabase.table("pathr_resource")
        .select("*")
        .in_("id", [str(row["resource_id"]) for row in rows])
        .execute()
        .data
        or []
    )
    by_id = {str(item["id"]): item for item in resources}
    return [
        {**row, "resource": by_id.get(str(row["resource_id"]))}
        for row in rows
        if by_id.get(str(row["resource_id"]))
    ]
