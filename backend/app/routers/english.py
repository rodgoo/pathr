"""Módulo de idioma: nivelamento, prática e vocabulário.

Módulo ATIVÁVEL, não seção fixa: `pathr_english_profile.enabled` é o
interruptor, e enquanto ele estiver desligado nada aqui aparece no plano
diário. Foi assim que o recurso foi pedido, e é a diferença entre um app que
respeita quem já fala inglês e um que empurra prática que ninguém pediu.

O nivelamento é adaptativo: a dificuldade do próximo item sai do acerto do
anterior, então o teste converge no nível em ~20 itens em vez de precisar de
100.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services.progress import log_activity

router = APIRouter(prefix="/english", tags=["idioma"])

BANDS = ["A1", "A2", "B1", "B2", "C1", "C2"]

ITEMS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "itens": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "habilidade": {"type": "STRING"},
                    "banda": {"type": "STRING"},
                    "contexto": {"type": "STRING"},
                    "enunciado": {"type": "STRING"},
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correta": {"type": "INTEGER"},
                    "explicacao": {"type": "STRING"},
                },
                "required": ["enunciado", "alternativas", "correta", "explicacao"],
            },
        }
    },
    "required": ["itens"],
}

SYSTEM_PROMPT = """Você cria itens de avaliação de inglês corporativo para profissionais de tecnologia.

Regras:

1. O enunciado e as alternativas ficam EM INGLÊS. A explicação fica em
   português do Brasil — a pessoa está aprendendo, e a explicação é o ensino.
2. Todo item nasce de uma situação real de trabalho em time distribuído:
   daily, code review, e-mail de prazo, entrevista técnica, apresentação,
   negociação de escopo. Nada de gramática solta sem contexto.
3. Exatamente 4 alternativas; o campo correta é o índice de 0 a 3. As erradas
   precisam ser erros que brasileiros realmente cometem em inglês (falso
   cognato, tradução literal, tom errado), não absurdos.
4. O campo habilidade: grammar, vocabulary, reading, listening, writing,
   speaking ou business.
5. O campo banda: A1, A2, B1, B2, C1 ou C2 — a dificuldade real do item.
6. A explicação diz por que a certa soa natural e por que a mais tentadora
   das erradas soa estranha para um falante nativo.
7. Responda apenas o JSON."""


class EnglishSettings(BaseModel):
    enabled: Optional[bool] = None
    target_level: Optional[str] = Field(default=None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    focus_areas: Optional[list[Any]] = None
    daily_goal_min: Optional[int] = Field(default=None, ge=5, le=180)


class AnswerItem(BaseModel):
    item_id: str
    answer: int = Field(ge=0, le=3)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _profile(supabase: Client, user_id: str) -> dict[str, Any]:
    rows = (
        supabase.table("pathr_english_profile")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]
    # Conta criada antes deste módulo existir — cria na primeira visita em vez
    # de responder 404 por algo que é responsabilidade nossa.
    return (
        supabase.table("pathr_english_profile")
        .insert({"user_id": user_id})
        .execute()
        .data[0]
    )


@router.get("/profile")
def get_english_profile(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _profile(supabase, str(current_user["id"]))


@router.patch("/profile")
def update_english_profile(
    payload: EnglishSettings,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    update = payload.model_dump(exclude_unset=True)
    if not update:
        return _profile(supabase, str(current_user["id"]))
    update["updated_at"] = _now().isoformat()
    _profile(supabase, str(current_user["id"]))
    return (
        supabase.table("pathr_english_profile")
        .update(update)
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data[0]
    )


@router.post("/assessment", status_code=status.HTTP_201_CREATED)
async def start_assessment(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Abre um nivelamento e gera o primeiro lote de itens.

    Gera em lote de 5, não os 20 de uma vez: o teste é adaptativo, e os itens
    seguintes só podem ser calibrados depois de ver como a pessoa foi nos
    primeiros. Gerar tudo antes desperdiçaria cota em itens de dificuldade
    errada.
    """
    user_id = str(current_user["id"])
    profile = _profile(supabase, user_id)

    assessment = (
        supabase.table("pathr_english_assessment")
        .insert({"user_id": user_id, "kind": "placement", "item_count": 20})
        .execute()
        .data[0]
    )
    start_band = profile.get("cefr_level") or "B1"
    await _generate_items(supabase, user_id, str(assessment["id"]), start_band, count=5, offset=0)
    return _assessment_payload(supabase, str(assessment["id"]), user_id)


