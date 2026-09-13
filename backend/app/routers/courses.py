"""Cursos com certificado, escolhidos pelo que a pessoa quer aprender.

O catálogo e a ordenação moram em services/courses.py. Aqui só se junta o que
diz o que a pessoa quer: as tags (meta e "quero aprender"), os módulos ainda
abertos do roadmap e a frase do objetivo.
"""

from typing import Any

from fastapi import APIRouter, Depends
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.routers.tags import _objetivo_de, list_mine
from app.services import courses

router = APIRouter(prefix="/courses", tags=["cursos"])


@router.get("")
def list_courses(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    minhas = list_mine(current_user, supabase)
    perfil = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
        or [{}]
    )[0]
    objetivo = " ".join(
        [_objetivo_de(perfil), *[str(meta) for meta in (perfil.get("goals") or [])]]
    ).strip()

    cursos = courses.recomendar(minhas, _slugs_do_roadmap(supabase, user_id), objetivo)
    return {
        "cursos": cursos,
        "conferido_em": courses.CONFERIDO_EM,
        # A tela usa para dizer POR QUE está vazia: sem nada pedido, o caminho
        # é configurar o objetivo; com pedido e sem curso, é falta de catálogo.
        "tem_pedido": bool(objetivo) or any(tag["is_target"] for tag in minhas),
    }


def _slugs_do_roadmap(supabase: Client, user_id: str) -> list[str]:
    """As tags dos módulos ainda por fazer no plano principal."""
    planos = (
        supabase.table("pathr_roadmap")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_primary", True)
        .limit(1)
        .execute()
        .data
    )
    if not planos:
        return []
    nodes: list[dict[str, Any]] = (
        supabase.table("pathr_roadmap_node")
        .select("tag_ids,status")
        .eq("roadmap_id", str(planos[0]["id"]))
        .execute()
        .data
        or []
    )
    tag_ids = {
        str(tag_id)
        for node in nodes
        if node.get("status") not in ("done", "skipped")
        for tag_id in (node.get("tag_ids") or [])
    }
    if not tag_ids:
        return []
    tags = supabase.table("pathr_tag").select("slug").in_("id", list(tag_ids)).execute().data or []
    return [str(tag["slug"]) for tag in tags]
