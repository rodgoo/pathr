"""Sequência de estudos em dupla.

O que se segura: conta só os dias em que OS DOIS estudaram; a sequência
continua viva durante o dia de hoje enquanto um dos dois ainda não estudou;
um dia em que só um estudou quebra; e ela só aparece entre amigos aceitos.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.services import sequencia_dupla as S
from tests.fake_supabase import FakeSupabase

HOJE = date(2026, 9, 13)


def _dias(*atras):
    return {HOJE - timedelta(days=n) for n in atras}


def test_conta_so_os_dias_em_que_os_dois_estudaram():
    r = S.calcular(_dias(0, 1, 2, 3), _dias(0, 1, 2), HOJE)
    assert r == {"atual": 3, "recorde": 3, "hoje_voce": True, "hoje_amigo": True}


def test_hoje_sem_um_dos_dois_a_sequencia_ainda_vale_ate_ontem():
    r = S.calcular(_dias(0, 1, 2), _dias(1, 2), HOJE)
    assert r["atual"] == 2 and r["hoje_voce"] is True and r["hoje_amigo"] is False


def test_um_dia_so_de_um_quebra_e_o_recorde_fica():
    # Juntos de 10 a 5 dias atrás (6 dias), depois só um estudou no dia 4.
    meus = _dias(*range(0, 11))
    dele = _dias(*range(5, 11), 0, 1)
    r = S.calcular(meus, dele, HOJE)
    assert r["atual"] == 2 and r["recorde"] == 6


def test_sem_dia_juntos_ontem_nem_hoje_zera():
    assert S.calcular(_dias(5, 6), _dias(5, 6), HOJE)["atual"] == 0


ANA = "aaaaaaaa-0000-0000-0000-000000000001"
BRUNO = "bbbbbbbb-0000-0000-0000-000000000002"
CARLA = "cccccccc-0000-0000-0000-000000000003"


def test_lista_de_amigos_traz_a_sequencia_so_de_quem_e_amigo():
    hoje = date.today()
    dias = [(hoje - timedelta(days=n)).isoformat() for n in (0, 1, 2)]
    banco = FakeSupabase(
        pathr_user=[
            {"id": uid, "name": nome, "username": nome.lower(), "avatar_path": None}
            for uid, nome in ((ANA, "Ana"), (BRUNO, "Bruno"), (CARLA, "Carla"))
        ],
        pathr_profile=[],
        pathr_tag=[],
        pathr_user_tag=[],
        pathr_friendship=[
            {"id": "f1", "requester_id": ANA, "addressee_id": BRUNO, "status": "accepted"},
            {"id": "f2", "requester_id": CARLA, "addressee_id": ANA, "status": "pending"},
        ],
        pathr_study_day=[{"user_id": uid, "day": d} for uid in (ANA, BRUNO, CARLA) for d in dias],
    )
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: {"id": ANA, "timezone_name": None}
    try:
        resposta = TestClient(app).get("/social/amigos").json()
    finally:
        app.dependency_overrides.clear()
    bruno = resposta["amigos"][0]
    assert bruno["sequencia"]["atual"] == 3 and bruno["sequencia"]["hoje_amigo"] is True
    # Convite pendente não revela em que dias a pessoa estudou.
    assert "sequencia" not in resposta["recebidos"][0]