async def _generate_items(
    supabase: Client, user_id: str, assessment_id: str, band: str, count: int, offset: int
) -> None:
    result = await generate_json(
        SYSTEM_PROMPT,
        f"Gere {count} itens de nivel {band} para um profissional de tecnologia brasileiro. "
        "Varie a habilidade entre eles.",
        ITEMS_SCHEMA,
    )
    rows = []
    for index, item in enumerate(result.content.get("itens") or []):
        if not isinstance(item, dict):
            continue
        options = [str(option).strip() for option in (item.get("alternativas") or []) if str(option).strip()]
        try:
            correct = int(item.get("correta"))
        except (TypeError, ValueError):
            continue
        prompt = str(item.get("enunciado") or "").strip()
        if not prompt or len(options) != 4 or not 0 <= correct <= 3:
            continue
        skill = str(item.get("habilidade") or "grammar").strip().lower()
        item_band = str(item.get("banda") or band).strip().upper()
        rows.append(
            {
                "assessment_id": assessment_id,
                "user_id": user_id,
                "skill": skill if skill in
                {"grammar", "vocabulary", "reading", "listening", "writing", "speaking", "business"}
                else "grammar",
                "type": "mcq",
                "cefr_band": item_band if item_band in BANDS else band,
                "prompt": prompt[:2000],
                "context": str(item.get("contexto") or "").strip()[:1000] or None,
                "options": options,
                "correct": {"index": correct},
                "feedback": str(item.get("explicacao") or "").strip()[:1500],
                "order_index": offset + index,
            }
        )
    if rows:
        supabase.table("pathr_english_item").insert(rows).execute()


