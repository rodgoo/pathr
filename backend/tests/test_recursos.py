"""Feature flags: quem vê cada recurso e quem pode ligar/desligar.

O que este arquivo trava:
- "todos" liga para qualquer um; "admin" só para super admin; "ninguem" para
  ninguém — e a resolução é no servidor, não na tela;
- só super admin lista e muda os flags;
- a chave desconhecida e o estado inválido são recusados.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.services import features
from tests.fake_supabase import FakeSupabase

ADMIN = {"id": "11111111-0000-0000-0000-000000000001", "email": "chefe@exemplo.com", "name": "Chefe"}
ANA = {"id": "22222222-0000-0000-0000-000000000002", "email": "ana@exemplo.com", "name": "Ana"}


@pytest.fixture(autouse=True)
def _admins(monkeypatch):
    monkeypatch.setattr(settings, "super_admin_emails", ["chefe@exemplo.com"])


@pytest.fixture
def banco():
    return FakeSupabase(pathr_feature_flag=[])


@pytest.fixture
def como(banco):
    atual = {}
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: atual["user"]
    cliente = TestClient(app)

    def trocar(user):
        atual["user"] = user
        return cliente

    yield trocar
    app.dependency_overrides.clear()


def test_resolucao_por_estado(banco):
    # candidaturas nasce "admin" no registro.
    assert features.habilitadas_para(ADMIN, banco)["candidaturas"] is True
    assert features.habilitadas_para(ANA, banco)["candidaturas"] is False

    banco.tabelas["pathr_feature_flag"] = [{"key": "candidaturas", "state": "todos"}]
    assert features.habilitadas_para(ANA, banco)["candidaturas"] is True

    banco.tabelas["pathr_feature_flag"] = [{"key": "candidaturas", "state": "ninguem"}]
    assert features.habilitadas_para(ADMIN, banco)["candidaturas"] is False


def test_features_do_usuario(como):
    corpo = como(ANA).get("/features").json()
    assert corpo == {"candidaturas": False}
    corpo = como(ADMIN).get("/features").json()
    assert corpo == {"candidaturas": True}


def test_so_super_admin_lista_e_muda(como, banco):
    assert como(ANA).get("/admin/recursos").status_code == 404
    assert como(ANA).put("/admin/recursos/candidaturas", json={"state": "todos"}).status_code == 404

    lista = como(ADMIN).get("/admin/recursos").json()
    assert lista[0]["key"] == "candidaturas" and lista[0]["state"] == "admin" and lista[0]["default"] == "admin"
    assert lista[0]["label"] and lista[0]["description"]


def test_admin_liga_para_todos(como, banco):
    resposta = como(ADMIN).put("/admin/recursos/candidaturas", json={"state": "todos"})
    assert resposta.status_code == 200 and resposta.json() == {"key": "candidaturas", "state": "todos"}
    # Agora a Ana passa a ver.
    assert como(ANA).get("/features").json()["candidaturas"] is True


def test_chave_e_estado_invalidos(como):
    assert como(ADMIN).put("/admin/recursos/nao-existe", json={"state": "todos"}).status_code == 404
    assert como(ADMIN).put("/admin/recursos/candidaturas", json={"state": "talvez"}).status_code == 422
