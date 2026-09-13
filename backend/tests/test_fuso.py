"""O fuso de cada conta vem de onde a pessoa mora.

O que se segura: as exceções dentro de um estado (o oeste do Amazonas em Rio
Branco, Fernando de Noronha), o fuso do estado quando a cidade não se acha, e
mudar a cidade no perfil muda o fuso da conta — que é o que decide quando o
dia de estudo vira.
"""

from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.services import geo
from tests.fake_supabase import FakeSupabase


def test_fuso_pela_cidade_com_as_excecoes_dentro_do_estado():
    assert geo.fuso_de("Vitoria", "ES") == "America/Sao_Paulo"
    assert geo.fuso_de("Manaus", "AM") == "America/Manaus"
    assert geo.fuso_de("Tabatinga", "AM") == "America/Rio_Branco"
    assert geo.fuso_de("Fernando de Noronha", "PE") == "America/Noronha"
    assert geo.fuso_de("Recife", "PE") == "America/Sao_Paulo"
    assert geo.fuso_de("Cuiabá", "Mato Grosso") == "America/Cuiaba"


def test_sem_cidade_vale_o_estado_e_sem_nada_brasilia():
    assert geo.fuso_de("Cidade Que Nao Existe", "RR") == "America/Boa_Vista"
    assert geo.fuso_de(None, None) == "America/Sao_Paulo"


def test_mudar_a_cidade_no_perfil_muda_o_fuso_da_conta():
    uid = "aaaaaaaa-0000-0000-0000-000000000001"
    banco = FakeSupabase(
        pathr_user=[{"id": uid, "name": "Ana", "timezone_name": "America/Sao_Paulo"}],
        pathr_profile=[{"user_id": uid, "city": "Vitória", "state": "ES"}],
    )
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: {"id": uid}
    try:
        resposta = TestClient(app).patch("/profile", json={"city": "Manaus", "state": "AM"})
        sem_cidade = TestClient(app).patch("/profile", json={"bio": "oi"})
    finally:
        app.dependency_overrides.clear()
    assert resposta.status_code == 200 and sem_cidade.status_code == 200
    assert banco.linhas("pathr_user")[0]["timezone_name"] == "America/Manaus"
