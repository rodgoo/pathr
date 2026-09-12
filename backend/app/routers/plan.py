"""O plano da semana e os ajustes de rota.

As regras moram em services/weekly_plan.py e services/route_adjust.py, que não
conhecem o banco. Este arquivo só junta a evidência e grava o resultado.

A virada da semana é o momento do ajuste. Na primeira abertura de cada semana
a rota se corrige com o que o app mediu na semana anterior, e só DEPOIS o
checklist é montado — senão a lista nova sairia do plano velho. Uma vez por
semana e não a cada abertura: um plano que muda de forma toda vez que a tela
carrega não é plano, e a pessoa pararia de confiar nele.

O GET da semana grava (cria a linha na primeira abertura, marca evidências).
É escrita preguiçosa de algo derivado, não uma mudança pedida pela pessoa —
por isso não precisa de rota POST separada nem de aviso a outros aparelhos.
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.routers import library as library_router
from app.services import resource_search, route_adjust, weekly_plan
from app.services.progress import local_today

router = APIRouter(prefix="/plan", tags=["plano"])
logger = logging.getLogger("pathr.plan")


class MarcarItem(BaseModel):
    feito: bool


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _quando(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    try:
        lido = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return lido if lido.tzinfo else lido.replace(tzinfo=timezone.utc)


def _dia(valor: Any) -> Optional[date]:
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    lido = _quando(valor)
    return lido.date() if lido else None


def _principal(supabase: Client, user_id: str) -> dict:
    linhas = (
        supabase.table("pathr_roadmap")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_primary", True)
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gere o roadmap primeiro — o plano da semana sai dele.",
        )
    return linhas[0]


def _nodes(supabase: Client, roadmap_id: str) -> list[dict]:
    return (
        supabase.table("pathr_roadmap_node").select("*").eq("roadmap_id", roadmap_id).execute().data
        or []
    )


def _horas_semanais(supabase: Client, user_id: str, roadmap: dict) -> float:
    """As horas de HOJE, do perfil — não as da geração do plano.

    A aba Objetivo edita o perfil. Usar as horas gravadas no roadmap faria o
    checklist ignorar quem acabou de dizer que agora tem menos tempo.
    """
    perfil = (
        supabase.table("pathr_profile")
        .select("weekly_hours")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    horas = (perfil[0].get("weekly_hours") if perfil else None) or roadmap.get("weekly_hours") or 8
    return float(horas)


def _minutos_de_idioma(supabase: Client, user_id: str) -> int:
    """O idioma sai do mesmo orçamento — é o que a aba Idiomas promete."""
    try:
        linhas = (
            supabase.table("pathr_english_profile")
            .select("enabled,daily_goal_min")
            .eq("user_id", user_id)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return 0
    return sum(int(l.get("daily_goal_min") or 0) * 7 for l in linhas if l.get("enabled"))


def _niveis(supabase: Client, user_id: str) -> dict[str, tuple[int, str]]:
    linhas = (
        supabase.table("pathr_user_tag")
        .select("tag_id,proficiency,source")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    return {
        str(l["tag_id"]): (int(l.get("proficiency") or 0), str(l.get("source") or ""))
        for l in linhas
    }


def _pendentes(supabase: Client, user_id: str) -> dict[str, int]:
    """Conceitos vencidos por tag. A data é conferida aqui, e não na consulta,
    porque o volume por pessoa é pequeno e a comparação de fuso fica explícita."""
    agora = _agora()
    linhas = (
        supabase.table("pathr_review_item")
        .select("tag_id,due_at")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    contagem: dict[str, int] = {}
    for linha in linhas:
        vence = _quando(linha.get("due_at"))
        if vence and vence <= agora:
            chave = str(linha.get("tag_id") or "")
            contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def _notas(supabase: Client, user_id: str):
    """Última nota de quiz e de explicação por módulo, e quando aconteceu."""
    quizzes = (
        supabase.table("pathr_quiz").select("id,node_id").eq("user_id", user_id).execute().data
        or []
    )
    no_do_quiz = {str(q["id"]): str(q["node_id"]) for q in quizzes if q.get("node_id")}
    tentativas = (
        supabase.table("pathr_attempt")
        .select("quiz_id,score,finished_at")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    quiz_nota: dict[str, float] = {}
    quiz_quando: dict[str, datetime] = {}
    for tentativa in tentativas:
        no = no_do_quiz.get(str(tentativa.get("quiz_id")))
        quando = _quando(tentativa.get("finished_at"))
        if not no or quando is None or tentativa.get("score") is None:
            continue
        if no not in quiz_quando or quando > quiz_quando[no]:
            quiz_quando[no] = quando
            quiz_nota[no] = float(tentativa["score"])

    explicacoes = (
        supabase.table("pathr_explanation")
        .select("node_id,score,created_at")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    feyn_nota: dict[str, int] = {}
    feyn_quando: dict[str, datetime] = {}
    for explicacao in explicacoes:
        no = str(explicacao.get("node_id") or "")
        quando = _quando(explicacao.get("created_at"))
        if not no or quando is None:
            continue
        if no not in feyn_quando or quando > feyn_quando[no]:
            feyn_quando[no] = quando
            feyn_nota[no] = int(explicacao.get("score") or 0)
    return quiz_nota, feyn_nota, quiz_quando, feyn_quando


def _minutos_por_dia(supabase: Client, user_id: str) -> dict[date, int]:
    linhas = (
        supabase.table("pathr_activity")
        .select("activity_date,minutes")
        .eq("user_id", user_id)
        .order("activity_date", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )
    por_dia: dict[date, int] = {}
    for linha in linhas:
        dia = _dia(linha.get("activity_date"))
        if dia:
            por_dia[dia] = por_dia.get(dia, 0) + int(linha.get("minutes") or 0)
    return por_dia


def _ajustar(supabase: Client, user: dict, roadmap: dict, aplicar: bool) -> tuple[list[dict], int]:
    user_id = str(user["id"])
    hoje = local_today(user.get("timezone_name"))
    criado = _dia(roadmap.get("created_at")) or hoje
    semana = weekly_plan.semana_do_plano(criado, hoje, int(roadmap.get("horizon_weeks") or 12))
    nodes = _nodes(supabase, str(roadmap["id"]))
    quiz_nota, feyn_nota, _, _ = _notas(supabase, user_id)

    idade = (hoje - criado).days
    horas_reais = None
    if idade >= route_adjust.MINIMO_DE_DIAS:
        horas_reais = route_adjust.horas_por_semana(
            _minutos_por_dia(supabase, user_id), hoje, min(route_adjust.DIAS_DE_RITMO, idade)
        )

    meta = roadmap.get("meta") or {}
    evidencia = route_adjust.Evidencia(
        nivel_por_tag=_niveis(supabase, user_id),
        pendentes_por_tag=_pendentes(supabase, user_id),
        nota_quiz_por_node=quiz_nota,
        nota_feynman_por_node=feyn_nota,
        horas_planejadas=_horas_semanais(supabase, user_id, roadmap),
        horas_reais=horas_reais,
        semana_atual=semana,
        ja_reforcados=set(meta.get("reforcados") or []),
        ja_compactados=set(meta.get("compactados") or []),
    )
    mudancas, campos = route_adjust.propor(nodes, evidencia)

    if aplicar and mudancas:
        for node_id, valores in campos.items():
            supabase.table("pathr_roadmap_node").update(valores).eq("id", node_id).execute()
        fim = max(
            [int(v.get("week_end") or 0) for v in campos.values()]
            + [int(roadmap.get("horizon_weeks") or 0)]
        )
        historico = list(meta.get("ajustes") or [])
        historico.insert(0, {"em": _agora().isoformat(), "semana": semana, "mudancas": mudancas})
        novo_meta = {
            **meta,
            "ajustes": historico[:20],
            "reforcados": sorted(
                evidencia.ja_reforcados
                | {m["node_id"] for m in mudancas if m["tipo"] == "reforcar"}
            ),
            "compactados": sorted(
                evidencia.ja_compactados
                | {m["node_id"] for m in mudancas if m["tipo"] == "compactar"}
            ),
        }
        supabase.table("pathr_roadmap").update(
            {"meta": novo_meta, "horizon_weeks": fim, "updated_at": _agora().isoformat()}
        ).eq("id", str(roadmap["id"])).execute()
    return mudancas, semana


def _orcamento(supabase: Client, user_id: str, roadmap: dict) -> int:
    return max(
        30,
        int(_horas_semanais(supabase, user_id, roadmap) * 60) - _minutos_de_idioma(supabase, user_id),
    )


def _montar(supabase: Client, user_id: str, roadmap: dict, semana: int) -> list[dict]:
    nodes = _nodes(supabase, str(roadmap["id"]))
    modulos = weekly_plan.modulos_da_semana(nodes, semana)
    niveis = {tag: nivel for tag, (nivel, _origem) in _niveis(supabase, user_id).items()}
    pendentes = sum(_pendentes(supabase, user_id).values())
    return weekly_plan.montar(modulos, niveis, pendentes, _orcamento(supabase, user_id, roadmap))


def _evidencias(supabase: Client, user_id: str, inicio: date, itens: list[dict]) -> bool:
    _, _, quiz_quando, feyn_quando = _notas(supabase, user_id)
    desde = datetime(inicio.year, inicio.month, inicio.day, tzinfo=timezone.utc)
    quiz_nos = {no for no, quando in quiz_quando.items() if quando >= desde}
    feyn_nos = {no for no, quando in feyn_quando.items() if quando >= desde}
    pendentes = sum(_pendentes(supabase, user_id).values())
    return weekly_plan.aplicar_evidencias(
        itens, quiz_nos, feyn_nos, pendentes, _agora().isoformat()
    )


def _linha_da_semana(supabase: Client, user_id: str, inicio: date) -> Optional[dict]:
    linhas = (
        supabase.table("pathr_weekly_checklist")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start", inicio.isoformat())
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def _gravar(supabase: Client, user_id: str, inicio: date, dados: dict, existe: bool) -> None:
    if existe:
        supabase.table("pathr_weekly_checklist").update(dados).eq("user_id", user_id).eq(
            "week_start", inicio.isoformat()
        ).execute()
        return
    try:
        supabase.table("pathr_weekly_checklist").insert(
            {"user_id": user_id, "week_start": inicio.isoformat(), **dados}
        ).execute()
    except Exception:  # noqa: BLE001
        # Duas abas abrindo a tela inicial na mesma virada de semana: a
        # segunda bate na unicidade (usuário, semana). O conteúdo é o mesmo —
        # grava por cima em vez de devolver 500 para quem só abriu o app.
        supabase.table("pathr_weekly_checklist").update(dados).eq("user_id", user_id).eq(
            "week_start", inicio.isoformat()
        ).execute()


def _payload(
    semana: int, inicio: date, itens: list[dict], orcamento: int, ajustes: list[dict]
) -> dict:
    return {
        "semana": semana,
        "inicio": inicio.isoformat(),
        "itens": itens,
        "resumo": weekly_plan.resumo(itens),
        "orcamento_min": orcamento,
        "ajustes": ajustes,
    }


def _modulos_sem_material(supabase: Client, roadmap_id: str, itens: list[dict]) -> list[str]:
    """Os módulos da semana que ainda não tiveram busca de material."""
    ids: list[str] = []
    for item in itens:
        node_id = item.get("node_id")
        if node_id and node_id not in ids:
            ids.append(node_id)
    if not ids:
        return []
    nodes = {str(n["id"]): n for n in _nodes(supabase, roadmap_id)}
    tags_de = {nid: {str(t) for t in (nodes.get(nid, {}).get("tag_ids") or [])} for nid in ids}
    todas = sorted(set().union(*tags_de.values()))
    if not todas:
        return []
    linhas = (
        supabase.table("pathr_tag").select("id,curated_at").in_("id", todas).execute().data or []
    )
    carentes = {str(t["id"]) for t in linhas if resource_search.needs_curation(t)}
    return [nid for nid in ids if tags_de[nid] & carentes]


async def _curar_semana(supabase: Client, user: dict, node_ids: list[str]) -> None:
    """Busca o material dos módulos da semana, depois da resposta.

    O checklist promete "Estudar o material de X", e a promessa era falsa
    enquanto a busca dependesse de alguém achar o botão. Aqui ela sai sozinha,
    em segundo plano para não atrasar a tela inicial, e pela mesma rota do
    botão — a carência de 14 dias por tag segura a cota do YouTube.
    """
    for node_id in node_ids:
        try:
            await library_router.curate_library(
                node_id=node_id, current_user=user, supabase=supabase
            )
        except Exception:  # noqa: BLE001
            logger.warning("busca de material da semana falhou em %s", node_id, exc_info=True)


@router.get("/week")
def semana_atual(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    # Por último e com default: o FastAPI injeta pelo tipo, e chamar a função
    # direto (teste) não pode deslocar os outros parâmetros.
    background: BackgroundTasks = None,
):
    """O checklist da semana. Na virada, ajusta a rota e monta a lista nova."""
    user_id = str(current_user["id"])
    roadmap = _principal(supabase, user_id)
    inicio = weekly_plan.inicio_da_semana(local_today(current_user.get("timezone_name")))
    linha = _linha_da_semana(supabase, user_id, inicio)

    ajustes: list[dict] = []
    if linha is None or str(linha.get("roadmap_id")) != str(roadmap["id"]):
        ajustes, semana = _ajustar(supabase, current_user, roadmap, aplicar=True)
        itens = _montar(supabase, user_id, roadmap, semana)
        _gravar(
            supabase,
            user_id,
            inicio,
            {
                "roadmap_id": str(roadmap["id"]),
                "week_index": semana,
                "items": itens,
                "updated_at": _agora().isoformat(),
            },
            existe=linha is not None,
        )
    else:
        guardados = list(linha.get("items") or [])
        semana = int(linha.get("week_index") or 1)
        # A lista se remonta sozinha quando o que a gerou mudou: o nível subiu
        # num quiz, uma revisão entrou na fila, ou a semana acabou cedo e há
        # módulos seguintes a puxar. O que já foi feito continua feito — ver
        # `weekly_plan.preservar`. Não ajusta a rota: isso é da virada.
        itens = weekly_plan.preservar(_montar(supabase, user_id, roadmap, semana), guardados)
        if weekly_plan.mudou(itens, guardados):
            _gravar(
                supabase, user_id, inicio, {"items": itens, "updated_at": _agora().isoformat()}, True
            )
        else:
            itens = guardados

    if _evidencias(supabase, user_id, inicio, itens):
        _gravar(
            supabase, user_id, inicio, {"items": itens, "updated_at": _agora().isoformat()}, True
        )
    if background is not None:
        sem_material = _modulos_sem_material(supabase, str(roadmap["id"]), itens)
        if sem_material:
            background.add_task(_curar_semana, supabase, current_user, sem_material)
    return _payload(semana, inicio, itens, _orcamento(supabase, user_id, roadmap), ajustes)


@router.patch("/week/items/{item_id}")
def marcar_item(
    item_id: str,
    payload: MarcarItem,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Marca à mão. Não registra atividade: marcar não é estudar — o que conta
    para o streak já foi registrado pelo quiz ou pela explicação em si."""
    user_id = str(current_user["id"])
    inicio = weekly_plan.inicio_da_semana(local_today(current_user.get("timezone_name")))
    linha = _linha_da_semana(supabase, user_id, inicio)
    if linha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ainda não há checklist nesta semana — abra a tela inicial para gerá-lo.",
        )
    itens = list(linha.get("items") or [])
    try:
        item = weekly_plan.marcar(itens, item_id, payload.feito, _agora().isoformat())
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")
    except weekly_plan.ItemVerificado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este item foi confirmado pelo que você fez — um quiz respondido ou uma "
                "explicação enviada — e não se desmarca à mão."
            ),
        )
    _gravar(supabase, user_id, inicio, {"items": itens, "updated_at": _agora().isoformat()}, True)
    return {"item": item, "resumo": weekly_plan.resumo(itens)}


