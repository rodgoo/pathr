"""Erros de validação chegam em português, com o rótulo do campo."""

from fastapi.testclient import TestClient

from app.main import app


def test_email_invalido_no_login_vem_em_portugues():
    resposta = TestClient(app).post("/auth/login", json={"email": "sem-arroba", "password": "qualquer"})
    assert resposta.status_code == 422
    detalhe = resposta.json()["detail"]
    assert detalhe == "E-mail: informe um e-mail válido, como nome@exemplo.com."


def test_campo_faltando_e_texto_curto_em_portugues():
    cliente = TestClient(app)
    faltando = cliente.post("/auth/login", json={"password": "x"}).json()["detail"]
    assert faltando == "E-mail: preencha este campo."
    curta = cliente.post(
        "/auth/signup",
        json={"name": "Ana", "email": "ana@exemplo.com", "password": "curta", "birth_date": "1990-01-01",
              "city": "Vitória", "state": "ES"},
    ).json()["detail"]
    assert curta == "Senha: use ao menos 10 caracteres."


def test_nenhum_detalhe_de_validacao_sai_em_ingles():
    for corpo in ({"email": "a@", "password": "x"}, {}, {"email": 123, "password": None}):
        detalhe = TestClient(app).post("/auth/login", json=corpo).json()["detail"]
        for palavra in ("should", "value is", "field required", "valid email", "Input"):
            assert palavra not in detalhe, detalhe
