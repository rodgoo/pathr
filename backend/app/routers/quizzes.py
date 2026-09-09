"""Quizzes: gerar com IA, responder e realimentar o perfil.

O quiz não existe para dar nota. Ele existe porque é a única evidência real
de proficiência que o app consegue coletar — o currículo é o que a pessoa
escreveu sobre si, e concluir um módulo prova que ela estudou, não que
aprendeu. Por isso o resultado atualiza `pathr_user_tag` com confiança alta,
e é o único caminho que faz isso.

A resposta correta NUNCA vai junto com a pergunta: o cliente recebe enunciado
e alternativas, e só vê o gabarito depois de responder. Mandar tudo de uma vez
transformaria o quiz em decoração.
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

router = APIRouter(prefix="/quizzes", tags=["quiz"])

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "questoes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "enunciado": {"type": "STRING"},
                    "codigo": {"type": "STRING"},
                    "linguagem": {"type": "STRING"},
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correta": {"type": "INTEGER"},
                    "explicacao": {"type": "STRING"},
                    "dificuldade": {"type": "STRING"},
                },
                "required": ["enunciado", "alternativas", "correta", "explicacao"],
            },
        },
    },
    "required": ["questoes"],
}

SYSTEM_PROMPT = """Você escreve quizzes técnicos em português do Brasil para avaliar competência real.

Regras:

1. Toda questão testa APLICAÇÃO, não memorização de definição. Prefira
   cenários (um trecho de código com um problema, uma decisão de projeto a
   tomar) a perguntas do tipo o que significa X.
2. Exatamente 4 alternativas. O campo correta é o índice de 0 a 3.
3. As alternativas erradas precisam ser plausíveis: cada uma deve refletir um
   engano que uma pessoa real comete. Alternativa absurda entrega a resposta.
4. A explicação diz por que a certa está certa E por que a mais tentadora das
   erradas está errada. Duas a quatro frases.
5. O campo codigo é opcional; quando existir, use o campo linguagem
   (java, python, javascript, sql...). Não coloque a resposta em comentário.
6. O campo dificuldade: facil, medio ou dificil. Distribua conforme o nível
   informado — não faça todas fáceis.
7. Responda apenas o JSON."""


class GenerateQuiz(BaseModel):
    tag_ids: list[str] = Field(default_factory=list, max_length=6)
    node_id: Optional[str] = None
    question_count: int = Field(default=6, ge=3, le=15)
    difficulty: str = Field(default="medio", pattern="^(facil|medio|dificil|adaptativo)$")


class SubmitAnswers(BaseModel):
    # question_id -> índice escolhido
    answers: dict[str, int]
    duration_s: int = Field(default=0, ge=0, le=7200)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    payload: GenerateQuiz,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Gera um quiz sobre as tags pedidas, calibrado pelo nível atual."""
    user_id = str(current_user["id"])
    tag_ids = payload.tag_ids
    if not tag_ids and payload.node_id:
        node = (
            supabase.table("pathr_roadmap_node")
            .select("tag_ids")
            .eq("id", payload.node_id)
            .limit(1)
            .execute()
            .data
        )
        tag_ids = [str(tag) for tag in ((node[0].get("tag_ids") if node else None) or [])]
    if not tag_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Informe ao menos uma tecnologia."
        )

    tags = (
        supabase.table("pathr_tag").select("id,name").in_("id", tag_ids).execute().data or []
    )
    if not tags:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecnologia não encontrada.")
    names = [tag["name"] for tag in tags]

    levels = (
        supabase.table("pathr_user_tag")
        .select("tag_id,proficiency")
        .eq("user_id", user_id)
        .in_("tag_id", tag_ids)
        .execute()
        .data
        or []
    )
    average = (
        sum(int(row.get("proficiency") or 0) for row in levels) / len(levels) if levels else 0
    )

    prompt = (
        f"TECNOLOGIAS: {', '.join(names)}\n"
        f"NIVEL ATUAL DA PESSOA: {average:.1f} de 5\n"
        f"QUANTIDADE DE QUESTOES: {payload.question_count}\n"
        f"DIFICULDADE PEDIDA: {payload.difficulty}\n\n"
        "Escreva questoes que uma pessoa neste nivel consiga responder pensando, "
        "mas nao consiga responder por eliminacao."
    )
    result = await generate_json(SYSTEM_PROMPT, prompt, QUIZ_SCHEMA)
    questions = _clean_questions(result.content.get("questoes"))
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não devolveu questões utilizáveis. Tente de novo.",
        )

    quiz = (
        supabase.table("pathr_quiz")
        .insert(
            {
                "user_id": user_id,
                "title": str(result.content.get("titulo") or f"Quiz de {names[0]}")[:200],
                "kind": "practice",
                "node_id": payload.node_id,
                "tag_ids": tag_ids,
                "difficulty": payload.difficulty,
                "question_count": len(questions),
                "generated_by": result.model,
            }
        )
        .execute()
        .data[0]
    )

    supabase.table("pathr_question").insert(
        [
            {
                "quiz_id": quiz["id"],
                "type": "single",
                "prompt": question["enunciado"],
                "code_snippet": question["codigo"] or None,
                "code_language": question["linguagem"] or None,
                "options": question["alternativas"],
                "correct": {"index": question["correta"]},
                "explanation": question["explicacao"],
                "difficulty": question["dificuldade"],
                "tag_ids": tag_ids,
                "order_index": index,
            }
            for index, question in enumerate(questions)
        ]
    ).execute()

    return get_quiz(str(quiz["id"]), current_user, supabase)


