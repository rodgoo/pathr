"""O plano de estudos: gerar, ler e marcar progresso.

Um usuário pode ter vários roadmaps (mudou de objetivo, quer comparar), mas
só um é `is_primary` — é o que a tela inicial mostra. Gerar um novo não apaga
o anterior: o histórico é o que permite voltar atrás depois de uma mudança de
rumo que não deu certo.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import roadmap_builder
from app.services.progress import log_activity
from app.services.tag_catalog import TagCatalog

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


class GenerateRequest(BaseModel):
    objective: str = Field(min_length=5, max_length=500)
    horizon_weeks: int = Field(default=12, ge=4, le=52)
    weekly_hours: int = Field(default=8, ge=1, le=60)
    # Texto livre da pessoa: o que atrapalha, prazo, restrição. Vai inteiro
    # para o prompt porque é onde mora o que nenhum campo estruturado captura.
    context: str = Field(default="", max_length=2000)


class DraftIn(BaseModel):
    # Sem `min_length`: apagar tudo é uma edição legítima, e recusá-la faria o
    # servidor guardar um texto que a pessoa já removeu da tela.
    content: str = Field(default="", max_length=100_000)


class NodePatch(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(locked|todo|doing|done|skipped)$")
    progress_pct: Optional[int] = Field(default=None, ge=0, le=100)
    minutes: int = Field(default=0, ge=0, le=600)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _known_tags(supabase: Client, user_id: str) -> tuple[list[dict], list[str]]:
    """O que o usuário sabe, e o que ele marcou como meta."""
    rows = (
        supabase.table("pathr_user_tag")
        .select("tag_id,proficiency,is_target")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    if not rows:
        return [], []
    tags = (
        supabase.table("pathr_tag")
        .select("id,name")
        .in_("id", [str(row["tag_id"]) for row in rows])
        .execute()
        .data
        or []
    )
    names = {str(tag["id"]): tag["name"] for tag in tags}

    known = []
    targets = []
    for row in rows:
        name = names.get(str(row["tag_id"]))
        if not name:
            continue
        known.append({"name": name, "proficiency": int(row.get("proficiency") or 0)})
        if row.get("is_target"):
            targets.append(name)
    return known, targets


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_roadmap(
    payload: GenerateRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Gera o plano com IA e o grava como o roadmap principal."""
    user_id = str(current_user["id"])
    profile_rows = (
        supabase.table("pathr_profile").select("*").eq("user_id", user_id).limit(1).execute().data
    )
    profile = profile_rows[0] if profile_rows else {}

    known, targets = _known_tags(supabase, user_id)
    if not known:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Adicione suas competências (ou envie um currículo) antes de gerar o plano.",
        )

    catalog = TagCatalog(supabase).load()
    catalog_names = [
        row["name"]
        for row in (
            supabase.table("pathr_tag")
            .select("name")
            .order("popularity", desc=True)
            .limit(400)
            .execute()
            .data
            or []
        )
    ]

    prompt = roadmap_builder.build_prompt(
        objective=payload.objective,
        weeks=payload.horizon_weeks,
        weekly_hours=payload.weekly_hours,
        current_role=profile.get("current_role") or "",
        years=float(profile.get("years_experience") or 0),
        known=known,
        targets=targets,
        catalog_names=catalog_names,
        extra=payload.context,
    )

    job = _open_job(supabase, user_id)
    plan, ai_result = await roadmap_builder.generate(prompt)
    if not plan["fases"]:
        _close_job(supabase, job, "failed", error="plano vazio")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA respondeu um plano vazio. Tente de novo em instantes.",
        )

    roadmap = _persist(supabase, user_id, payload, plan, catalog, ai_result.model)
    _close_job(
        supabase,
        job,
        "done",
        provider=ai_result.provider,
        model=ai_result.model,
        tokens=ai_result.tokens,
        latency_ms=ai_result.latency_ms,
        output={"fases": len(plan["fases"])},
    )
    log_activity(
        supabase,
        user=current_user,
        kind="roadmap_created",
        title=plan["titulo"],
        ref_id=str(roadmap["id"]),
    )
    return get_roadmap(str(roadmap["id"]), current_user, supabase)


