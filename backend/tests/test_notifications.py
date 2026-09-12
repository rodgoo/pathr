"""Quando cada aviso sai. Sem banco e sem e-mail: só a regra.

É o tipo de código que erra calado — um e-mail na hora errada, no fuso errado,
ou duas vezes, não quebra nada e só aparece na caixa de entrada de quem usa.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import notifications as avisos

SP = ZoneInfo("America/Sao_Paulo")
TUDO_LIGADO = {avisos.LEMBRETE: True, avisos.RESUMO: True, avisos.RISCO: True}


def _quando(dia: int, hora: int) -> datetime:
    # 2026-09-07 é uma segunda-feira.
    return datetime(2026, 9, dia, hora, 0, tzinfo=SP)


def test_lembrete_sai_de_manha():
    assert avisos.devidos(_quando(8, 8), TUDO_LIGADO, False, 0, set()) == [avisos.LEMBRETE]


def test_nada_sai_fora_das_janelas():
    for hora in (0, 7, 12, 15, 19, 23):
        assert avisos.devidos(_quando(8, hora), TUDO_LIGADO, False, 3, set()) == []


def test_janela_de_duas_horas_cobre_o_atraso():
    """A máquina suspende e o cron atrasa. Hora exata perderia o dia inteiro."""
    assert avisos.LEMBRETE in avisos.devidos(_quando(8, 9), TUDO_LIGADO, False, 0, set())
    assert avisos.RISCO in avisos.devidos(_quando(8, 21), TUDO_LIGADO, False, 2, set())


def test_segunda_recebe_o_resumo_antes_do_plano():
    """Primeiro o que aconteceu, depois o que fazer."""
    assert avisos.devidos(_quando(7, 8), TUDO_LIGADO, False, 0, set()) == [
        avisos.RESUMO,
        avisos.LEMBRETE,
    ]


def test_resumo_so_na_segunda():
    assert avisos.RESUMO not in avisos.devidos(_quando(9, 8), TUDO_LIGADO, False, 0, set())


def test_risco_so_para_quem_tem_sequencia_e_nao_estudou():
    assert avisos.devidos(_quando(8, 20), TUDO_LIGADO, False, 5, set()) == [avisos.RISCO]
    # Já estudou hoje: avisar seria mentira.
    assert avisos.devidos(_quando(8, 20), TUDO_LIGADO, True, 5, set()) == []
    # Sem sequência não há o que perder.
    assert avisos.devidos(_quando(8, 20), TUDO_LIGADO, False, 0, set()) == []


@pytest.mark.parametrize("tipo", [avisos.LEMBRETE, avisos.RESUMO, avisos.RISCO])
def test_preferencia_desligada_cala_o_aviso(tipo):
    desligado = {**TUDO_LIGADO, tipo: False}
    manha = avisos.devidos(_quando(7, 8), desligado, False, 5, set())
    noite = avisos.devidos(_quando(7, 20), desligado, False, 5, set())
    assert tipo not in manha + noite


def test_o_que_ja_saiu_hoje_nao_sai_de_novo():
    """A trava contra repetição é esta, e não a estreiteza da janela."""
    ja = {avisos.LEMBRETE, avisos.RESUMO}
    assert avisos.devidos(_quando(7, 9), TUDO_LIGADO, False, 0, ja) == []


def test_o_relogio_e_o_da_pessoa():
    """8h em Lisboa não são 8h em São Paulo, e o servidor roda em UTC."""
    utc = datetime(2026, 9, 8, 11, 0, tzinfo=ZoneInfo("UTC"))
    em_sp = utc.astimezone(SP)  # 8h
    em_lisboa = utc.astimezone(ZoneInfo("Europe/Lisbon"))  # 12h
    assert avisos.devidos(em_sp, TUDO_LIGADO, False, 0, set()) == [avisos.LEMBRETE]
    assert avisos.devidos(em_lisboa, TUDO_LIGADO, False, 0, set()) == []
