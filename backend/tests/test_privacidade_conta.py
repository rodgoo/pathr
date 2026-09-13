"""Exportar e apagar a conta: o que sai no arquivo e o que não pode sobrar.

A exclusão apaga linhas E arquivos. A cascata do banco resolve as linhas; os
arquivos do storage (currículo, foto, fotos de relato) só somem se a rota os
remover — antes, ficavam lá depois de a pessoa mandar apagar tudo.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from tests.fake_supabase import FakeSupabase

ANA = "aaaaaaaa-0000-0000-0000-000000000001"
BRUNO = "bbbbbbbb-0000-0000-0000-000000000002"


class _Bucket:
    def __init__(self, storage, nome):
        self.storage, self.nome = storage, nome

    def remove(self, caminhos):
        self.storage.removidos.setdefault(self.nome, []).extend(caminhos)


class _Storage:
    def __init__(self):
        self.removidos = {}

    def from_(self, nome):
        return _Bucket(self, nome)


@pytest.fixture
def banco():
    duplo = FakeSupabase(
        pathr_user=[
            {"id": ANA, "email": "ana@x.com", "name": "Ana", "username": "ana", "avatar_path": f"{ANA}/avatar.png"},
            {"id": BRUNO, "email": "bruno@x.com", "name": "Bruno Lima", "username": "bruno"},
        ],
        pathr_resume=[{"id": "r1", "user_id": ANA, "storage_path": f"{ANA}/cv.pdf", "raw_text": "texto"}],
        pathr_report=[
            {"id": "p1", "user_id": ANA, "kind": "sugestao", "message": "ideia", "attachment_path": "p1.png",
             "attachment_type": "image/png", "status": "aberto"},
            {"id": "p2", "user_id": BRUNO, "kind": "reclamacao", "message": "outra", "attachment_path": "p2.png"},
        ],
        pathr_friendship=[
            {"id": "f1", "requester_id": ANA, "addressee_id": BRUNO, "status": "accepted", "created_at": "2026-09-01"},
        ],
        pathr_security_event=[
            {"id": "s1", "user_id": ANA, "event_type": "login_ok", "ip": "1.2.3.4"},
            {"id": "s2", "user_id": BRUNO, "event_type": "login_ok", "ip": "5.6.7.8"},
        ],
    )
    duplo.storage = _Storage()
    return duplo


@pytest.fixture
def cliente(banco):
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: next(u for u in banco.linhas("pathr_user") if u["id"] == ANA)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_exportacao_traz_relatos_e_amizades_sem_dado_da_outra_conta(cliente):
    dados = cliente.get("/profile/export").json()
    assert [r["message"] for r in dados["relatos"]] == ["ideia"]
    assert dados["relatos"][0]["tinha_foto"] is True and "attachment_path" not in dados["relatos"][0]
    assert dados["amizades"] == [{"com": "bruno", "situacao": "amigos", "desde": "2026-09-01"}]
    assert "bruno@x.com" not in str(dados) and "Bruno Lima" not in str(dados)


def test_excluir_conta_apaga_arquivos_relatos_amizades_e_trilha_de_seguranca(cliente, banco):
    assert cliente.delete("/profile/account").status_code == 204

    removidos = banco.storage.removidos
    assert removidos[settings.resume_bucket] == [f"{ANA}/cv.pdf"]
    assert removidos[settings.report_bucket] == ["p1.png"]
    assert removidos[settings.avatar_bucket] == [f"{ANA}/avatar.png"]

    assert [r["id"] for r in banco.linhas("pathr_report")] == ["p2"]
    assert banco.linhas("pathr_friendship") == []
    assert [e["id"] for e in banco.linhas("pathr_security_event")] == ["s2"]
    assert [u["id"] for u in banco.linhas("pathr_user")] == [BRUNO]


def test_storage_fora_do_ar_nao_impede_apagar_a_conta(cliente, banco):
    class _Quebrado:
        def from_(self, _nome):
            raise RuntimeError("storage indisponível")

    banco.storage = _Quebrado()
    assert cliente.delete("/profile/account").status_code == 204
    assert [u["id"] for u in banco.linhas("pathr_user")] == [BRUNO]
