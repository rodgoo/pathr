"""Feynman: explicar com as próprias palavras, e ser cobrado pela lacuna.

## Por que este pilar precisa existir separado dos outros três

O app já tinha recordação ativa (o quiz), repetição espaçada (o SM-2) e a
reciclagem que liga as duas. Nenhum dos três flagra a ilusão de competência —
ler sobre closures, acompanhar o raciocínio de quem escreveu, e sair achando
que entendeu. Reconhecer a alternativa certa entre quatro é muito mais fácil
que produzir a explicação do zero, e é por isso que dá para ir bem num quiz
sobre algo que não se sabe explicar.

Escrever a explicação não deixa esconder: ou a ideia se sustenta em prosa, ou
o texto trava exatamente onde o entendimento acaba.

## O que a correção faz, e o que ela deliberadamente não faz

Ela NÃO reescreve a explicação. Devolver uma versão melhorada seria dar a
resposta — a pessoa leria, concordaria, e a ilusão voltaria intacta. O que sai
daqui é: uma nota, o que ficou de pé, e a lista do que ficou pela metade.

Cada lacuna vira um item em `pathr_review_item` vencendo HOJE. Ela volta como
questão reescrita no próximo quiz da trilha, pelo mesmo caminho de um erro de
quiz. É aqui que os quatro pilares deixam de ser quatro recursos soltos: o
Feynman acha o buraco, a repetição espaçada marca a volta, a recordação ativa
cobra, e a reciclagem reescreve para não virar decoreba da frase.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services import review
from app.services.progress import log_activity

router = APIRouter(prefix="/explanations", tags=["feynman"])

GRADE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "nota": {"type": "INTEGER"},
        "retorno": {"type": "STRING"},
        "sustenta": {"type": "ARRAY", "items": {"type": "STRING"}},
        "lacunas": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "conceito": {"type": "STRING"},
                    "por_que": {"type": "STRING"},
                },
                "required": ["conceito", "por_que"],
            },
        },
    },
    "required": ["nota", "retorno", "lacunas"],
}

SYSTEM_PROMPT = """Você avalia explicações pelo método Feynman, em português do Brasil.

A pessoa tentou explicar um conceito técnico com as próprias palavras, como se
explicasse para alguém que não conhece o assunto. Seu trabalho é dizer onde a
explicação SE SUSTENTA sozinha e onde ela depende de algo que não foi dito.

Regras que não podem ser quebradas:

1. NUNCA reescreva a explicação nem entregue a versão correta. Quem lê uma
   explicação pronta concorda com ela e volta a achar que entendeu — que é
   exatamente a ilusão que este exercício existe para quebrar. Aponte a
   lacuna; não a preencha.
2. `nota` de 0 a 100 é quanto da ideia a explicação sustenta SOZINHA, para
   alguém que não conhece o assunto. Texto certo mas que só funciona para quem
   já sabe não passa de 60.
3. Julgue a EXPLICAÇÃO, não a escrita. Erro de português, frase torta e falta
   de jargão não descontam nada; o que desconta é a ideia faltando, a relação
   de causa não dita, e a afirmação errada.
4. `lacunas` é o coração da resposta. Cada uma tem `conceito` (a ideia que
   faltou, em até 8 palavras, descrevendo a IDEIA e não o texto) e `por_que`
   (uma frase dizendo o que exatamente ficou de fora). No máximo 4, as mais
   importantes. Explicação boa pode ter zero — não invente lacuna para parecer
   criterioso.
5. Afirmação ERRADA vira lacuna, e o `por_que` diz que está errada. Deixar
   passar é pior que qualquer omissão: a pessoa segue confiante no engano.
6. `retorno` são duas a quatro frases, na segunda pessoa, ditas a quem está
   aprendendo. Comece pelo que funcionou.
