"""A geração do quiz: quantas questões saem, e como a correção explica cada alternativa.

O relato, com print: o quiz saiu com UMA questão (o pedido era de 6), "Bom resultado — a proficiência subiu" em
cima de um acerto só, e a explicação era um bloco corrido que só dizia por que a certa estava certa. As causas:
a limpeza descartava em silêncio toda questão sem exatamente 4 alternativas, ninguém comparava o resultado com o
pedido, e o prompt pedia para explicar só "a mais tentadora" das erradas.
"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.ai_providers import AiProviderError
from app.routers import quizzes
from tests.fake_supabase import FakeSupabase

EU = {"id": str(uuid.uuid4()), "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}


@pytest.fixture(autouse=True)
def sem_sorteio(monkeypatch):
    """A ordem das alternativas é sorteada de verdade em produção; aqui ela fica como veio, para o gabarito ser
    previsível. (O sorteio tem os testes dele em test_quiz_equilibrio.py.) Sem isto, estes testes só passavam
    porque o texto de `analise` cita "alternativa 0", o que desliga o sorteio por acaso."""
    monkeypatch.setattr(quizzes, "_misturar", lambda itens: None)


def _q(i: int, opcoes: int = 4, analise: bool = True, correta: int = 1, **extra) -> dict:
    """Uma questão como o modelo a devolve."""
    q = {
        "conceito": f"conceito {i}",
        "enunciado": f"Enunciado numero {i} sobre containers e camadas?",
        "alternativas": [f"opcao {i}.{k}" for k in range(opcoes)],
        "correta": correta,
        "explicacao": f"A ideia central da questao {i}.",
        "dificuldade": "medio",
    }
    if analise:
        q["analise"] = [f"texto da alternativa {k} da questao {i}" for k in range(opcoes)]
    return {**q, **extra}


# --- a explicação, formatada --------------------------------------------------


def test_a_explicacao_diz_por_que_cada_alternativa_esta_certa_ou_errada():
    [limpa] = quizzes._clean_questions([_q(1, correta=1)])
    texto = limpa["explicacao"]
    assert texto.startswith("A ideia central da questao 1.")
    assert "**Por que cada alternativa:**" in texto
    assert "- **Alternativa 1 — errada.** texto da alternativa 0 da questao 1" in texto
    assert "- **Alternativa 2 — correta.** texto da alternativa 1 da questao 1" in texto
    assert "- **Alternativa 3 — errada.**" in texto and "- **Alternativa 4 — errada.**" in texto
    assert texto.count("— correta.") == 1 and texto.count("— errada.") == 3


def test_as_alternativas_sao_numeradas_de_1_como_a_tela_mostra():
    [limpa] = quizzes._clean_questions([_q(1, correta=0)])
    assert "**Alternativa 1 — correta.**" in limpa["explicacao"]
    assert "Alternativa 0" not in limpa["explicacao"]


def test_sem_a_analise_fica_so_o_resumo_como_antes():
    [limpa] = quizzes._clean_questions([_q(1, analise=False)])
    assert limpa["explicacao"] == "A ideia central da questao 1."


@pytest.mark.parametrize("analise", [["so um"], ["a", "b", "c"], ["a", "b", "", "d"], "texto solto", None])
def test_analise_incompleta_nao_e_usada(analise):
    """Um texto faltando não pode ser adivinhado nem deixar uma alternativa sem explicação no meio das outras."""
    [limpa] = quizzes._clean_questions([{**_q(1, analise=False), "analise": analise}])
    assert limpa["explicacao"] == "A ideia central da questao 1."
    assert "Por que cada alternativa" not in limpa["explicacao"]


def test_o_prompt_pede_a_analise_de_cada_alternativa_e_a_quantidade_certa():
    assert "analise" in quizzes.SYSTEM_PROMPT and "EXATAMENTE 4 textos" in quizzes.SYSTEM_PROMPT
    assert "EXATAMENTE a quantidade" in quizzes.SYSTEM_PROMPT
    assert "analise" in quizzes.QUIZ_SCHEMA["properties"]["questoes"]["items"]["properties"]


# --- a limpeza deixa de derrubar questão à toa -------------------------------


def test_alternativa_a_mais_nao_derruba_a_questao():
    """Era o que deixava um quiz de 6 com 1 questão: tudo que não vinha com exatamente 4 opções sumia."""
    [limpa] = quizzes._clean_questions([_q(1, opcoes=5, correta=2)])
    assert len(limpa["alternativas"]) == 4 and limpa["correta"] == 2
    assert limpa["explicacao"].count("— errada.") == 3, "a análise também é cortada para 4"


def test_alternativa_a_menos_ou_gabarito_fora_da_faixa_ainda_descarta():
    assert quizzes._clean_questions([_q(1, opcoes=3)]) == []
    assert quizzes._clean_questions([_q(1, correta=4)]) == []
    assert quizzes._clean_questions([_q(1, opcoes=5, correta=4)]) == [], "o gabarito seria cortado junto"


def test_questao_repetida_e_removida():
    a, b = _q(1), _q(1, conceito="outro nome")
    assert len(quizzes._sem_repetidas(quizzes._clean_questions([a, b, _q(2)]))) == 2


# --- gerar de ponta a ponta ---------------------------------------------------


@pytest.fixture
def geracao(monkeypatch):
    """`generate_quiz` com a IA e as consultas auxiliares trocadas por dublês. `respostas` = o que cada chamada da IA devolve."""
    estado = {"respostas": [], "prompts": []}

    async def ia(sistema, prompt, schema, **k):
        estado["prompts"].append(prompt)
        resposta = estado["respostas"].pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return SimpleNamespace(content={"titulo": "Quiz de Docker", "questoes": resposta}, model="falso")

    monkeypatch.setattr(quizzes, "generate_json", ia)
    monkeypatch.setattr(quizzes, "_due_reviews", lambda *a, **k: [])
    monkeypatch.setattr(quizzes, "_recent_scores", lambda *a, **k: [])
    monkeypatch.setattr(quizzes, "_materiais_concluidos", lambda *a, **k: [])
    monkeypatch.setattr(quizzes.conhecimento, "pendentes", lambda *a, **k: [])
    estado["banco"] = FakeSupabase(
        pathr_tag=[{"id": "t1", "name": "Docker"}], pathr_user_tag=[], pathr_quiz=[], pathr_question=[], pathr_attempt=[],
    )
    return estado


async def _gerar(estado, quantas=6):
    return await quizzes.generate_quiz(quizzes.GenerateQuiz(tag_ids=["t1"], question_count=quantas), EU, estado["banco"])


async def test_quiz_completo_na_primeira_vez_nao_faz_segunda_chamada(geracao):
    geracao["respostas"] = [[_q(i) for i in range(6)]]
    quiz = await _gerar(geracao)
    assert len(quiz["questions"]) == 6 and len(geracao["prompts"]) == 1


async def test_o_pedido_diz_a_quantidade_exata(geracao):
    geracao["respostas"] = [[_q(i) for i in range(6)]]
    await _gerar(geracao)
    assert "QUANTIDADE DE QUESTOES: 6 (devolva exatamente esta quantidade)" in geracao["prompts"][0]


async def test_o_que_faltou_e_completado_em_uma_segunda_chamada(geracao):
    """O caso do print: o modelo devolve 6, cinco vêm com 3 alternativas, e antes o quiz saía com UMA questão."""
    geracao["respostas"] = [
        [_q(0)] + [_q(i, opcoes=3) for i in range(1, 6)],
        [_q(i) for i in range(10, 15)],
    ]
    quiz = await _gerar(geracao)
    assert len(quiz["questions"]) == 6
    assert len(geracao["prompts"]) == 2
    assert "JA ESCRITAS" in geracao["prompts"][1] and "conceito 0" in geracao["prompts"][1]
    assert "ESCREVA MAIS 5 QUESTOES" in geracao["prompts"][1]
    assert len(geracao["banco"].linhas("pathr_question")) == 6
    assert geracao["banco"].linhas("pathr_quiz")[0]["question_count"] == 6


async def test_a_segunda_chamada_nao_traz_repetida(geracao):
    geracao["respostas"] = [[_q(i) for i in range(3)], [_q(0), _q(1), _q(20), _q(21)]]
    quiz = await _gerar(geracao)
    enunciados = [q["prompt"] for q in quiz["questions"]]
    assert len(enunciados) == len(set(enunciados)) == 5


async def test_mais_do_que_o_pedido_e_cortado(geracao):
    geracao["respostas"] = [[_q(i) for i in range(9)]]
    quiz = await _gerar(geracao, quantas=6)
    assert len(quiz["questions"]) == 6


async def test_quiz_com_menos_de_tres_questoes_e_recusado(geracao):
    """Um acerto em uma questão dá 100% e sobe a proficiência: com menos de 3 não é evidência de nada."""
    geracao["respostas"] = [[_q(0)] + [_q(i, opcoes=2) for i in range(1, 6)], [_q(7, opcoes=2)]]
    with pytest.raises(HTTPException) as erro:
        await _gerar(geracao)
    assert erro.value.status_code == 502
    assert geracao["banco"].linhas("pathr_quiz") == [] and geracao["banco"].linhas("pathr_question") == []


async def test_falha_ao_completar_mantem_o_que_ja_ha_se_for_o_bastante(geracao):
    geracao["respostas"] = [[_q(i) for i in range(4)] + [_q(9, opcoes=2), _q(8, opcoes=2)], AiProviderError("cota do dia")]
    quiz = await _gerar(geracao)
    assert len(quiz["questions"]) == 4


async def test_falha_ao_completar_com_pouca_coisa_recusa(geracao):
    geracao["respostas"] = [[_q(0), _q(1)] + [_q(i, opcoes=2) for i in range(2, 6)], AiProviderError("fora do ar")]
    with pytest.raises(HTTPException) as erro:
        await _gerar(geracao)
    assert erro.value.status_code == 502


async def test_pedido_de_tres_com_tres_nao_completa(geracao):
    geracao["respostas"] = [[_q(i) for i in range(3)]]
    quiz = await _gerar(geracao, quantas=3)
    assert len(quiz["questions"]) == 3 and len(geracao["prompts"]) == 1


async def test_a_correcao_grava_a_explicacao_formatada(geracao):
    geracao["respostas"] = [[_q(i, correta=2) for i in range(3)]]
    await _gerar(geracao, quantas=3)
    gravada = geracao["banco"].linhas("pathr_question")[0]["explanation"]
    assert "**Por que cada alternativa:**" in gravada and "**Alternativa 3 — correta.**" in gravada
