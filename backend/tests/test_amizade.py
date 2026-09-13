"""Amizade entre contas, e o que uma conta pode ver da outra.

Três contas — Ana, Bruno e Carla — porque as regras que importam são sobre a
TERCEIRA pessoa: quem não é ponta de um convite não o aceita, não o apaga e
nem descobre que ele existe.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.routers.social import pontuar
from tests.fake_supabase import FakeSupabase

ANA = "aaaaaaaa-0000-0000-0000-000000000001"
BRUNO = "bbbbbbbb-0000-0000-0000-000000000002"
CARLA = "cccccccc-0000-0000-0000-000000000003"
DAVI = "dddddddd-0000-0000-0000-000000000004"


def _usuario(uid, nome, username):
    return {"id": uid, "name": nome, "username": username, "email": f"{username}@x.com",
            "email_verified_at": "2026-01-01", "avatar_path": f"{uid}/avatar.png"}


def _perfil(uid, cidade, uf, objetivo, discoverable=True):
    return {"user_id": uid, "city": cidade, "state": uf, "target_role": objetivo,
            "discoverable": discoverable, "birth_date": "1990-01-01"}


@pytest.fixture
def banco():
    return FakeSupabase(
        pathr_user=[
            _usuario(ANA, "Ana Souza", "anasouza"),
            _usuario(BRUNO, "Bruno Lima", "brunolima"),
            _usuario(CARLA, "Carla Reis", "carlareis"),
            _usuario(DAVI, "Davi Melo", "davimelo"),
        ],
        pathr_profile=[
            _perfil(ANA, "Vitória", "ES", "Fullstack Java"),
            _perfil(BRUNO, "Vitória", "ES", "Backend Java"),
            _perfil(CARLA, "Recife", "PE", "Designer"),
            # Davi se escondeu das sugestões.
            _perfil(DAVI, "Vitória", "ES", "Fullstack Java", discoverable=False),
        ],
        pathr_tag=[{"id": "t-java", "name": "Java"}, {"id": "t-react", "name": "React"}],
        pathr_user_tag=[
            {"user_id": ANA, "tag_id": "t-java", "proficiency": 2},
            {"user_id": BRUNO, "tag_id": "t-java", "proficiency": 4},
            {"user_id": BRUNO, "tag_id": "t-react", "proficiency": 1},
        ],
        pathr_friendship=[],
    )


@pytest.fixture
def como(banco, monkeypatch):
    """`como(ANA)` devolve um cliente logado como Ana."""
    atual = {}
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: next(
        u for u in banco.linhas("pathr_user") if u["id"] == atual["id"]
    )
    cliente = TestClient(app)

    def trocar(uid):
        atual["id"] = uid
        return cliente

    yield trocar
    app.dependency_overrides.clear()


def test_convite_aceito_vira_amizade_para_os_dois(como):
    assert como(ANA).post("/social/amigos/brunolima").json() == {"relacao": "enviado"}

    recebidos = como(BRUNO).get("/social/amigos").json()["recebidos"]
    assert [c["username"] for c in recebidos] == ["anasouza"]

    assert como(BRUNO).post(f"/social/convites/{recebidos[0]['friendship_id']}/aceitar").status_code == 200
    assert [c["username"] for c in como(ANA).get("/social/amigos").json()["amigos"]] == ["brunolima"]
    assert [c["username"] for c in como(BRUNO).get("/social/amigos").json()["amigos"]] == ["anasouza"]


def test_convite_cruzado_vira_amizade_sem_passo_extra(como, banco):
    como(ANA).post("/social/amigos/brunolima")
    assert como(BRUNO).post("/social/amigos/anasouza").json() == {"relacao": "amigos"}
    assert len(banco.linhas("pathr_friendship")) == 1


def test_quem_enviou_nao_aceita_o_proprio_convite(como):
    como(ANA).post("/social/amigos/brunolima")
    convite = como(ANA).get("/social/amigos").json()["enviados"][0]["friendship_id"]
    assert como(ANA).post(f"/social/convites/{convite}/aceitar").status_code == 404


def test_terceira_pessoa_nao_aceita_nem_apaga_e_recebe_404(como, banco):
    """404 e não 403: um id adivinhado não pode confirmar que o convite existe."""
    como(ANA).post("/social/amigos/brunolima")
    convite = como(ANA).get("/social/amigos").json()["enviados"][0]["friendship_id"]

    assert como(CARLA).post(f"/social/convites/{convite}/aceitar").status_code == 404
    assert como(CARLA).delete(f"/social/convites/{convite}").status_code == 404
    assert len(banco.linhas("pathr_friendship")) == 1


def test_recusar_apaga_o_convite_sem_deixar_rastro(como, banco):
    como(ANA).post("/social/amigos/brunolima")
    convite = como(BRUNO).get("/social/amigos").json()["recebidos"][0]["friendship_id"]
    assert como(BRUNO).delete(f"/social/convites/{convite}").status_code == 204
    assert banco.linhas("pathr_friendship") == []
    assert como(ANA).get("/social/amigos").json() == {"amigos": [], "recebidos": [], "enviados": []}


def test_id_de_convite_malformado_e_404_e_nao_500(como):
    assert como(ANA).post("/social/convites/nao-e-uuid/aceitar").status_code == 404


def test_nao_se_adiciona(como):
    assert como(ANA).post("/social/amigos/anasouza").status_code == 400


def test_cartao_nao_vaza_email_nem_nascimento(como):
    cartao = como(ANA).get("/social/pessoas/sugestoes").json()[0]
    assert "email" not in cartao and "birth_date" not in cartao
    assert {"username", "name", "has_avatar", "city", "state", "objetivo", "stack"} <= set(cartao)


def test_sugestoes_poem_a_mesma_cidade_primeiro_e_escondem_quem_pediu(como):
    sugeridos = [c["username"] for c in como(ANA).get("/social/pessoas/sugestoes").json()]
    assert sugeridos[0] == "brunolima"  # Vitória, e Java em comum
    assert "davimelo" not in sugeridos  # não quer aparecer
    assert "anasouza" not in sugeridos  # não sugere a si mesma


def test_sugestoes_nao_repetem_quem_ja_tem_relacao(como):
    como(ANA).post("/social/amigos/brunolima")
    assert "brunolima" not in [c["username"] for c in como(ANA).get("/social/pessoas/sugestoes").json()]


def test_stack_vem_do_que_a_pessoa_mais_domina(como):
    bruno = next(c for c in como(ANA).get("/social/pessoas/sugestoes").json() if c["username"] == "brunolima")
    assert bruno["stack"] == ["Java", "React"]


def test_busca_parcial_nao_acha_quem_se_escondeu_mas_o_arroba_exato_acha(como):
    assert "davimelo" not in [c["username"] for c in como(ANA).get("/social/pessoas/busca", params={"q": "davi"}).json()]
    assert [c["username"] for c in como(ANA).get("/social/pessoas/busca", params={"q": "@davimelo"}).json()] == ["davimelo"]


def test_foto_de_quem_se_escondeu_nao_sai_para_desconhecido(como):
    assert como(ANA).get("/social/pessoas/davimelo/avatar").status_code == 404


def test_privacidade_desligada_tira_das_sugestoes(como):
    assert como(BRUNO).put("/social/privacidade", json={"discoverable": False}).status_code == 200
    assert "brunolima" not in [c["username"] for c in como(ANA).get("/social/pessoas/sugestoes").json()]


def test_trocar_username_para_um_ocupado_devolve_sugestoes(como):
    resposta = como(ANA).put("/social/username", json={"username": "brunolima"})
    assert resposta.status_code == 409
    assert resposta.json()["detail"]["sugestoes"]


def test_pontuacao_proximidade_pesa_mais_que_afinidade():
    eu = {"city": "Vitória", "state": "ES", "objetivo": "Java", "_tag_ids": {"t1"}}
    vizinho_sem_nada_em_comum = {"city": "Vitória", "state": "ES", "objetivo": "Design", "_tag_ids": set()}
    distante_igualzinho = {"city": "Recife", "state": "PE", "objetivo": "Java", "_tag_ids": {"t1"}}
    assert pontuar(eu, vizinho_sem_nada_em_comum) > pontuar(eu, distante_igualzinho)


def test_cartao_diz_o_que_as_duas_contas_tem_em_comum(como, banco):
    bruno = next(c for c in como(ANA).get("/social/pessoas/sugestoes").json() if c["username"] == "brunolima")
    # Ana tem Java; Bruno tem Java e React: em comum só Java, e a stack não é a mesma.
    assert bruno["em_comum"] == ["Java"] and bruno["mesma_stack"] is False

    banco.tabelas["pathr_user_tag"].append({"user_id": ANA, "tag_id": "t-react", "proficiency": 1})
    bruno = como(ANA).get("/social/pessoas/busca", params={"q": "@brunolima"}).json()[0]
    assert sorted(bruno["em_comum"]) == ["Java", "React"] and bruno["mesma_stack"] is True

    # Quem não tem tecnologia nenhuma não "tem a mesma stack" de outra conta vazia.
    carla = como(DAVI).get("/social/pessoas/busca", params={"q": "@carlareis"}).json()[0]
    assert carla["em_comum"] == [] and carla["mesma_stack"] is False