7. Responda apenas o JSON."""


class SubmitExplanation(BaseModel):
    concept: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=40, max_length=8000)
    node_id: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_explanation(
    payload: SubmitExplanation,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Corrige a explicação e transforma cada lacuna em revisão.

    O mínimo de 40 caracteres não é burocracia: uma linha não é explicação, e
    corrigir uma linha gastaria uma chamada de IA para devolver "escreva mais".
    """
    user_id = str(current_user["id"])

    tag_ids: list[str] = []
    if payload.node_id:
        node = _owned_node(supabase, payload.node_id, user_id)
        tag_ids = [str(tag) for tag in (node.get("tag_ids") or [])]

    prompt = (
        f"CONCEITO QUE A PESSOA SE PROPOS A EXPLICAR: {payload.concept}\n\n"
        "--- EXPLICACAO DELA ---\n"
        f"{payload.content}\n"
        "--- FIM ---"
    )
    resultado = await generate_json(SYSTEM_PROMPT, prompt, GRADE_SCHEMA)
    conteudo = resultado.content or {}

    nota = _nota(conteudo.get("nota"))
    lacunas = _lacunas(conteudo.get("lacunas"))

    linha = (
        supabase.table("pathr_explanation")
        .insert(
            {
                "user_id": user_id,
                "node_id": payload.node_id,
                "concept": payload.concept.strip()[:200],
                "content": payload.content,
                "score": nota,
                "feedback": str(conteudo.get("retorno") or "").strip()[:2000] or None,
                "gaps": lacunas,
                "tag_ids": tag_ids,
                "graded_by": resultado.model,
            }
        )
        .execute()
        .data[0]
    )

    viraram_revisao = _para_revisao(supabase, user_id, lacunas, tag_ids)

    log_activity(
        supabase,
        user=current_user,
        kind="explanation_done",
        title=payload.concept.strip()[:200],
        ref_id=str(linha["id"]),
        # Explicar do zero custa tempo real de raciocínio, e é o exercício mais
        # caro que o app pede. Os minutos são estimados pelo tamanho do texto,
        # com teto — não há como cronometrar sem vigiar a digitação.
        minutes=min(30, max(5, len(payload.content) // 120)),
        tag_ids=tag_ids,
        detail={"score": nota, "lacunas": len(lacunas)},
    )

    return {
        "id": str(linha["id"]),
        "score": nota,
        "feedback": linha.get("feedback"),
        "sustenta": [str(item)[:300] for item in (conteudo.get("sustenta") or [])][:5],
        "gaps": lacunas,
        "viraram_revisao": viraram_revisao,
    }


@router.get("")
def list_explanations(
    node_id: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O histórico, do mais recente para o mais antigo.

    Explicar o mesmo conceito de novo semanas depois e comparar as duas
    versões É o método — por isso aqui é lista, e não a última explicação.
    """
    query = (
        supabase.table("pathr_explanation")
        .select("id,concept,score,feedback,gaps,node_id,created_at")
        .eq("user_id", str(current_user["id"]))
    )
    if node_id:
        query = query.eq("node_id", node_id)
    return (
        query.order("created_at", desc=True).limit(max(1, min(limit, 100))).execute().data or []
    )


def _nota(bruta: Any) -> int:
    try:
        return max(0, min(100, int(bruta)))
    except (TypeError, ValueError):
        # Modelo que não devolveu número não invalida a correção inteira: o
        # retorno em prosa e as lacunas continuam valendo.
        return 0


def _lacunas(bruto: Any) -> list[dict[str, str]]:
    """Só o que tem conceito. Uma lacuna sem nome não vira item de revisão."""
    if not isinstance(bruto, list):
        return []
    limpas: list[dict[str, str]] = []
    vistas: set[str] = set()
    for item in bruto:
        if not isinstance(item, dict):
            continue
        conceito = str(item.get("conceito") or "").strip()[:200]
        if not conceito:
            continue
        chave = review.concept_key(conceito)
        if chave in vistas:
            continue
        vistas.add(chave)
        limpas.append(
            {"conceito": conceito, "por_que": str(item.get("por_que") or "").strip()[:500]}
        )
    return limpas[:4]


def _para_revisao(
    supabase: Client, user_id: str, lacunas: list[dict[str, str]], tag_ids: list[str]
) -> int:
    """Cada lacuna vira item vencendo hoje, e devolve quantas entraram.

    É o mesmo caminho de um erro de quiz, de propósito: uma lacuna descoberta
    explicando não é diferente de uma descoberta errando — as duas são coisas
    que a pessoa não sabe, e as duas precisam voltar reescritas.

    Best-effort. Perder um item de revisão custa uma repetição; perder a
    correção que a pessoa acabou de esperar custa o exercício inteiro.
    """
    if not lacunas:
        return 0
    tag_id = tag_ids[0] if tag_ids else None

    ja_pendentes: set[str] = set()
    if tag_id:
        try:
            ja_pendentes = {
                review.concept_key(linha.get("front"))
                for linha in (
                    supabase.table("pathr_review_item")
                    .select("front")
                    .eq("user_id", user_id)
                    .eq("tag_id", tag_id)
                    .limit(200)
                    .execute()
                    .data
                    or []
                )
            }
        except Exception:  # noqa: BLE001
            ja_pendentes = set()

    entraram = 0
    for lacuna in lacunas:
        if review.concept_key(lacuna["conceito"]) in ja_pendentes:
            continue
        try:
            supabase.table("pathr_review_item").insert(
                {
                    "user_id": user_id,
                    "kind": "concept",
                    "tag_id": tag_id,
                    "front": lacuna["conceito"],
                    "back": lacuna["por_que"] or lacuna["conceito"],
                    "due_at": _now().isoformat(),
                    "lapses": 1,
                }
            ).execute()
            entraram += 1
        except Exception:  # noqa: BLE001
            continue
    return entraram


def _owned_node(supabase: Client, node_id: str, user_id: str) -> dict[str, Any]:
    """O módulo é desta pessoa?

    `pathr_roadmap_node` não tem `user_id` — ele pertence ao roadmap, e é o
    roadmap que pertence a alguém. Sem isto, um id adivinhado ligaria a
    explicação de alguém ao módulo de outra pessoa.
    """
    linhas = (
        supabase.table("pathr_roadmap_node").select("*").eq("id", node_id).limit(1).execute().data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    node = linhas[0]
    dono = (
        supabase.table("pathr_roadmap")
        .select("id")
        .eq("id", node["roadmap_id"])
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not dono:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Módulo não encontrado.")
    return node
