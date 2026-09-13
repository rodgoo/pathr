"""A sequência de estudos de dois amigos: os dias seguidos em que OS DOIS estudaram.

## A regra

- Conta um dia quando as duas pessoas têm atividade nele (`pathr_study_day`).
- A sequência atual termina hoje, se os dois já estudaram hoje; senão termina
  ontem e continua VIVA até o fim do dia — ninguém perde a sequência às nove da
  manhã só porque o amigo ainda não abriu o app.
- O recorde é a maior sequência na janela lida.

O "hoje" é o de quem olha. Cada dia de estudo foi gravado no fuso de quem
estudou (ver `activity_date`), então amigos em fusos muito diferentes podem
ver um dia de diferença — para quem mora no mesmo país, é o mesmo calendário.

## Por que só entre amigos

A sequência revela em que dias a outra pessoa estudou. Só aparece quando a
amizade foi aceita pelos dois, e só como número e "estudou hoje" — nunca a
lista de dias.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

# Quanto histórico ler para o recorde. Um ano cobre qualquer sequência real e
# fica abaixo do limite de linhas de uma consulta (uma linha por dia).
JANELA_DIAS = 366


def calcular(dias_meus: Iterable[date], dias_dele: Iterable[date], hoje: date) -> dict[str, Any]:
    meus, dele = set(dias_meus), set(dias_dele)
    juntos = meus & dele

    inicio = hoje if hoje in juntos else hoje - timedelta(days=1)
    atual = 0
    dia = inicio
    while dia in juntos:
        atual += 1
        dia -= timedelta(days=1)

    recorde = 0
    for dia in juntos:
        if dia - timedelta(days=1) in juntos:
            continue  # não é começo de sequência
        tamanho = 0
        while dia + timedelta(days=tamanho) in juntos:
            tamanho += 1
        recorde = max(recorde, tamanho)

    return {
        "atual": atual,
        "recorde": max(recorde, atual),
        "hoje_voce": hoje in meus,
        "hoje_amigo": hoje in dele,
    }


def dias_de_estudo(supabase: Any, user_id: str, hoje: date) -> set[date]:
    desde = (hoje - timedelta(days=JANELA_DIAS)).isoformat()
    try:
        linhas = (
            supabase.table("pathr_study_day")
            .select("day")
            .eq("user_id", user_id)
            .gte("day", desde)
            .limit(JANELA_DIAS + 2)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        # Sem a tabela (banco fora do ar), a lista de amigos continua; só a
        # sequência some.
        return set()
    return {date.fromisoformat(str(linha["day"])[:10]) for linha in linhas}