def _assessment_payload(supabase: Client, assessment_id: str, user_id: str) -> dict[str, Any]:
    """O nivelamento com os itens ainda não respondidos — sem gabarito."""
    rows = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("id", assessment_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nivelamento não encontrado.")
    items = (
        supabase.table("pathr_english_item")
        .select("id,skill,type,cefr_band,prompt,context,options,order_index,is_correct")
        .eq("assessment_id", assessment_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    return {**rows[0], "items": [item for item in items if item.get("is_correct") is None]}


@router.get("/assessment/{assessment_id}")
def get_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _assessment_payload(supabase, assessment_id, str(current_user["id"]))


@router.post("/assessment/{assessment_id}/answer")
async def answer_assessment(
    assessment_id: str,
    payload: AnswerItem,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Responde um item, devolve o gabarito e adapta o próximo lote."""
    user_id = str(current_user["id"])
    items = (
        supabase.table("pathr_english_item")
        .select("*")
        .eq("id", payload.item_id)
        .eq("user_id", user_id)
        .eq("assessment_id", assessment_id)
        .limit(1)
        .execute()
        .data
    )
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")
    item = items[0]
    if item.get("is_correct") is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item já respondido.")

    expected = int((item.get("correct") or {}).get("index", -1))
    is_correct = payload.answer == expected

    supabase.table("pathr_english_item").update(
        {
            "user_answer": str(payload.answer),
            "is_correct": is_correct,
            "answered_at": _now().isoformat(),
        }
    ).eq("id", item["id"]).execute()

    assessment = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("id", assessment_id)
        .limit(1)
        .execute()
        .data[0]
    )
    answered = int(assessment.get("answered_count") or 0) + 1
    correct_count = int(assessment.get("correct_count") or 0) + int(is_correct)
    supabase.table("pathr_english_assessment").update(
        {"answered_count": answered, "correct_count": correct_count}
    ).eq("id", assessment_id).execute()

    remaining = (
        supabase.table("pathr_english_item")
        .select("id", count="exact")
        .eq("assessment_id", assessment_id)
        .is_("is_correct", "null")
        .execute()
    )
    pending = remaining.count or 0

    finished = answered >= int(assessment.get("item_count") or 20)
    if finished:
        result = _finish_assessment(supabase, current_user, assessment_id, answered, correct_count)
        return {"is_correct": is_correct, "correct_index": expected,
                "explanation": item.get("feedback"), "finished": True, "result": result}

    # Acertou -> sobe a banda; errou -> desce. É isto que faz o teste
    # convergir: cada resposta move o alvo em direção ao nível real.
    if pending <= 1:
        band = _next_band(item.get("cefr_band") or "B1", is_correct)
        await _generate_items(supabase, user_id, assessment_id, band, count=5, offset=answered)

    return {
        "is_correct": is_correct,
        "correct_index": expected,
        "explanation": item.get("feedback"),
        "finished": False,
        "answered": answered,
        "total": int(assessment.get("item_count") or 20),
    }


def _next_band(current: str, went_up: bool) -> str:
    index = BANDS.index(current) if current in BANDS else 2
    return BANDS[max(0, min(len(BANDS) - 1, index + (1 if went_up else -1)))]


def _finish_assessment(
    supabase: Client, user: dict, assessment_id: str, answered: int, correct_count: int
) -> dict[str, Any]:
    """Fecha o nivelamento e grava o nível resultante.

    O nível sai da banda MÉDIA dos itens acertados, não do percentual de
    acerto: acertar 90% de itens A2 não faz ninguém B2, e é exatamente esse o
    erro que um teste não adaptativo comete.
    """
    items = (
        supabase.table("pathr_english_item")
        .select("cefr_band,is_correct,skill")
        .eq("assessment_id", assessment_id)
        .execute()
        .data
        or []
    )
    correct_bands = [
        BANDS.index(item["cefr_band"])
        for item in items
        if item.get("is_correct") and item.get("cefr_band") in BANDS
    ]
    level = BANDS[round(sum(correct_bands) / len(correct_bands))] if correct_bands else "A1"

    sub_scores: dict[str, Any] = {}
    for skill in {item.get("skill") for item in items if item.get("skill")}:
        of_skill = [item for item in items if item.get("skill") == skill]
        hits = sum(1 for item in of_skill if item.get("is_correct"))
        sub_scores[skill] = round(100 * hits / len(of_skill))

    supabase.table("pathr_english_assessment").update(
        {
            "status": "done",
            "cefr_result": level,
            "sub_scores": sub_scores,
            "finished_at": _now().isoformat(),
        }
    ).eq("id", assessment_id).execute()

    supabase.table("pathr_english_profile").update(
        {
            "cefr_level": level,
            "sub_scores": sub_scores,
            "last_assessment_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
        }
    ).eq("user_id", str(user["id"])).execute()

    log_activity(
        supabase,
        user=user,
        kind="english_assessment",
        title=f"Nivelamento concluído — {level}",
        ref_id=assessment_id,
        minutes=12,
        detail={"level": level, "correct": correct_count, "answered": answered},
    )
    return {"cefr_level": level, "sub_scores": sub_scores,
            "correct": correct_count, "answered": answered}


@router.get("/vocab")
def list_vocab(
    due_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Baralho de vocabulário. `due_only` traz só o que vence hoje — é a
    única visão que importa numa sessão de revisão."""
    query = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("user_id", str(current_user["id"]))
    )
    if due_only:
        query = query.lte("due_at", _now().isoformat())
    return query.order("due_at").limit(max(1, min(limit, 200))).execute().data or []


class VocabReview(BaseModel):
    # Qualidade da lembrança, na escala do SM-2: 0 esqueci, 5 lembrei na hora.
    quality: int = Field(ge=0, le=5)


@router.post("/vocab/{vocab_id}/review")
def review_vocab(
    vocab_id: str,
    payload: VocabReview,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Aplica o SM-2 e reagenda o cartão.

    SM-2 e não um intervalo fixo porque o que consolida vocabulário é revisar
    ANTES de esquecer, e esse ponto é diferente para cada palavra e cada
    pessoa. Um erro (quality < 3) zera o intervalo: a palavra volta hoje.
    """
    from datetime import timedelta

    rows = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("id", vocab_id)
        .eq("user_id", str(current_user["id"]))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão não encontrado.")
    card = rows[0]

    ease = float(card.get("ease") or 2.5)
    repetitions = int(card.get("repetitions") or 0)
    interval = int(card.get("interval_days") or 0)

    if payload.quality < 3:
        repetitions = 0
        interval = 0
    else:
        repetitions += 1
        interval = 1 if repetitions == 1 else 6 if repetitions == 2 else round(interval * ease)
        ease = max(
            1.3,
            ease + (0.1 - (5 - payload.quality) * (0.08 + (5 - payload.quality) * 0.02)),
        )

    updated = (
        supabase.table("pathr_english_vocab")
        .update(
            {
                "ease": round(ease, 2),
                "repetitions": repetitions,
                "interval_days": interval,
                "due_at": (_now() + timedelta(days=max(interval, 0))).isoformat(),
            }
        )
        .eq("id", vocab_id)
        .execute()
        .data[0]
    )
    return updated
