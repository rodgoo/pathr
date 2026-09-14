"""A próxima atividade prática de um módulo.

## Sempre há algo para fazer

Cada módulo tem uma fila de enunciados (`pathr_activity_exercise`). Respondeu
um, o próximo é gerado — diferente dos anteriores, na dificuldade que as
notas pedem, e puxando as lacunas que a correção achou. É o método dos outros
pilares aplicado à prática: errar vira o assunto da próxima tarefa.

## Sem a IA, ainda há atividade

Se o modelo não responder (cota, fora do ar, resposta vazia), a atividade sai
do objetivo do módulo, girando entre eles. A aba nunca fica sem nada — que era
exatamente a reclamação.

## O que vai para o modelo

Só dado do sistema: título, objetivos e tecnologias do módulo, os enunciados
que o próprio modelo já escreveu, as notas e os nomes das lacunas. O texto
que a pessoa escreveu NÃO entra aqui — ele só vai para a correção, que tem as
travas contra instrução embutida (routers/explanations.py).
"""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client

from app.ai_providers import AiProviderError, generate_json

logger = logging.getLogger(__name__)

TIPOS = ("codigo", "comandos", "explicacao", "configuracao", "pratica")

SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "enunciado": {"type": "STRING"},
        "tipo": {"type": "STRING"},
        "dicas": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["enunciado", "tipo"],
}

SISTEMA = """Você cria a PRÓXIMA atividade prática de um módulo de estudo, em português do Brasil.

Regras:
1. Uma tarefa só, que a pessoa resolve ESCREVENDO (código, comandos, configuração,
   passo a passo ou uma explicação curta) em 5 a 20 minutos, sem ajuda de IA.
2. Diferente das ANTERIORES: outro cenário, outro recorte do assunto. Nunca repita
   nem reescreva de leve um enunciado da lista.
3. Dificuldade pelas NOTAS RECENTES: média abaixo de 60 → mais simples e focada no
   que faltou; de 60 a 80 → mesmo nível com um detalhe a mais; acima de 80 → um
   degrau acima. Sem notas, comece pelo básico do objetivo.
4. Se houver LACUNAS, exercite pelo menos uma delas, com outras palavras.
5. `enunciado`: 1 a 4 frases concretas, com o contexto necessário (ex.: "Você tem um
   repositório local sem remoto. Escreva os comandos para..."). NUNCA inclua a
   resposta, nem parte dela.
6. `tipo`: "codigo", "comandos", "explicacao" ou "configuracao".
7. `dicas`: até 2 dicas curtas que orientam sem entregar a solução.
8. Fique no assunto do módulo. Responda apenas o JSON."""


def _limpo(texto: Any, limite: int) -> str:
    return " ".join(str(texto or "").split())[:limite]


def _objetivos(node: dict[str, Any]) -> list[str]:
    return [_limpo(o, 300) for o in (node.get("objectives") or []) if _limpo(o, 300)]


def reserva(node: dict[str, Any], quantas_ja: int) -> dict[str, Any]:
    """A atividade sem IA: gira entre os objetivos do módulo."""
    objetivos = _objetivos(node) or [_limpo(node.get("title"), 200) or "o assunto deste módulo"]
    objetivo = objetivos[quantas_ja % len(objetivos)]
    return {
        "statement": (
            f"Mostre na prática: {objetivo.rstrip('.')}. Escreva a solução completa, "
            "com um comentário curto explicando o que cada passo faz."
        ),
        "kind": "pratica",
        "hints": [],
        "generated_by": None,
    }


def _historico(supabase: Client, user_id: str, node_id: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_activity_exercise")
        .select("statement,score,answered_at,created_at")
        .eq("user_id", user_id)
        .eq("node_id", node_id)
        .order("created_at", desc=True)
        .limit(12)
        .execute()
        .data
        or []
    )


def _lacunas_recentes(supabase: Client, user_id: str, node_id: str) -> list[str]:
    try:
        linhas = (
            supabase.table("pathr_explanation")
            .select("gaps")
            .eq("user_id", user_id)
            .eq("node_id", node_id)
            .order("created_at", desc=True)
            .limit(3)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 — sem lacunas a atividade só fica mais genérica
        return []
    nomes: list[str] = []
    for linha in linhas:
        for lacuna in linha.get("gaps") or []:
            nome = _limpo((lacuna or {}).get("conceito") if isinstance(lacuna, dict) else lacuna, 120)
            if nome and nome not in nomes:
                nomes.append(nome)
    return nomes[:6]


def _tecnologias(supabase: Client, node: dict[str, Any]) -> list[str]:
    ids = [str(t) for t in (node.get("tag_ids") or [])]
    if not ids:
        return []
    try:
        return [str(t["name"]) for t in (supabase.table("pathr_tag").select("name").in_("id", ids).execute().data or [])]
    except Exception:  # noqa: BLE001
        return []


async def gerar(supabase: Client, user_id: str, node: dict[str, Any]) -> dict[str, Any]:
    """Gera, grava e devolve a próxima atividade do módulo."""
    node_id = str(node["id"])
    historico = _historico(supabase, user_id, node_id)
    notas = [int(h["score"]) for h in historico if h.get("score") is not None][:5]
    anteriores = [_limpo(h.get("statement"), 400) for h in historico]

    dados: dict[str, Any]
    try:
        prompt = "\n".join(
            [
                f"MÓDULO: {_limpo(node.get('title'), 200)}",
                "OBJETIVOS:",
                *[f"- {o}" for o in _objetivos(node)[:6]],
                f"TECNOLOGIAS: {', '.join(_tecnologias(supabase, node)) or '—'}",
                f"NOTAS RECENTES (0 a 100, mais nova primeiro): {', '.join(map(str, notas)) or 'nenhuma ainda'}",
                "LACUNAS DAS ÚLTIMAS CORREÇÕES:",
                *([f"- {nome}" for nome in _lacunas_recentes(supabase, user_id, node_id)] or ["- nenhuma"]),
                "ANTERIORES (não repita):",
                *([f"- {a}" for a in anteriores] or ["- nenhuma"]),
            ]
        )
        resultado = await generate_json(SISTEMA, prompt, SCHEMA)
        conteudo = resultado.content or {}
        enunciado = str(conteudo.get("enunciado") or "").strip()[:1500]
        if len(enunciado) < 20:
            raise ValueError("enunciado vazio")
        tipo = str(conteudo.get("tipo") or "pratica").strip().lower()
        dados = {
            "statement": enunciado,
            "kind": tipo if tipo in TIPOS else "pratica",
            "hints": [_limpo(d, 240) for d in (conteudo.get("dicas") or []) if _limpo(d, 240)][:2],
            "generated_by": resultado.model,
        }
    except (AiProviderError, ValueError, TypeError, AttributeError) as exc:
        logger.info("atividade sem IA para o módulo (%s)", type(exc).__name__)
        dados = reserva(node, len(historico))

    return (
        supabase.table("pathr_activity_exercise")
        .insert({"user_id": user_id, "node_id": node_id, **dados})
        .execute()
        .data[0]
    )
