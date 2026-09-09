"""Catálogo de tecnologias e as competências do usuário.

Duas coisas diferentes com o mesmo vocabulário: `pathr_tag` é o catálogo
GLOBAL (uma "React" para todo mundo) e `pathr_user_tag` é o que uma pessoa
sabe sobre cada uma. A tela de Skills mistura as duas — lista o catálogo e
marca o que é seu — e é por isso que `GET /tags/mine` devolve as duas juntas
em vez de obrigar o frontend a cruzar dois arrays por id.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services.tag_catalog import TagCatalog, normalize_category

router = APIRouter(prefix="/tags", tags=["competências"])


class UserTagUpsert(BaseModel):
    # Um dos dois: `tag_id` quando veio do catálogo, `name` quando a pessoa
    # digitou algo que talvez ainda não exista.
    tag_id: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=60)
    category: Optional[str] = Field(default=None, max_length=30)
    proficiency: int = Field(default=0, ge=0, le=5)
    is_target: bool = False


class UserTagPatch(BaseModel):
    proficiency: Optional[int] = Field(default=None, ge=0, le=5)
    is_target: Optional[bool] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("")
def list_catalog(
    q: str = "",
    category: str = "",
    limit: int = 200,
    supabase: Client = Depends(get_supabase),
    _current_user: dict = Depends(get_current_user),
):
    """Catálogo global, para busca e autocomplete. Ordenado por popularidade:
    quem digita "j" quer "Java" ou "JavaScript" antes de "Jenkins"."""
    query = supabase.table("pathr_tag").select("id,slug,name,category,color,icon,popularity")
    if category:
        query = query.eq("category", normalize_category(category))
    if q.strip():
        # ilike cobre o começo e o meio do nome; os apelidos ficam de fora
        # aqui porque a busca é interativa e o casamento por apelido é papel
        # da importação de currículo, não da digitação.
        query = query.ilike("name", f"%{q.strip()}%")
    return (
        query.order("popularity", desc=True)
        .order("name")
        .limit(max(1, min(limit, 500)))
        .execute()
        .data
        or []
    )


@router.get("/mine")
def list_mine(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """As competências do usuário, já com o nome e a categoria da tag."""
    rows = (
        supabase.table("pathr_user_tag")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
        or []
    )
    if not rows:
        return []

    tag_ids = list({str(row["tag_id"]) for row in rows})
    tags = (
        supabase.table("pathr_tag")
        .select("id,slug,name,category,color,icon")
        .in_("id", tag_ids)
        .execute()
        .data
        or []
    )
    by_id = {str(tag["id"]): tag for tag in tags}

    merged = []
    for row in rows:
        tag = by_id.get(str(row["tag_id"]))
        if not tag:
            # Tag apagada do catálogo — a linha do usuário perdeu o
            # referente. Omitir é melhor que mostrar uma competência sem nome.
            continue
        merged.append(
            {
                "id": str(row["id"]),
                "tag_id": str(row["tag_id"]),
                "slug": tag["slug"],
                "name": tag["name"],
                "category": tag["category"],
                "color": tag.get("color"),
                "proficiency": int(row.get("proficiency") or 0),
                "confidence": float(row.get("confidence") or 0),
                "is_target": bool(row.get("is_target")),
                "source": row.get("source"),
                "last_assessed_at": row.get("last_assessed_at"),
            }
        )
    merged.sort(key=lambda item: (-item["proficiency"], item["name"]))
    return merged


@router.post("/mine", status_code=status.HTTP_201_CREATED)
def upsert_mine(
    payload: UserTagUpsert,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Adiciona ou atualiza uma competência.

    `source='manual'` e `confidence=0.8`: quando a própria pessoa marca o
    nível, o sistema confia mais do que no que o currículo dizia (0.4) e menos
    do que num quiz respondido, que é a única evidência de verdade.
    """
    user_id = str(current_user["id"])
    if payload.tag_id:
        tag_rows = (
            supabase.table("pathr_tag").select("*").eq("id", payload.tag_id).limit(1).execute().data
        )
        if not tag_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecnologia não encontrada.")
        tag = tag_rows[0]
    elif payload.name:
        tag = TagCatalog(supabase).load().resolve(payload.name, payload.category or "")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Informe tag_id ou name."
        )

    fields: dict[str, Any] = {
        "proficiency": payload.proficiency,
        "is_target": payload.is_target,
        "source": "manual",
        "confidence": 0.8,
        "last_assessed_at": _now().isoformat(),
    }
    existing = (
        supabase.table("pathr_user_tag")
        .select("id")
        .eq("user_id", user_id)
        .eq("tag_id", str(tag["id"]))
        .limit(1)
        .execute()
        .data
    )
    if existing:
        row = (
            supabase.table("pathr_user_tag")
            .update(fields)
            .eq("id", existing[0]["id"])
            .execute()
            .data[0]
        )
    else:
        row = (
            supabase.table("pathr_user_tag")
            .insert({"user_id": user_id, "tag_id": str(tag["id"]), **fields})
            .execute()
            .data[0]
        )
    return {"id": str(row["id"]), "tag_id": str(tag["id"]), "slug": tag["slug"], "name": tag["name"],
            "proficiency": row["proficiency"], "is_target": row["is_target"]}


@router.patch("/mine/{user_tag_id}")
def patch_mine(
    user_tag_id: str,
    payload: UserTagPatch,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    update = payload.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para atualizar.")
    if "proficiency" in update:
        update["confidence"] = 0.8
        update["source"] = "manual"
        update["last_assessed_at"] = _now().isoformat()
    rows = (
        supabase.table("pathr_user_tag")
        .update(update)
        .eq("id", user_tag_id)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competência não encontrada.")
    return rows[0]


@router.delete("/mine/{user_tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mine(
    user_tag_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Tira a competência do perfil. A tag global continua existindo — ela é
    de todo mundo."""
    supabase.table("pathr_user_tag").delete().eq("id", user_tag_id).eq(
        "user_id", str(current_user["id"])
    ).execute()
