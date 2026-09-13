"""Cursos com certificado, escolhidos pelo que a pessoa quer aprender.

O catálogo e a ordenação moram em services/courses.py. Aqui só se junta o que
diz o que a pessoa quer: as tags marcadas como meta, os módulos ainda
abertos do roadmap e a frase do objetivo. E o que a pessoa já possui: o
certificado marcado aqui aparece em Perfil e tags.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.routers.tags import _objetivo_de, list_mine
from app.services import courses

router = APIRouter(prefix="/courses", tags=["cursos"])


def _meus(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_user_course")
        .select("course_id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


@router.get("/mine")
def my_courses(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Os cursos com certificado que a pessoa marcou como "já possuo", do mais
    recente ao mais antigo. Curso que saiu do catálogo não aparece."""
    saida = []
    for linha in _meus(supabase, str(current_user["id"])):
        curso = courses.por_id(str(linha["course_id"]))
        if curso:
            saida.append({**courses.resumido(curso), "possuido_em": linha.get("created_at")})
    return saida


def _curso_ou_404(course_id: str) -> courses.Curso:
    curso = courses.por_id(course_id)
    if not curso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso não encontrado.")
    return curso


@router.put("/mine/{course_id}")
def mark_owned(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Marca como "já possuo". Idempotente: marcar de novo não duplica."""
    curso = _curso_ou_404(course_id)
    user_id = str(current_user["id"])
    existente = (
        supabase.table("pathr_user_course")
        .select("course_id,created_at")
        .eq("user_id", user_id)
        .eq("course_id", curso.id)
        .limit(1)
        .execute()
        .data
    )
    linha = existente[0] if existente else (
        supabase.table("pathr_user_course").insert({"user_id": user_id, "course_id": curso.id}).execute().data[0]
    )
    return {**courses.resumido(curso), "possuido_em": linha.get("created_at")}


@router.delete("/mine/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def unmark_owned(
    course_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    supabase.table("pathr_user_course").delete().eq("user_id", str(current_user["id"])).eq(
        "course_id", course_id
    ).execute()


@router.get("")
def list_courses(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    todos: bool = False,
):
    """Os cursos do que a pessoa pediu; com `todos`, o catálogo inteiro para buscar."""
    user_id = str(current_user["id"])
    minhas = list_mine(current_user, supabase)
    perfil = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
        or [{}]
    )[0]
    objetivo = " ".join(
        [_objetivo_de(perfil), *[str(meta) for meta in (perfil.get("goals") or [])]]
    ).strip()

    cursos = courses.recomendar(minhas, _slugs_do_roadmap(supabase, user_id), objetivo, todos=todos)
    possuidos = {linha["course_id"] for linha in _meus(supabase, user_id)}
    for curso in cursos:
        curso["possuo"] = curso["id"] in possuidos
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
