"""A fila de atividades práticas de um módulo.

- `GET  /roadmap/nodes/{id}/atividades` — a atividade aberta (se houver) e as
  já feitas, com nota.
- `POST /roadmap/nodes/{id}/atividades/proxima` — a próxima. Se ainda há uma
  aberta, devolve ELA em vez de gerar outra: dois cliques (ou duas abas) não
  podem gastar duas chamadas de IA nem empilhar tarefas sem resposta.

A correção continua em `POST /explanations` (modo `atividade`, com o
`exercise_id`): é ela que marca a atividade como respondida.
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.routers.roadmap import _owned_node
from app.services import atividades

router = APIRouter(prefix="/roadmap/nodes", tags=["atividades"])


def publica(linha: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "enunciado": linha.get("statement") or "",
        "tipo": linha.get("kind") or "pratica",
        "dicas": list(linha.get("hints") or []),
        "criada_em": linha.get("created_at"),
        "respondida_em": linha.get("answered_at"),
        "nota": linha.get("score"),
    }


def _do_modulo(supabase: Client, user_id: str, node_id: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_activity_exercise")
        .select("*")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
        .data
        or []
    )


@router.get("/{node_id}/atividades")
def listar(
    node_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    _owned_node(supabase, node_id, user_id)
    linhas = _do_modulo(supabase, user_id, node_id)
    aberta = next((linha for linha in linhas if not linha.get("answered_at")), None)
    feitas = [linha for linha in linhas if linha.get("answered_at")]
    return {
        "atual": publica(aberta) if aberta else None,
        "feitas": [publica(linha) for linha in feitas[:10]],
        "total_feitas": len(feitas),
    }


@router.post("/{node_id}/atividades/proxima", status_code=status.HTTP_201_CREATED)
async def proxima(
    node_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    node = _owned_node(supabase, node_id, user_id)
    aberta = next((linha for linha in _do_modulo(supabase, user_id, node_id) if not linha.get("answered_at")), None)
    if aberta:
        return publica(aberta)
    return publica(await atividades.gerar(supabase, user_id, node))
