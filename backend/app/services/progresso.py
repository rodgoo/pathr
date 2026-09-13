"""O progresso do plano, contando o que já se fez nos módulos em andamento.

## O que estava errado

O percentual contava só módulo CONCLUÍDO. Quem fez o quiz e o material de um
módulo de seis horas via 0% — no card "Continue", na barra do plano e na
lateral — até marcar o módulo inteiro como feito. Para quem estuda uma hora
por dia, isso é uma semana com a barra parada, e barra parada diz "você não
saiu do lugar".

## O que se conta agora

- **Avanço do módulo:** a fração dos itens da lista da semana ligados a ele
  que já foram feitos (material, quiz, explicação, atividade). É o registro do
  que a pessoa fez de verdade; o quiz e a explicação ali são confirmados pelo
  servidor, não por um clique.
- **Progresso do plano:** a média desse avanço, pesada pelas horas estimadas de
  cada módulo. Terminar um módulo de 15 horas anda mais que um de 2.
- Módulo concluído vale inteiro; módulo pulado sai da conta. Módulo em
  andamento para em 95%: o 100% é de quem marcou o módulo como feito.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

_TETO_EM_ANDAMENTO = 0.95


def avanco_por_modulo(checklists: Iterable[dict[str, Any]]) -> dict[str, float]:
    """node_id -> fração dos itens da lista feitos, somando todas as semanas.

    O mesmo item reaparece na semana seguinte enquanto não é feito: cada
    (módulo, tipo) conta uma vez, e vale como feito se foi feito em qualquer
    semana.
    """
    itens: dict[tuple[str, str], bool] = {}
    for semana in checklists:
        for item in semana.get("items") or []:
            node_id = item.get("node_id")
            if not node_id:
                continue  # a revisão espaçada não é de um módulo só
            chave = (str(node_id), str(item.get("tipo") or item.get("id")))
            itens[chave] = itens.get(chave, False) or bool(item.get("feito"))

    totais: dict[str, int] = {}
    feitos: dict[str, int] = {}
    for (node_id, _tipo), feito in itens.items():
        totais[node_id] = totais.get(node_id, 0) + 1
        feitos[node_id] = feitos.get(node_id, 0) + int(feito)
    return {node_id: feitos[node_id] / total for node_id, total in totais.items()}


def avanco_do_modulo(modulo: dict[str, Any], avanco: dict[str, float]) -> Optional[float]:
    """De 0 a 1, ou None para módulo pulado (fora da conta)."""
    status = modulo.get("status")
    if status == "skipped":
        return None
    if status == "done":
        return 1.0
    guardado = int(modulo.get("progress_pct") or 0) / 100
    return min(_TETO_EM_ANDAMENTO, max(guardado, avanco.get(str(modulo.get("id")), 0.0)))


def resumo(modulos: list[dict[str, Any]], avanco: dict[str, float]) -> dict[str, Any]:
    peso_total = feito = 0.0
    for modulo in modulos:
        fracao = avanco_do_modulo(modulo, avanco)
        if fracao is None:
            continue
        peso = float(modulo.get("estimated_hours") or 1)
        peso_total += peso
        feito += peso * fracao
    return {
        "progress_pct": round(100 * feito / peso_total) if peso_total else 0,
        "done_nodes": sum(1 for m in modulos if m.get("status") == "done"),
        "total_nodes": len(modulos),
    }


def com_avanco(modulos: list[dict[str, Any]], avanco: dict[str, float]) -> list[dict[str, Any]]:
    """Os módulos com `progress_pct` já refletindo a lista da semana."""
    saida = []
    for modulo in modulos:
        fracao = avanco_do_modulo(modulo, avanco)
        saida.append({**modulo, "progress_pct": round(100 * fracao) if fracao is not None else 0})
    return saida


def checklists_do_usuario(supabase: Any, user_id: str, roadmap_id: str) -> list[dict[str, Any]]:
    try:
        return (
            supabase.table("pathr_weekly_checklist")
            .select("items")
            .eq("user_id", user_id)
            .eq("roadmap_id", roadmap_id)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        # Sem a lista, vale o que os módulos dizem: progresso a menos é melhor
        # do que a tela do plano quebrada.
        return []
