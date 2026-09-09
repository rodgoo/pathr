"""Biblioteca: material curado e o progresso do usuário nele.

`pathr_resource` é um catálogo GLOBAL, como as tags — um vídeo bom sobre JPA
serve para todo mundo que estuda JPA, e curar por usuário multiplicaria o
mesmo trabalho. O que é por pessoa mora em `pathr_user_resource`: salvo, em
andamento, concluído, nota, minutos gastos.

A curadoria é filtrada pelas tags do usuário, e é isso que faz a biblioteca
parecer pessoal sem ser duplicada.

Quem PREENCHE o catálogo é `POST /curate`, que delega a
services/resource_search.py. Até ele existir esta tabela só era lida, e a
biblioteca vinha vazia para todo mundo — o modelo estava pronto e a fonte
nunca chegou.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.services import resource_search
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


# ---------------------------------------------------------------------------
# Curadoria — quem escreve no catálogo
# ---------------------------------------------------------------------------

# Quantas tags uma chamada pode buscar. O limite é de COTA, não de tempo:
# `search.list` do YouTube custa 100 das 10.000 unidades diárias do app
# inteiro, então três tags por clique são 300 unidades. Quem abre um módulo
# com seis tecnologias recebe as três mais carentes agora e as outras na
# chamada seguinte, em vez de o primeiro usuário do dia consumir a cota de
# todos.
_MAX_TAGS_PER_CALL = 3


@router.post("/curate")
async def curate_library(
    node_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Busca material novo para as tags do usuário (ou as de um módulo).

    Devolve o que ENTROU, não o que existe: a tela chama isto e recarrega a
    lista, e um resumo do catálogo inteiro aqui só duplicaria o GET.

    Não é idempotente por acaso — é por carência. Chamar duas vezes seguidas
    não busca duas vezes, porque `pathr_tag.curated_at` segura a segunda; o
    retorno nesse caso traz `tags_buscadas: []`, e é assim que a tela sabe
    dizer "já procuramos há pouco" em vez de "não achamos nada".
    """
    user_id = str(current_user["id"])

    if node_id:
        node = _owned_node(supabase, node_id, user_id)
        wanted = [str(tag) for tag in (node.get("tag_ids") or [])]
    else:
        wanted = _user_tag_ids(supabase, user_id)

    if not wanted:
        return {
            "novos": 0,
            "tags_buscadas": [],
            "motivo": "Nenhuma tecnologia associada ainda — preencha o perfil ou gere o roadmap.",
        }

    tags = (
        supabase.table("pathr_tag")
        .select("id,name,slug,category,curated_at")
        .in_("id", wanted)
        .execute()
        .data
        or []
    )
    pendentes = [tag for tag in tags if resource_search.needs_curation(tag)][:_MAX_TAGS_PER_CALL]

    if not pendentes:
        return {
            "novos": 0,
            "tags_buscadas": [],
            "motivo": "Essas tecnologias foram buscadas há pouco. A curadoria repete a cada 14 dias.",
        }

    novos = 0
    for tag in pendentes:
        candidatos = await resource_search.search_for_tag(tag)
        novos += _absorve(supabase, candidatos, str(tag["id"]))
        # Carimba mesmo quando a busca não achou nada: sem isso, uma tag sem
        # material seria rebuscada a cada clique e gastaria a cota inteira
        # justamente no assunto que não tem resultado.
        supabase.table("pathr_tag").update({"curated_at": _now().isoformat()}).eq(
            "id", str(tag["id"])
        ).execute()

    # Sem `log_activity` aqui, de propósito. Ela não só escreve no feed: ela
    # chama `touch_streak`, que avança a sequência de dias mesmo com xp=0. Um
    # clique em "procurar material" viraria um dia estudado, e o streak
    # passaria a medir cliques em vez de estudo — justo o número que o app usa
    # para dizer à pessoa que ela está sendo constante. Procurar material não é
    # estudar; ler o que foi encontrado é, e isso já entra por `resource_done`.
    fontes = resource_search.sources_enabled()
    return {
        "novos": novos,
        "tags_buscadas": [tag.get("name") or tag.get("slug") for tag in pendentes],
        "motivo": None
        if novos
        else (
            "Nenhum material novo passou na verificação de link."
            if any(fontes.values())
            else "Nenhuma fonte de busca configurada no servidor."
        ),
    }


def _absorve(supabase: Client, candidatos: list, tag_id: str) -> int:
    """Grava os candidatos e devolve quantos são NOVOS.

    Não usa upsert com `on_conflict=url` de propósito. O catálogo é global e um
    mesmo vídeo serve a várias tags: um upsert sobrescreveria `tag_ids` com a
    tag desta rodada, e o vídeo que servia Docker e Kubernetes passaria a
    servir só o último. Aqui a linha que já existe recebe a tag NOVA somada às
    que ela já tinha.
    """
    if not candidatos:
        return 0

    urls = [item.url for item in candidatos]
    existentes = {
        row["url"]: row
        for row in (
            supabase.table("pathr_resource").select("id,url,tag_ids").in_("url", urls).execute().data
            or []
        )
    }

    inserir = []
    for candidato in candidatos:
        atual = existentes.get(candidato.url)
        if atual is None:
            inserir.append(candidato.to_row())
            continue

        ja_tem = {str(tag) for tag in (atual.get("tag_ids") or [])}
        if tag_id not in ja_tem:
            supabase.table("pathr_resource").update(
                {"tag_ids": sorted(ja_tem | {tag_id})}
            ).eq("id", atual["id"]).execute()

    if inserir:
        supabase.table("pathr_resource").insert(inserir).execute()
    return len(inserir)


def _owned_node(supabase: Client, node_id: str, user_id: str) -> dict[str, Any]:
    """O módulo é deste usuário?

    Mesma checagem em dois passos de roadmap.py: `pathr_roadmap_node` não tem
    `user_id` — ele pertence ao roadmap, e é o roadmap que pertence a alguém.
    Sem isto, um id adivinhado gastaria a cota de busca de outra pessoa.
    """
    rows = (
        supabase.table("pathr_roadmap_node").select("*").eq("id", node_id).limit(1).execute().data
    )
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