def linha_do_roadmap(
    user_id: str, payload: GenerateRequest, plan: dict[str, Any], model: str
) -> dict[str, Any]:
    """A linha de `pathr_roadmap`, montada e nada mais.

    Separada do `_persist` para poder ser conferida sem banco: foi aqui que
    faltou `goal`, uma coluna NOT NULL, e TODA geração de plano morria num 500
    logo depois de a IA ter feito o trabalho inteiro. O teste em
    tests/test_roadmap_persist.py compara estas chaves com as colunas
    obrigatórias do modelo, então uma coluna nova sem valor reprova antes de
    chegar à produção.
    """
    return {
        "user_id": user_id,
        "title": plan["titulo"],
        # O objetivo em texto livre, inteiro. `target_role` é o mesmo texto
        # cortado em 120 para caber num rótulo de tela — e cortar não pode ser
        # o único lugar onde o objetivo existe.
        "goal": payload.objective,
        "target_role": payload.objective[:120],
        "horizon_weeks": payload.horizon_weeks,
        "weekly_hours": payload.weekly_hours,
        "status": "active",
        "is_primary": True,
        "generated_by": model,
        "summary": plan["resumo"],
        "meta": {"objective": payload.objective, "context": payload.context},
    }


def _persist(
    supabase: Client,
    user_id: str,
    payload: GenerateRequest,
    plan: dict[str, Any],
    catalog: TagCatalog,
    model: str,
) -> dict[str, Any]:
    """Grava o plano: uma linha de roadmap, uma de fase, uma por módulo.

    Fase e módulo moram na MESMA tabela (`pathr_roadmap_node`), diferenciados
    por `kind` e ligados por `parent_id`. Uma tabela em vez de duas porque
    fase e módulo têm exatamente os mesmos campos de progresso, e a árvore
    pode ganhar um terceiro nível sem migração.
    """
    supabase.table("pathr_roadmap").update({"is_primary": False}).eq("user_id", user_id).execute()

    roadmap = (
        supabase.table("pathr_roadmap")
        .insert(linha_do_roadmap(user_id, payload, plan, model))
        .execute()
        .data[0]
    )

    order = 0
    for phase in plan["fases"]:
        phase_row = (
            supabase.table("pathr_roadmap_node")
            .insert(
                {
                    "roadmap_id": roadmap["id"],
                    "title": phase["titulo"],
                    "description": phase["objetivo"],
                    "kind": "phase",
                    "order_index": order,
                    "week_start": phase["semana_inicio"] or None,
                    "week_end": phase["semana_fim"] or None,
                    "status": "todo",
                }
            )
            .execute()
            .data[0]
        )
        order += 1

        for module in phase["modulos"]:
            tag_ids = [str(catalog.resolve(name)["id"]) for name in module["tags"]]
            supabase.table("pathr_roadmap_node").insert(
                {
                    "roadmap_id": roadmap["id"],
                    "parent_id": phase_row["id"],
                    "title": module["titulo"],
                    "description": module["descricao"],
                    "kind": module["tipo"],
                    "tag_ids": tag_ids,
                    "order_index": order,
                    "level": module["nivel"],
                    "estimated_hours": module["horas"],
                    "week_start": module["semana_inicio"] or None,
                    "week_end": module["semana_fim"] or None,
                    # O primeiro módulo do plano já nasce em andamento: abrir o
                    # roadmap e ver tudo "a fazer" não diz por onde começar.
                    "status": "doing" if order == 1 else "todo",
                    "objectives": module["objetivos"],
                }
            ).execute()
            order += 1

    return roadmap


