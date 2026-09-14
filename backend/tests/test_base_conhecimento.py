"""A base de conhecimento da conta e o "Perguntar".

O que se segura:
- nada se perde: dúvida, erro de quiz e falha da IA entram na base;
- um tema é uma linha: repetir soma `times_seen` e reabre o que foi revisado;
- acertar o que voltava para revisão tira da lista de pendências;
- o tutor lê o contexto do BANCO, conferindo o dono; questão de quiz não
  respondida não leva o gabarito; a explicação sempre termina perguntando se
  ficou claro; "ainda não" traz outra explicação e pesa mais na base.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.ai_providers import AiProviderError
from app.routers import duvidas as rotas
from app.services import conhecimento, duvidas
from tests.fake_supabase import FakeSupabase

EU = {"id": "11111111-1111-1111-1111-111111111111", "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}
OUTRA = "99999999-9999-9999-9999-999999999999"
EXEMPLO = "22222222-2222-2222-2222-222222222222"
QUESTAO = "33333333-3333-3333-3333-333333333333"


def _banco(**extra):
    tabelas = dict(
        pathr_knowledge_item=[],
        pathr_doubt_thread=[],
        pathr_doubt_message=[],
        pathr_tag=[{"id": "t-java", "slug": "java", "name": "Java"}],
        pathr_walkthrough=[{
            "id": EXEMPLO, "user_id": EU["id"], "language": "java", "topic": "modificadores de acesso",
            "title": "Modificadores de acesso em Java", "summary": "public, private, protected",
            "code": "public class Exemplo { private int privado = 20; }",
        }],
        pathr_quiz=[{"id": "Q1", "user_id": EU["id"], "title": "Quiz de Java", "tag_ids": ["t-java"], "node_id": None}],
        pathr_question=[{
            "id": QUESTAO, "quiz_id": "Q1", "prompt": "Qual modificador esconde o campo da subclasse?",
            "options": ["public", "private", "protected", "default"], "correct": {"index": 1},
            "explanation": "private não é visto nem pela subclasse.",
        }],
        pathr_attempt=[],
    )
    tabelas.update(extra)
    return FakeSupabase(**tabelas)


@pytest.fixture
def tutor(monkeypatch):
    estado = SimpleNamespace(pedidos=[], falhar=False, resposta="private só é visível dentro da própria classe.")

    async def falso(sistema, pedido, _schema, **_):
        estado.pedidos.append(pedido)
        if estado.falhar:
            raise AiProviderError("fora do ar")
        return SimpleNamespace(content={"resposta": estado.resposta, "conceito": "diferença entre private e protected"}, model="falso")

    monkeypatch.setattr(duvidas, "generate_json", falso)
    return estado


# --- a base -----------------------------------------------------------------


def test_um_tema_e_uma_linha_e_repetir_pesa_mais():
    banco = _banco()
    conhecimento.registrar(banco, EU["id"], "duvida", "Diferença entre private e protected", tag_id="t-java")
    conhecimento.registrar(banco, EU["id"], "quiz", "diferenca entre PRIVATE e protected!")
    linhas = banco.linhas("pathr_knowledge_item")
    assert len(linhas) == 1 and linhas[0]["times_seen"] == 2 and linhas[0]["tag_id"] == "t-java"

    conhecimento.marcar_revisado(banco, EU["id"], "diferença entre private e protected")
    assert banco.linhas("pathr_knowledge_item")[0]["status"] == "revisado"
    conhecimento.registrar(banco, EU["id"], "quiz", "diferença entre private e protected")
    assert banco.linhas("pathr_knowledge_item")[0]["status"] == "pendente", "errar de novo reabre"


def test_pendentes_filtram_por_tecnologia_e_ordenam_pelo_peso():
    banco = _banco()
    conhecimento.registrar(banco, EU["id"], "duvida", "git push", tag_id="t-git")
    conhecimento.registrar(banco, EU["id"], "quiz", "private vs protected", tag_id="t-java")
    conhecimento.registrar(banco, EU["id"], "quiz", "private vs protected", tag_id="t-java")
    conhecimento.registrar(banco, EU["id"], "palavra", "deadline", idioma="en")
    temas = [i["concept"] for i in conhecimento.pendentes(banco, EU["id"], tag_ids=["t-java", "t-git"])]
    assert temas == ["private vs protected", "git push"]
    assert conhecimento.pendentes(banco, EU["id"], tag_ids=["t-java"], so_nao_buscados=True)
    item = conhecimento.pendentes(banco, EU["id"], tag_ids=["t-java"])[0]
    conhecimento.marcar_buscado(banco, str(item["id"]))
    assert conhecimento.pendentes(banco, EU["id"], tag_ids=["t-java"], so_nao_buscados=True) == []


# --- o tutor ------------------------------------------------------------------


def test_perguntar_no_laboratorio_explica_termina_perguntando_e_guarda_na_base(tutor):
    banco = _banco()
    corpo = rotas.Abrir(contexto_tipo="laboratorio", contexto_ref=EXEMPLO, trecho="linha 4: private int privado = 20;",
                        pergunta="Por que o privado não aparece na subclasse?")
    saida = asyncio.run(rotas.abrir(corpo, EU, banco))

    assert [m["papel"] for m in saida["mensagens"]] == ["pessoa", "tutor"]
    assert saida["mensagens"][1]["texto"].endswith(duvidas.PERGUNTA_FINAL), "a pergunta final é garantida"
    assert "public class Exemplo" in tutor.pedidos[0] and "linha 4" in tutor.pedidos[0], "contexto e trecho vão ao tutor"
    item = banco.linhas("pathr_knowledge_item")[0]
    assert item["source"] == "duvida" and item["tag_id"] == "t-java"
    assert item["concept"] == "diferença entre private e protected"


def test_contexto_de_outra_pessoa_nao_serve(tutor):
    banco = _banco()
    banco.tabelas["pathr_walkthrough"][0]["user_id"] = OUTRA
    with pytest.raises(HTTPException) as erro:
        asyncio.run(rotas.abrir(rotas.Abrir(contexto_tipo="laboratorio", contexto_ref=EXEMPLO, pergunta="o que é isso?"), EU, banco))
    assert erro.value.status_code == 404
    assert tutor.pedidos == []


def test_questao_nao_respondida_nao_leva_o_gabarito(tutor):
    banco = _banco()
    asyncio.run(rotas.abrir(rotas.Abrir(contexto_tipo="quiz", contexto_ref=QUESTAO, pergunta="qual é a certa?"), EU, banco))
    assert "SEM SOLUÇÃO" in tutor.pedidos[0] and "Alternativa certa" not in tutor.pedidos[0]
    assert "Alternativa 1: public" in tutor.pedidos[0], "alternativas contadas a partir de 1"

    banco.tabelas["pathr_attempt"].append({"id": "A1", "quiz_id": "Q1", "user_id": EU["id"]})
    asyncio.run(rotas.abrir(rotas.Abrir(contexto_tipo="quiz", contexto_ref=QUESTAO, pergunta="por que a 2?"), EU, banco))
    assert "Alternativa certa: 2" in tutor.pedidos[-1]


def test_ainda_nao_entendi_explica_de_novo_e_pesa_mais(tutor):
    banco = _banco()
    aberta = asyncio.run(rotas.abrir(rotas.Abrir(contexto_tipo="laboratorio", contexto_ref=EXEMPLO, pergunta="não entendi o private"), EU, banco))
    tutor.resposta = "Pense numa gaveta trancada: só a classe tem a chave. A explicação ficou clara? Conseguiu entender?"
    saida = asyncio.run(rotas.entendeu(aberta["id"], rotas.Retorno(entendeu=False), EU, banco))

    assert [m["papel"] for m in saida["mensagens"]] == ["pessoa", "tutor", "pessoa", "tutor"]
    assert saida["mensagens"][-1]["texto"].count(duvidas.PERGUNTA_FINAL) == 1, "não duplica a pergunta"
    assert banco.linhas("pathr_knowledge_item")[0]["times_seen"] >= 2

    fim = asyncio.run(rotas.entendeu(aberta["id"], rotas.Retorno(entendeu=True), EU, banco))
    assert fim["status"] == "entendida" and fim["entendeu"] is True
    assert banco.linhas("pathr_knowledge_item")[0]["status"] == "pendente", "entender não é dominar: continua para revisão"


def test_ia_fora_do_ar_a_duvida_nao_se_perde(tutor):
    tutor.falhar = True
    banco = _banco()
    with pytest.raises(AiProviderError):
        asyncio.run(rotas.abrir(rotas.Abrir(contexto_tipo="geral", pergunta="o que é injeção de dependência?"), EU, banco))
    item = banco.linhas("pathr_knowledge_item")[0]
    assert item["source"] == "duvida" and "injeção de dependência" in item["concept"]


def test_erro_no_quiz_entra_na_base():
    from app.routers import quizzes

    banco = _banco(pathr_review_item=[])
    questoes = [{"id": QUESTAO, "concept": "private vs protected", "tag_ids": ["t-java"], "prompt": "x",
                 "options": ["a", "b"], "correct": {"index": 1}, "explanation": "y"}]
    quizzes._recycle(banco, EU["id"], questoes, [{"question_id": QUESTAO, "is_correct": False}])
    item = banco.linhas("pathr_knowledge_item")[0]
    assert item["source"] == "quiz" and item["tag_id"] == "t-java"