@router.post("/week/refresh")
def refazer_semana(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Remonta a lista com o nível de agora, mantendo o que já foi feito.

    Para quando o nível mudou no meio da semana, ou quando a pessoa terminou
    tudo cedo e quer os próximos módulos. Não ajusta a rota: isso é da virada.
    """
    user_id = str(current_user["id"])
    roadmap = _principal(supabase, user_id)
    hoje = local_today(current_user.get("timezone_name"))
    inicio = weekly_plan.inicio_da_semana(hoje)
    semana = weekly_plan.semana_do_plano(
        _dia(roadmap.get("created_at")) or hoje, hoje, int(roadmap.get("horizon_weeks") or 12)
    )
    linha = _linha_da_semana(supabase, user_id, inicio)
    itens = _montar(supabase, user_id, roadmap, semana)
    if linha is not None:
        itens = weekly_plan.preservar(itens, list(linha.get("items") or []))
    _evidencias(supabase, user_id, inicio, itens)
    _gravar(
        supabase,
        user_id,
        inicio,
        {
            "roadmap_id": str(roadmap["id"]),
            "week_index": semana,
            "items": itens,
            "updated_at": _agora().isoformat(),
        },
        existe=linha is not None,
    )
    return _payload(semana, inicio, itens, _orcamento(supabase, user_id, roadmap), [])


@router.post("/adjust")
def ajustar_rota(
    preview: bool = False,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Ajusta a rota agora, sem esperar a virada. `preview` só mostra."""
    roadmap = _principal(supabase, str(current_user["id"]))
    mudancas, semana = _ajustar(supabase, current_user, roadmap, aplicar=not preview)
    return {"semana": semana, "mudancas": mudancas, "aplicado": bool(mudancas) and not preview}


@router.get("/adjustments")
def historico_de_ajustes(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Os ajustes já feitos, do mais recente para o mais antigo."""
    roadmap = _principal(supabase, str(current_user["id"]))
    return (roadmap.get("meta") or {}).get("ajustes") or []
