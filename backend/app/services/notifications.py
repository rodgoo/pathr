"""Quais avisos uma pessoa deve receber AGORA.

Função pura, separada do envio, porque a regra é o que erra em silêncio: um
e-mail que sai na hora errada, no fuso errado, ou duas vezes, é pior que não
sair — e nada disso aparece em teste de integração.

## O relógio é o da pessoa, não o do servidor

A Fly roda em UTC e quem estuda vive em São Paulo, Lisboa ou onde estiver. O
lembrete das 8h é 8h DELA. Por isso o disparo roda de hora em hora e pergunta,
para cada pessoa, que horas são no fuso dela.

## Janela de duas horas, e não um instante

O disparo pode atrasar: a máquina está suspensa e leva segundos para acordar, o
cron atrasa, uma rodada falha. Uma comparação exata (`hora == 8`) perderia o
aviso do dia inteiro por causa de um minuto. A janela de duas horas cobre o
atraso, e a trava de "já enviado hoje" (pathr_email_log) é que impede a
repetição — não a estreiteza da janela.
"""

from __future__ import annotations

from datetime import datetime

LEMBRETE = "lembrete_diario"
RESUMO = "resumo_semanal"
RISCO = "sequencia_em_risco"

# Manhã: o lembrete e o resumo saem quando o dia ainda cabe. Noite: o aviso de
# sequência sai tarde o bastante para a pessoa já ter tido o dia, e cedo o
# bastante para ela ainda conseguir estudar quinze minutos.
_MANHA = (8, 9)
_NOITE = (20, 21)


def devidos(
    agora_local: datetime,
    preferencias: dict[str, bool],
    teve_atividade_hoje: bool,
    streak_atual: int,
    ja_enviados_hoje: set[str],
) -> list[str]:
    """Os avisos a mandar agora, na ordem em que devem sair."""
    saida: list[str] = []
    hora = agora_local.hour

    if hora in _MANHA:
        # Segunda-feira recebe o resumo da semana que passou ANTES do plano de
        # hoje: primeiro o que aconteceu, depois o que fazer.
        if agora_local.weekday() == 0 and preferencias.get(RESUMO) and RESUMO not in ja_enviados_hoje:
            saida.append(RESUMO)
        if preferencias.get(LEMBRETE) and LEMBRETE not in ja_enviados_hoje:
            saida.append(LEMBRETE)

    if hora in _NOITE and preferencias.get(RISCO) and RISCO not in ja_enviados_hoje:
        # Só quem tem sequência viva e ainda não estudou hoje. Avisar quem não
        # tem nada a perder é só barulho, e avisar quem já estudou é mentira.
        if streak_atual >= 1 and not teve_atividade_hoje:
            saida.append(RISCO)

    return saida