@router.get("")
def list_roadmaps(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return (
        supabase.table("pathr_roadmap")
        .select("id,title,target_role,horizon_weeks,weekly_hours,status,is_primary,summary,created_at")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


@router.get("/current")
def current_roadmap(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O plano principal, com a árvore montada. 404 quando ainda não existe —
    é o sinal que o frontend usa para levar a pessoa ao onboarding."""
    rows = (
        supabase.table("pathr_roadmap")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .eq("is_primary", True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum plano gerado ainda."
        )
    return get_roadmap(str(rows[0]["id"]), current_user, supabase)


@router.get("/{roadmap_id}")
def get_roadmap(
    roadmap_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O plano com fases e módulos aninhados, do jeito que a tela desenha."""
    rows = (
        supabase.table("pathr_roadmap")
        .select("*")
        .eq("id", roadmap_id)
        .eq("user_id", str(current_user["id"]))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado.")
    roadmap = rows[0]

    nodes = (
        supabase.table("pathr_roadmap_node")
        .select("*")
        .eq("roadmap_id", roadmap_id)
        .order("order_index")
        .execute()
        .data
        or []
    )

    phases = [node for node in nodes if node.get("kind") == "phase"]
    children: dict[str, list[dict]] = {}
    for node in nodes:
        parent = node.get("parent_id")
        if parent:
            children.setdefault(str(parent), []).append(node)

    modules = [node for node in nodes if node.get("kind") != "phase"]
    done = sum(1 for node in modules if node.get("status") == "done")

    return {
        **roadmap,
        "progress_pct": round(100 * done / len(modules)) if modules else 0,
        "total_nodes": len(modules),
        "done_nodes": done,
        "phases": [
            {**phase, "modules": children.get(str(phase["id"]), [])} for phase in phases
        ],
    }


@router.patch("/nodes/{node_id}")
def patch_node(
    node_id: str,
    payload: NodePatch,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Marca progresso num módulo.

    Concluir registra atividade (streak, XP, heatmap) e sobe a proficiência
    das tags do módulo — é assim que estudar realimenta o perfil, sem a
    pessoa ter que editar níveis à mão.
    """
    node = _owned_node(supabase, node_id, str(current_user["id"]))
    update: dict[str, Any] = {}
    if payload.status:
        update["status"] = payload.status
        if payload.status == "done":
            update["completed_at"] = _now().isoformat()
            update["progress_pct"] = 100
    if payload.progress_pct is not None:
        update["progress_pct"] = payload.progress_pct
    if not update:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para atualizar.")

    updated = (
        supabase.table("pathr_roadmap_node").update(update).eq("id", node_id).execute().data[0]
    )

    if update.get("status") == "done" and node.get("status") != "done":
        tag_ids = [str(tag) for tag in (node.get("tag_ids") or [])]
        log_activity(
            supabase,
            user=current_user,
            kind="node_done",
            title=node.get("title") or "",
            ref_id=node_id,
            minutes=payload.minutes,
            tag_ids=tag_ids,
        )
        _bump_proficiency(supabase, str(current_user["id"]), tag_ids)
        _advance_next(supabase, node)

    return updated


@router.get("/nodes/{node_id}/draft")
def get_draft(
    node_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O rascunho da atividade prática deste módulo.

    Devolve string vazia quando não há nada escrito, e não 404: "ainda não
    escrevi" é um estado normal do campo, não um erro que a tela precise
    tratar.
    """
    user_id = str(current_user["id"])
    _owned_node(supabase, node_id, user_id)
    rows = (
        supabase.table("pathr_activity_draft")
        .select("content,updated_at")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return {"content": "", "updated_at": None}
    return {"content": rows[0].get("content") or "", "updated_at": rows[0].get("updated_at")}


@router.put("/nodes/{node_id}/draft")
def save_draft(
    node_id: str,
    payload: DraftIn,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Grava o rascunho. Substitui no lugar.

    O texto ficava no `localStorage`, preso a um navegador — e escrever a
    solução do zero é o trabalho mais caro de perder ao trocar de máquina. Um
    por (usuário, módulo): o que importa é o texto atual, não o histórico de
    cada tecla.
    """
    user_id = str(current_user["id"])
    _owned_node(supabase, node_id, user_id)
    agora = _now().isoformat()
    existente = (
        supabase.table("pathr_activity_draft")
        .select("id")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        supabase.table("pathr_activity_draft").update(
            {"content": payload.content, "updated_at": agora}
        ).eq("id", existente[0]["id"]).execute()
    else:
        supabase.table("pathr_activity_draft").insert(
            {
                "user_id": user_id,
                "node_id": node_id,
                "content": payload.content,
                "updated_at": agora,
            }
        ).execute()
    return {"content": payload.content, "updated_at": agora}


def _owned_node(supabase: Client, node_id: str, user_id: str) -> dict[str, Any]:
    """Confere o dono do nó pelo roadmap.

    `pathr_roadmap_node` não tem `user_id` — ele pertence ao roadmap, e é o
    roadmap que pertence a alguém. Sem esta checagem, um id adivinhado deixaria
    qualquer pessoa concluir módulo de outra.
    """
    rows = supabase.table("pathr_roadmap_node").select("*").eq("id", node_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    node = rows[0]
    owner = (
        supabase.table("pathr_roadmap")
        .select("id")
        .eq("id", node["roadmap_id"])
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    return node


def _bump_proficiency(supabase: Client, user_id: str, tag_ids: list[str]) -> None:
    """Concluir um módulo sobe em 1 o nível das tags dele, com teto em 3.

    Teto em 3 ("autônomo") de propósito: estudar comprova autonomia, não
    referência. Os níveis 4 e 5 só saem de avaliação ou de edição consciente
    da própria pessoa. A confiança sobe junto porque agora há evidência.
    """
    for tag_id in tag_ids:
        rows = (
            supabase.table("pathr_user_tag")
            .select("id,proficiency,confidence")
            .eq("user_id", user_id)
            .eq("tag_id", tag_id)
            .limit(1)
            .execute()
            .data
        )
        if rows:
            row = rows[0]
            current = int(row.get("proficiency") or 0)
            if current >= 3:
                continue
            supabase.table("pathr_user_tag").update(
                {
                    "proficiency": current + 1,
                    "confidence": min(1.0, float(row.get("confidence") or 0.5) + 0.2),
                    "source": "roadmap",
                    "last_assessed_at": _now().isoformat(),
                }
            ).eq("id", row["id"]).execute()
        else:
            supabase.table("pathr_user_tag").insert(
                {
                    "user_id": user_id,
                    "tag_id": tag_id,
                    "proficiency": 1,
                    "confidence": 0.6,
                    "source": "roadmap",
                    "last_assessed_at": _now().isoformat(),
                }
            ).execute()


def _advance_next(supabase: Client, node: dict[str, Any]) -> None:
    """Promove o próximo módulo a "em andamento".

    Sem isto, concluir um módulo deixaria o plano inteiro sem nada marcado
    como atual, e a tela inicial não teria o que oferecer como próximo passo.
    """
    candidates = (
        supabase.table("pathr_roadmap_node")
        .select("id,status,kind,order_index")
        .eq("roadmap_id", node["roadmap_id"])
        .gt("order_index", node.get("order_index") or 0)
        .order("order_index")
        .limit(10)
        .execute()
        .data
        or []
    )
    for candidate in candidates:
        if candidate.get("kind") != "phase" and candidate.get("status") == "todo":
            supabase.table("pathr_roadmap_node").update({"status": "doing"}).eq(
                "id", candidate["id"]
            ).execute()
            return


def _open_job(supabase: Client, user_id: str) -> Optional[str]:
    try:
        row = (
            supabase.table("pathr_ai_job")
            .insert({"user_id": user_id, "kind": "roadmap_gen", "status": "running"})
            .execute()
            .data[0]
        )
        return str(row["id"])
    except Exception:  # noqa: BLE001
        return None


def _close_job(
    supabase: Client,
    job_id: Optional[str],
    status_value: str,
    *,
    provider: str = "",
    model: str = "",
    tokens: int = 0,
    latency_ms: int = 0,
    output: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    if not job_id:
        return
    try:
        supabase.table("pathr_ai_job").update(
            {
                "status": status_value,
                "provider": provider or None,
                "model": model or None,
                "completion_tokens": tokens,
                "latency_ms": latency_ms,
                "output": output or {},
                "error": error,
                "finished_at": _now().isoformat(),
            }
        ).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001
        pass
