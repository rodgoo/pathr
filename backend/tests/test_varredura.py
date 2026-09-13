"""Varredura diária: o segredo, o que sai para o Notion e o e-mail de uma vez.

O que este arquivo segura:
- sem o segredo certo não se lê relato nenhum;
- o relato sai SEM autor — nome, e-mail e @ ficam no banco;
- o erro do servidor vira linha redigida, agrupada por defeito;
- o resumo sai uma vez por dia, e só trava o dia se o e-mail saiu.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_supabase
from app.main import app
from app.services import email as emails
from app.services import erros
from tests.fake_supabase import FakeSupabase

SEGREDO = "segredo-de-teste-da-varredura"
AGORA = datetime.now(timezone.utc)

ANA = {"id": "22222222-0000-0000-0000-000000000002", "email": "ana@exemplo.com", "name": "Ana Souza"}


def _relato(i, kind, horas_atras):
    return {
        "id": f"aaaaaaaa-0000-0000-0000-00000000000{i}",
        "user_id": ANA["id"],
        "kind": kind,
        "message": f"mensagem {i}",
        "page": "vagas",
        "status": "aberto",
        "attachment_path": "x.png" if i == 1 else None,
        "created_at": (AGORA - timedelta(hours=horas_atras)).isoformat(),
    }


@pytest.fixture
def banco():
    return FakeSupabase(
        pathr_user=[ANA],
        pathr_report=[
            _relato(1, "reclamacao", 2),
            _relato(2, "sugestao", 5),
            _relato(3, "reclamacao", 60),  # antigo: fora da janela
        ],
        pathr_error_event=[
            {"fingerprint": "f1", "method": "GET", "route": "/vagas", "error_type": "KeyError",
             "message": "'x'", "location": "app/routers/vagas.py:10",
             "occurred_at": (AGORA - timedelta(hours=h)).isoformat()}
            for h in (1, 3)
        ],
        pathr_scan_run=[],
    )


@pytest.fixture
def cliente(banco, monkeypatch):
    monkeypatch.setattr(settings, "scan_secret", SEGREDO)
    app.dependency_overrides[get_supabase] = lambda: banco
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _h(segredo=SEGREDO):
    return {"X-Pathr-Scan-Secret": segredo}


def test_sem_segredo_configurado_a_varredura_fica_desligada(banco, monkeypatch):
    monkeypatch.setattr(settings, "scan_secret", "")
    app.dependency_overrides[get_supabase] = lambda: banco
    try:
        assert TestClient(app).get("/jobs/varredura/dados", headers=_h("")).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_segredo_errado_nao_le_nada(cliente):
    assert cliente.get("/jobs/varredura/dados").status_code == 401
    assert cliente.get("/jobs/varredura/dados", headers=_h("errado")).status_code == 401
    assert cliente.post("/jobs/varredura/resumo", json={}, headers=_h("errado")).status_code == 401


def test_o_segredo_dos_avisos_nao_abre_a_varredura(cliente, monkeypatch):
    monkeypatch.setattr(settings, "jobs_secret", "outro")
    assert cliente.get("/jobs/varredura/dados", headers={"X-Pathr-Jobs-Secret": "outro"}).status_code == 401


def test_dados_trazem_relatos_da_janela_sem_autor_e_erros_agrupados(cliente):
    corpo = cliente.get("/jobs/varredura/dados", headers=_h()).json()
    assert sorted(r["mensagem"] for r in corpo["relatos"]) == ["mensagem 1", "mensagem 2"]
    texto = str(corpo["relatos"])
    for dado_pessoal in ("user_id", ANA["id"], ANA["email"], ANA["name"]):
        assert dado_pessoal not in texto
    com_foto = {r["mensagem"]: r["tem_foto"] for r in corpo["relatos"]}
    assert com_foto == {"mensagem 1": True, "mensagem 2": False}
    assert len(corpo["erros"]) == 1 and corpo["erros"][0]["ocorrencias"] == 2


def test_resumo_conta_e_manda_uma_vez_por_dia(cliente, monkeypatch):
    enviados = []
    monkeypatch.setattr(emails, "send_scan_summary", lambda *a: enviados.append(a) or True)
    achados = [
        {"categoria": "bug", "severidade": "baixo", "titulo": "Alinhamento"},
        {"categoria": "vulnerabilidade", "severidade": "alto", "titulo": "Header ausente"},
        {"categoria": "bug", "severidade": "critico", "titulo": "Login quebra"},
        {"categoria": "sugestao", "titulo": "Cache da busca"},
    ]
    primeira = cliente.post("/jobs/varredura/resumo", json={"achados": achados}, headers=_h()).json()
    assert primeira["enviado"] is True
    numeros = primeira["numeros"]
    assert numeros["bugs"] == 3 and numeros["vulnerabilidades"] == 1 and numeros["sugestoes"] == 1
    assert numeros["por_severidade"] == {"critico": 1, "alto": 1, "medio": 0, "baixo": 1}
    assert (numeros["erros"], numeros["ocorrencias_de_erro"]) == (1, 2)
    assert (numeros["relatos_bug"], numeros["relatos_sugestao"]) == (1, 1)
    # Destaques em ordem de severidade, sem as sugestões.
    assert enviados[0][2] == ["Login quebra", "Header ausente", "Alinhamento"]

    segunda = cliente.post("/jobs/varredura/resumo", json={"achados": achados}, headers=_h()).json()
    assert segunda["enviado"] is False and len(enviados) == 1


def test_falha_no_envio_nao_trava_o_dia(cliente, banco, monkeypatch):
    monkeypatch.setattr(emails, "send_scan_summary", lambda *a: False)
    assert cliente.post("/jobs/varredura/resumo", json={}, headers=_h()).json()["enviado"] is False
    assert banco.linhas("pathr_scan_run") == []


def test_link_do_email_so_aceita_notion(cliente, monkeypatch):
    monkeypatch.setattr(emails, "send_scan_summary", lambda *a: True)
    for truque in ("https://evil.example/x", "javascript:alert(1)", "https://www.notion.so.evil.example/"):
        assert cliente.post("/jobs/varredura/resumo", json={"notion_url": truque}, headers=_h()).status_code == 422


def test_email_do_resumo_tem_as_frases_pedidas(monkeypatch):
    capturado = {}
    monkeypatch.setattr(emails, "_send", lambda to, nome, assunto, html: capturado.update(a=assunto, h=html) or True)
    numeros = {"bugs": 3, "vulnerabilidades": 1, "por_severidade": {"critico": 1, "alto": 1, "medio": 0, "baixo": 1},
               "sugestoes": 2, "erros": 1, "ocorrencias_de_erro": 4, "relatos_bug": 1, "relatos_sugestao": 2}
    assert emails.send_scan_summary("m@x.com", numeros, ["<b>x</b>"], "https://www.notion.so/abc")
    html = capturado["h"]
    assert "3 bugs encontrados hoje" in html and "1 crítico" in html and "0 médios" in html
    assert "Usuários relataram 1 bug no sistema e 2 sugestões." in html
    assert "<b>x</b>" not in html  # título vindo da rotina é escapado
    assert capturado["a"].startswith("PathR hoje: 3 bugs")


def test_redacao_tira_dado_pessoal_da_mensagem_do_erro():
    texto = erros.redigir(
        "falhou para ana@exemplo.com id 6f1c2d3e-1111-2222-3333-444455556666 token eyJa.b.c tel 11987654321"
    )
    assert "ana@" not in texto and "6f1c" not in texto and "eyJ" not in texto and "98765" not in texto


def test_excecao_nao_tratada_vira_linha_redigida_com_rota_molde(banco):
    rota = APIRouter()

    @rota.get("/_teste_quebra/{item_id}")
    def _quebra(item_id: str):
        raise ValueError(f"sem item para ana@exemplo.com ({item_id})")

    app.include_router(rota)
    app.dependency_overrides[get_supabase] = lambda: banco
    try:
        resposta = TestClient(app, raise_server_exceptions=False).get("/_teste_quebra/123456789")
    finally:
        app.dependency_overrides.clear()
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/_teste_quebra/{item_id}"]
    assert resposta.status_code == 500
    novo = banco.linhas("pathr_error_event")[-1]
    assert novo["route"] == "/_teste_quebra/{item_id}"
    assert novo["error_type"] == "ValueError"
    assert "ana@" not in novo["message"] and "123456789" not in novo["message"]