def _clean_questions(raw: Any) -> list[dict[str, Any]]:
    """Descarta o que não dá para usar em vez de gravar questão quebrada.

    Uma questão sem 4 alternativas ou com índice de resposta fora do intervalo
    seria uma questão impossível de acertar — e o usuário não teria como saber
    que o erro foi nosso.
    """
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("enunciado") or "").strip()
        options = [str(option).strip() for option in (item.get("alternativas") or []) if str(option).strip()]
        try:
            correct = int(item.get("correta"))
        except (TypeError, ValueError):
            continue
        if not prompt or len(options) != 4 or not 0 <= correct <= 3:
            continue
        difficulty = str(item.get("dificuldade") or "").strip().lower()
        cleaned.append(
            {
                "enunciado": prompt[:2000],
                "codigo": str(item.get("codigo") or "").strip()[:4000],
                "linguagem": str(item.get("linguagem") or "").strip()[:30],
                "alternativas": options,
                "correta": correct,
                "explicacao": str(item.get("explicacao") or "").strip()[:2000],
                "dificuldade": difficulty if difficulty in {"facil", "medio", "dificil"} else "medio",
            }
        )
    return cleaned


@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O quiz para responder — SEM gabarito e SEM explicação."""
    quiz = _owned_quiz(supabase, quiz_id, str(current_user["id"]))
    questions = (
        supabase.table("pathr_question")
        .select("id,prompt,code_snippet,code_language,options,difficulty,order_index")
        .eq("quiz_id", quiz_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    return {**quiz, "questions": questions}


def _owned_quiz(supabase: Client, quiz_id: str, user_id: str) -> dict[str, Any]:
    rows = (
        supabase.table("pathr_quiz")
        .select("*")
        .eq("id", quiz_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz não encontrado.")
    return rows[0]


@router.post("/{quiz_id}/submit")
def submit_quiz(
    quiz_id: str,
    payload: SubmitAnswers,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Corrige, devolve o gabarito com explicações e realimenta o perfil.

    A correção acontece aqui e não no cliente pelo motivo óbvio — o cliente
    não tem o gabarito — e por um menos óbvio: é este o momento em que a
    proficiência por tag pode ser atualizada com evidência.
    """
    user_id = str(current_user["id"])
    quiz = _owned_quiz(supabase, quiz_id, user_id)
    questions = (
        supabase.table("pathr_question")
        .select("*")
        .eq("quiz_id", quiz_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    if not questions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz sem questões.")

    results = []
    correct_count = 0
    for question in questions:
        given = payload.answers.get(str(question["id"]))
        expected = int((question.get("correct") or {}).get("index", -1))
        is_correct = given is not None and int(given) == expected
        correct_count += int(is_correct)
        results.append(
            {
                "question_id": str(question["id"]),
                "answer": given,
                "correct_index": expected,
                "is_correct": is_correct,
                "explanation": question.get("explanation"),
            }
        )

    score = round(100 * correct_count / len(questions), 1)
    tag_ids = [str(tag) for tag in (quiz.get("tag_ids") or [])]
    breakdown = {"score": score, "correct": correct_count, "total": len(questions)}

    attempt = (
        supabase.table("pathr_attempt")
        .insert(
            {
                "quiz_id": quiz_id,
                "user_id": user_id,
                "finished_at": _now().isoformat(),
                "score": score,
                "correct_count": correct_count,
                "duration_s": payload.duration_s,
                "answers": results,
                "tag_breakdown": breakdown,
            }
        )
        .execute()
        .data[0]
    )

    _apply_result_to_tags(supabase, user_id, tag_ids, score)
    log_activity(
        supabase,
        user=current_user,
        kind="quiz_done",
        title=quiz.get("title") or "Quiz",
        ref_id=quiz_id,
        minutes=max(1, payload.duration_s // 60),
        tag_ids=tag_ids,
        detail=breakdown,
    )

    return {
        "attempt_id": str(attempt["id"]),
        "score": score,
        "correct_count": correct_count,
        "total": len(questions),
        "results": results,
    }


def _apply_result_to_tags(
    supabase: Client, user_id: str, tag_ids: list[str], score: float
) -> None:
    """Traduz a nota em proficiência.

    Só mexe nos extremos, e de forma assimétrica: 80% ou mais sobe um nível
    (teto 4), abaixo de 40% desce um (piso 1). A faixa do meio não mexe em
    nada — um 60% não é evidência de nada em particular, e ficar oscilando o
    perfil a cada quiz faria o roadmap se reescrever sem motivo.

    A confiança sobe sempre: mesmo um resultado ambíguo é mais evidência do
    que a estimativa do currículo tinha.
    """
    if not tag_ids:
        return
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
        if not rows:
            continue
        row = rows[0]
        current = int(row.get("proficiency") or 0)
        if score >= 80:
            proficiency = min(4, current + 1)
        elif score < 40:
            proficiency = max(1, current - 1)
        else:
            proficiency = current
        supabase.table("pathr_user_tag").update(
            {
                "proficiency": proficiency,
                "confidence": min(1.0, float(row.get("confidence") or 0.5) + 0.25),
                "source": "quiz",
                "last_assessed_at": _now().isoformat(),
            }
        ).eq("id", row["id"]).execute()


@router.get("")
def list_quizzes(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return (
        supabase.table("pathr_quiz")
        .select("id,title,kind,difficulty,question_count,tag_ids,created_at")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )


@router.get("/{quiz_id}/attempts")
def list_attempts(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _owned_quiz(supabase, quiz_id, str(current_user["id"]))
    return (
        supabase.table("pathr_attempt")
        .select("id,score,correct_count,duration_s,finished_at,tag_breakdown")
        .eq("quiz_id", quiz_id)
        .order("finished_at", desc=True)
        .execute()
        .data
        or []
    )
