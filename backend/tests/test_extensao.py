"""A chave da PathR Extension e o que ela abre.

O que se segura: a chave em claro só aparece na criação (no banco fica o hash);
chave revogada deixa de valer; ninguém revoga a chave de outra pessoa; os dados
que a extensão lê são os da dona da chave; e resposta sensível não entra no
banco nem chegando pela extensão.
"""

import pytest
from fastapi import HTTPException

from app.routers import extensao as rotas
from app.services import extensao as servico
from tests.fake_supabase import FakeSupabase

EU = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "eu@exemplo.com",
    "name": "Ana Souza",
}
OUTRA = {"id": "22222222-2222-2222-2222-222222222222", "email": "outra@exemplo.com"}


def _banco(**tabelas):
    return FakeSupabase(
        pathr_extension_token=[],
        pathr_rate_event=[],
        pathr_user=[EU, OUTRA],
        **tabelas,
    )


def test_a_chave_em_claro_nao_fica_guardada():
    banco = _banco()
    chave, linha = servico.criar(banco, EU["id"], "Notebook")

    assert chave.startswith(servico.PREFIXO)
    guardada = banco.table("pathr_extension_token").select("*").execute().data[0]
    # O que está no banco é o hash: quem ler a tabela não consegue usar nada.
    assert chave not in str(guardada)
    assert guardada["token_hash"] != chave
    assert linha["nome"] == "Notebook"
    assert "chave" not in linha and "token_hash" not in linha


def test_a_chave_vale_e_diz_de_quem_e():
    banco = _banco()
    chave, _ = servico.criar(banco, EU["id"])

    pessoa = servico.dono(banco, chave)

    assert pessoa["id"] == EU["id"]
    # Marca o uso, para a tela poder mostrar "usada hoje".
    assert banco.table("pathr_extension_token").select("*").execute().data[0]["last_used_at"]


def test_chave_revogada_nao_vale_mais():
    banco = _banco()
    chave, linha = servico.criar(banco, EU["id"])

    assert servico.revogar(banco, EU["id"], linha["id"]) is True
    assert servico.dono(banco, chave) is None
    # E some da lista da pessoa.
    assert servico.listar(banco, EU["id"]) == []


def test_ninguem_revoga_a_chave_de_outra_pessoa():
    banco = _banco()
    chave, linha = servico.criar(banco, EU["id"])

    assert servico.revogar(banco, OUTRA["id"], linha["id"]) is False
    assert servico.dono(banco, chave)["id"] == EU["id"]


def test_chave_inventada_nao_passa():
    banco = _banco()
    servico.criar(banco, EU["id"])

    assert servico.dono(banco, None) is None
    assert servico.dono(banco, "") is None
    assert servico.dono(banco, "pathr_ext_naoexiste") is None
    # Sem o prefixo nem chega a consultar o banco.
    assert servico.dono(banco, "sessao-do-app") is None


def test_o_teto_de_chaves_por_pessoa():
    banco = _banco()
    for _ in range(servico.MAXIMO_POR_PESSOA):
        servico.criar(banco, EU["id"])

    with pytest.raises(ValueError):
        servico.criar(banco, EU["id"])

    # Revogou uma, cabe outra.
    uma = servico.listar(banco, EU["id"])[0]
    servico.revogar(banco, EU["id"], uma["id"])
    assert servico.criar(banco, EU["id"])[0].startswith(servico.PREFIXO)


def test_a_rota_recusa_quem_nao_tem_chave_valida(monkeypatch):
    banco = _banco()
    monkeypatch.setattr(rotas.features, "habilitadas_para", lambda *_: {"candidaturas": True})

    with pytest.raises(HTTPException) as erro:
        rotas.pessoa_da_chave(supabase=banco, x_pathr_extensao="pathr_ext_qualquer")

    assert erro.value.status_code == 401


def test_a_rota_esconde_o_recurso_desligado(monkeypatch):
    banco = _banco()
    chave, _ = servico.criar(banco, EU["id"])
    monkeypatch.setattr(rotas.features, "habilitadas_para", lambda *_: {"candidaturas": False})

    with pytest.raises(HTTPException) as erro:
        rotas.pessoa_da_chave(supabase=banco, x_pathr_extensao=chave)

    # 404 e não 403: para quem não tem o recurso, ele não existe.
    assert erro.value.status_code == 404


def test_os_dados_que_a_extensao_le_sao_os_da_dona_da_chave(monkeypatch):
    banco = _banco(
        pathr_profile=[{"user_id": EU["id"], "city": "Campinas", "salary_expectation": "R$ 9.000"}],
        pathr_resume=[],
        pathr_answer_bank=[],
    )
    monkeypatch.setattr(rotas.features, "habilitadas_para", lambda *_: {"candidaturas": True})

    dados = rotas.dados_para_preencher(pessoa=EU, supabase=banco)

    assert dados["pessoa"]["nome"] == "Ana Souza"
    assert dados["perfil"]["cidade"] == "Campinas"
    assert dados["perfil"]["pretensao"] == "R$ 9.000"
    # As formas sensíveis viajam para a extensão decidir LÁ o que não preencher.
    assert "genero" in dados["sensiveis"] and "raca" in dados["sensiveis"]


def test_resposta_sensivel_nao_entra_no_banco_nem_pela_extensao(monkeypatch):
    banco = _banco(pathr_answer_bank=[])
    monkeypatch.setattr(rotas.features, "habilitadas_para", lambda *_: {"candidaturas": True})

    corpo = rotas.RespostasDaExtensao(
        respostas=[
            {"pergunta": "Qual seu gênero?", "resposta": "prefiro não responder"},
            {"pergunta": "Cidade", "resposta": "Campinas"},
        ]
    )
    resultado = rotas.guardar(corpo=corpo, pessoa=EU, supabase=banco)

    assert resultado["guardadas"] == 1
    guardadas = banco.table("pathr_answer_bank").select("*").execute().data
    assert [linha["question_key"] for linha in guardadas] == ["cidade"]
