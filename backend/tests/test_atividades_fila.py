"""A fila de atividades práticas: sempre há uma, respondeu, vem outra.

O que se segura: a próxima leva as anteriores, as notas e as lacunas para o
modelo; sem IA sai uma atividade do objetivo (nunca a aba vazia); com uma
aberta, "próxima" devolve a aberta em vez de gastar outra chamada; a correção
usa o enunciado DO BANCO e fecha a atividade; e uma já corrigida não é
corrigida de novo.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.ai_providers import AiProviderError
from app.routers import atividades as rotas
from app.routers import explanations
from app.services import atividades
from tests.fake_supabase import FakeSupabase

EU = {"id": "11111111-1111-1111-1111-111111111111", "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}
NO = "22222222-2222-2222-2222-222222222222"
EX1 = "33333333-3333-3333-3333-333333333333"


def _banco(**extra):
    tabelas = dict(
        pathr_roadmap=[{"id": "R1", "user_id": EU["id"]}],
        pathr_roadmap_node=[{
            "id": NO, "roadmap_id": "R1", "title": "Git e GitHub Actions",
            "objectives": ["Configurar repositórios remotos usando Git.", "Criar um workflow de CI simples."],
            "tag_ids": ["t-git"],
        }],
        pathr_tag=[{"id": "t-git", "name": "Git"}],
        pathr_activity_exercise=[],
        pathr_explanation=[],
        pathr_review_item=[],
    )
    tabelas.update(extra)
    return FakeSupabase(**tabelas)


@pytest.fixture
def ia(monkeypatch):
    estado = SimpleNamespace(pedidos=[], falhar=False)

    async def falso(sistema, pedido, _schema, **_):
        estado.pedidos.append((sistema, pedido))
        if estado.falhar:
            raise AiProviderError("fora do ar")
        if sistema is atividades.SISTEMA:
            return SimpleNamespace(
                content={"enunciado": "Você tem um repositório local sem remoto. Escreva os comandos para publicá-lo no GitHub.",
                         "tipo": "comandos", "dicas": ["Pense no nome do remoto."]},
                model="falso",
            )
        return SimpleNamespace(content={"nota": 72, "retorno": "Boa.", "lacunas": [{"conceito": "git remote add", "por_que": "faltou"}]}, model="falso")

    monkeypatch.setattr(atividades, "generate_json", falso)
    monkeypatch.setattr(explanations, "generate_json", falso)
    monkeypatch.setattr(explanations, "log_activity", lambda *a, **k: None)
    return estado


def test_proxima_gera_com_o_contexto_do_modulo(ia):
    banco = _banco(
        pathr_activity_exercise=[{"id": EX1, "user_id": EU["id"], "node_id": NO, "statement": "Crie um .gitignore para Python.",
                                  "kind": "codigo", "hints": [], "score": 45, "answered_at": "2026-09-12T10:00:00+00:00",
                                  "created_at": "2026-09-12T09:00:00+00:00"}],
        pathr_explanation=[{"user_id": EU["id"], "node_id": NO, "gaps": [{"conceito": "ignorar ambientes virtuais"}],
                            "created_at": "2026-09-12T10:00:00+00:00"}],
    )
    saida = asyncio.run(rotas.proxima(NO, EU, banco))

    assert saida["enunciado"].startswith("Você tem um repositório local") and saida["tipo"] == "comandos"
    assert saida["dicas"] == ["Pense no nome do remoto."] and saida["respondida_em"] is None
    _, pedido = ia.pedidos[0]
    assert "Configurar repositórios remotos usando Git." in pedido
    assert "Crie um .gitignore para Python." in pedido, "as anteriores vão para não repetir"
    assert "45" in pedido and "ignorar ambientes virtuais" in pedido, "nota e lacuna calibram a próxima"


def test_com_uma_aberta_nao_gera_outra(ia):
    banco = _banco()
    primeira = asyncio.run(rotas.proxima(NO, EU, banco))
    segunda = asyncio.run(rotas.proxima(NO, EU, banco))
    assert primeira["id"] == segunda["id"]
    assert len(ia.pedidos) == 1
    assert len(banco.linhas("pathr_activity_exercise")) == 1
    assert rotas.listar(NO, EU, banco)["atual"]["id"] == primeira["id"]


def test_sem_ia_ainda_ha_atividade(ia):
    ia.falhar = True
    banco = _banco()
    saida = asyncio.run(rotas.proxima(NO, EU, banco))
    assert "Configurar repositórios remotos usando Git" in saida["enunciado"]
    assert saida["tipo"] == "pratica"


def test_corrigir_pela_atividade_fecha_e_a_proxima_vem(ia):
    banco = _banco()
    atual = asyncio.run(rotas.proxima(NO, EU, banco))

    corpo = explanations.SubmitExplanation(
        concept="Git e GitHub Actions", content="git remote add origin URL\ngit push -u origin main  # publica",
        node_id=NO, modo="atividade", exercise_id=atual["id"],
    )
    resultado = asyncio.run(explanations.submit_explanation(corpo, EU, banco))
    assert resultado["score"] == 72

    _, pedido_da_correcao = ia.pedidos[-1]
    assert atual["enunciado"] in pedido_da_correcao, "corrige contra o enunciado do banco"

    lista = rotas.listar(NO, EU, banco)
    assert lista["atual"] is None and lista["total_feitas"] == 1 and lista["feitas"][0]["nota"] == 72

    nova = asyncio.run(rotas.proxima(NO, EU, banco))
    assert nova["id"] != atual["id"]

    with pytest.raises(HTTPException) as erro:
        asyncio.run(explanations.submit_explanation(corpo, EU, banco))
    assert erro.value.status_code == 409


def test_atividade_de_outra_pessoa_nao_serve(ia):
    banco = _banco(pathr_activity_exercise=[{"id": EX1, "user_id": "outra", "node_id": NO, "statement": "x" * 30,
                                             "kind": "pratica", "hints": [], "created_at": "2026-09-12T09:00:00+00:00"}])
    corpo = explanations.SubmitExplanation(
        concept="Git", content="git push origin main para publicar no GitHub, é isso",
        node_id=NO, modo="atividade", exercise_id=EX1,
    )
    with pytest.raises(HTTPException) as erro:
        asyncio.run(explanations.submit_explanation(corpo, EU, banco))
    assert erro.value.status_code == 404


def test_corrida_devolve_a_aberta_em_vez_de_duplicar(ia):
    """Se o índice único recusar a inserção (dois cliques ao mesmo tempo), a
    geração devolve a atividade aberta que venceu, sem estourar nem duplicar."""
    aberta = {
        "id": EX1, "user_id": EU["id"], "node_id": NO, "statement": "x" * 30,
        "kind": "pratica", "hints": [], "answered_at": None,
        "created_at": "2026-09-12T09:00:00+00:00",
    }
    banco = _banco(pathr_activity_exercise=[aberta])
    node = banco.linhas("pathr_roadmap_node")[0]

    original = banco.table

    def tabela(nome):
        consulta = original(nome)
        if nome == "pathr_activity_exercise":
            def _conflito(_payload):
                return SimpleNamespace(
                    execute=lambda: (_ for _ in ()).throw(
                        Exception("duplicate key value violates unique constraint ux_pathr_activity_open")
                    )
                )
            consulta.insert = _conflito
        return consulta

    banco.table = tabela

    saida = asyncio.run(atividades.gerar(banco, EU["id"], node))
    assert saida["id"] == EX1
    assert len(banco.linhas("pathr_activity_exercise")) == 1
