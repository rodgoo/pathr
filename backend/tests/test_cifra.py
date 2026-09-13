"""Cifra dos dados sensíveis.

O que se segura: com a chave ligada, o banco e o armazenamento de arquivos só
recebem texto cifrado — nascimento, currículo, fotos, relatos —, e a API
continua devolvendo o dado em claro a quem tem direito. Um texto cifrado
copiado para a linha de outra conta não abre, um byte trocado é recusado, o
dado antigo em claro continua lendo, e produção sem chave não grava em claro.
"""

import base64
import os

import pytest

from app.config import settings
from app.routers import resumes
from app.services import cifra
from tests.fake_supabase import FakeSupabase
from tests.test_relatos import ANA, MODERADOR, PNG, _relatar, _Storage, banco, como  # noqa: F401


def _chave() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", _chave())
    monkeypatch.setattr(settings, "data_encryption_keys_old", "")


# ── a cifra em si ────────────────────────────────────────────────────────────


def test_ida_e_volta_com_nonce_diferente_a_cada_vez(com_chave):
    a = cifra.cifrar("1990-05-02", "ctx:ana")
    b = cifra.cifrar("1990-05-02", "ctx:ana")
    assert a.startswith(cifra.PREFIXO) and "1990" not in a
    assert a != b  # mesmo dado, cifras diferentes: não dá para comparar pessoas
    assert cifra.decifrar(a, "ctx:ana") == "1990-05-02"


def test_cifra_copiada_para_outro_dono_nao_abre(com_chave):
    da_ana = cifra.cifrar("1990-05-02", cifra.ctx_nascimento("ana"))
    with pytest.raises(cifra.CifraIndisponivel):
        cifra.decifrar(da_ana, cifra.ctx_nascimento("bruno"))


def test_byte_adulterado_e_recusado(com_chave):
    arquivo = cifra.cifrar_bytes(PNG, "storage:x")
    adulterado = arquivo[:-1] + bytes([arquivo[-1] ^ 1])
    with pytest.raises(cifra.CifraIndisponivel):
        cifra.decifrar_bytes(adulterado, "storage:x")


def test_dado_antigo_em_claro_continua_lendo(com_chave):
    assert cifra.decifrar("mensagem antiga", "ctx") == "mensagem antiga"
    assert cifra.decifrar_bytes(PNG, "ctx") == PNG
    assert cifra.decifrar_json({"nome": "Ana"}, "ctx") == {"nome": "Ana"}


def test_producao_sem_chave_nao_grava_em_claro(monkeypatch):
    monkeypatch.setattr(settings, "data_encryption_key", "")
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(cifra.CifraIndisponivel):
        cifra.cifrar("1990-05-02", "ctx")
    with pytest.raises(cifra.CifraIndisponivel):
        cifra.cifrar_bytes(PNG, "ctx")


def test_trocar_a_chave_mantem_o_que_foi_cifrado_com_a_antiga(monkeypatch):
    antiga, nova = _chave(), _chave()
    monkeypatch.setattr(settings, "data_encryption_key", antiga)
    guardado = cifra.cifrar("segredo", "ctx")
    monkeypatch.setattr(settings, "data_encryption_key", nova)
    monkeypatch.setattr(settings, "data_encryption_keys_old", antiga)
    assert cifra.decifrar(guardado, "ctx") == "segredo"
    # O que se grava depois sai com a nova.
    monkeypatch.setattr(settings, "data_encryption_keys_old", "")
    assert cifra.decifrar(cifra.cifrar("outro", "ctx"), "ctx") == "outro"


# ── no banco e no bucket, só cifra ───────────────────────────────────────────


def test_relato_e_foto_ficam_cifrados_e_saem_em_claro(com_chave, como, banco):
    resposta = _relatar(como(ANA), foto=PNG, mensagem="O botão de salvar não responde.")
    assert resposta.status_code == 201 and resposta.json()["message"] == "O botão de salvar não responde."
    relato_id = resposta.json()["id"]

    linha = banco.linhas("pathr_report")[0]
    assert linha["message"].startswith(cifra.PREFIXO) and "botão" not in linha["message"]
    arquivo = next(iter(banco.storage.arquivos.values()))
    assert arquivo.startswith(cifra.MAGICO) and not arquivo.startswith(b"\x89PNG")

    assert como(ANA).get("/relatos/meus").json()[0]["message"] == "O botão de salvar não responde."
    foto = como(MODERADOR).get(f"/relatos/{relato_id}/foto")
    assert foto.status_code == 200 and foto.content == PNG

    como(MODERADOR).patch(f"/relatos/{relato_id}", json={"status": "resolvido", "moderator_note": "Corrigido."})
    assert banco.linhas("pathr_report")[0]["moderator_note"].startswith(cifra.PREFIXO)
    assert como(ANA).get("/relatos/meus").json()[0]["moderator_note"] == "Corrigido."


def test_data_de_nascimento_fica_cifrada_no_perfil(com_chave):
    from fastapi.testclient import TestClient

    from app.database import get_supabase
    from app.deps import get_current_user
    from app.main import app

    uid = "aaaaaaaa-0000-0000-0000-000000000001"
    duplo = FakeSupabase(pathr_user=[{"id": uid}], pathr_profile=[{"user_id": uid}])
    app.dependency_overrides[get_supabase] = lambda: duplo
    app.dependency_overrides[get_current_user] = lambda: {"id": uid}
    try:
        cliente = TestClient(app)
        assert cliente.patch("/profile", json={"birth_date": "1990-05-02"}).json()["birth_date"] == "1990-05-02"
        assert cliente.get("/profile").json()["birth_date"] == "1990-05-02"
        # Menor de idade é recusado.
        assert cliente.patch("/profile", json={"birth_date": "2015-01-01"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
    guardada = duplo.linhas("pathr_profile")[0]["birth_date"]
    assert guardada.startswith(cifra.PREFIXO) and "1990" not in guardada


def test_curriculo_arquivo_texto_e_dados_cifrados(com_chave):
    uid = "aaaaaaaa-0000-0000-0000-000000000001"
    duplo = FakeSupabase()
    duplo.storage = _Storage()
    caminho = resumes._store_file(duplo, uid, "hash", "pdf", b"%PDF-1.4 Ana Souza", "application/pdf")
    assert duplo.storage.arquivos[caminho].startswith(cifra.MAGICO)
    assert resumes._load_file(duplo, {"storage_path": caminho}) == b"%PDF-1.4 Ana Souza"

    linha = {
        "user_id": uid,
        "raw_text": cifra.cifrar("Ana Souza, ana@x.com", cifra.ctx_curriculo_texto(uid)),
        "parsed": cifra.cifrar_json({"nome": "Ana Souza"}, cifra.ctx_curriculo_dados(uid)),
    }
    assert "Ana" not in str(linha)
    aberto = resumes._decifrado(linha)
    assert aberto["raw_text"] == "Ana Souza, ana@x.com" and aberto["parsed"] == {"nome": "Ana Souza"}
