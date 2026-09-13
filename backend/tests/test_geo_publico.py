"""Sugestão de cidade no cadastro: sem sessão, com limite por IP."""

from fastapi.testclient import TestClient

from app.database import get_supabase
from app.main import app
from tests.fake_supabase import FakeSupabase


def test_cadastro_sugere_cidade_sem_estar_logado():
    banco = FakeSupabase(pathr_rate_event=[])
    app.dependency_overrides[get_supabase] = lambda: banco
    try:
        cliente = TestClient(app)
        cidades = cliente.get("/geo/cidades/publico", params={"q": "Vitória"}).json()
        assert any(c["nome"] == "Vitória" and c["uf"] == "ES" for c in cidades)
        # A rota logada continua exigindo sessão.
        assert cliente.get("/geo/cidades", params={"q": "Vit"}).status_code == 401
        # Uma letra só nem consulta nem conta no limite.
        assert cliente.get("/geo/cidades/publico", params={"q": "V"}).json() == []
    finally:
        app.dependency_overrides.clear()
