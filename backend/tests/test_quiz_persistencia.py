"""O quiz que não se perde: retomar o que está aberto, o histórico do módulo e a correção de uma tentativa antiga.

O quiz gerado e as respostas ainda não enviadas viviam só no navegador; sair da aba, limpar os dados ou trocar de
aparelho fazia a pessoa recomeçar. Agora o servidor guarda as questões (já guardava), o rascunho (`pathr_quiz.draft`)
e devolve tudo por módulo. Estes testes prendem o que mais importa quando o dado passa a morar no servidor: que uma
conta NUNCA enxergue o quiz, o rascunho ou o gabarito de outra, e que uma falha ao gravar o rascunho não derrube a tela.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.routers import quizzes
from tests.fake_supabase import FakeSupabase

ANA = {"id": str(uuid.uuid4()), "email": "ana@exemplo.com", "timezone_name": "America/Sao_Paulo"}
BIA = {"id": str(uuid.uuid4()), "email": "bia@exemplo.com", "timezone_name": "America/Sao_Paulo"}
NO = str(uuid.uuid4())


def _quiz(dono: dict, quando: str, **extra) -> dict:
    return {
        "id": str(uuid.uuid4()), "user_id": dono["id"], "node_id": NO, "title": f"Quiz {quando}",
        "question_count": 2, "kind": "practice", "difficulty": "medio", "tag_ids": [], "created_at": quando,
        "draft": None, **extra,
    }


def _questoes(quiz: dict) -> list[dict]:
    return [
        {"id": str(uuid.uuid4()), "quiz_id": quiz["id"], "prompt": f"Pergunta {i}", "code_snippet": None,
         "code_language": None, "options": ["a", "b", "c"], "difficulty": "medio", "order_index": i,
         "correct": {"index": 1}, "explanation": "porque sim", "concept": "x"}
        for i in range(2)
    ]


def _tentativa(quiz: dict, dono: dict, quando: str, score: float = 50.0) -> dict:
    return {
        "id": str(uuid.uuid4()), "quiz_id": quiz["id"], "user_id": dono["id"], "finished_at": quando, "score": score,
        "correct_count": 1, "duration_s": 60, "tag_breakdown": {"score": score, "correct": 1, "total": 2},
        "answers": [{"question_id": "q", "answer": 0, "correct_index": 1, "is_correct": False, "explanation": "porque sim"}],
    }


# --- retomar o que está aberto ------------------------------------------------


def test_devolve_o_quiz_aberto_do_modulo_com_o_rascunho_e_sem_gabarito():
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00")
    questoes = _questoes(quiz)
    quiz["draft"] = {"index": 1, "answers": {questoes[0]["id"]: 2}, "updated_at": "2026-09-20T10:05:00+00:00"}
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=questoes, pathr_attempt=[])

    resposta = quizzes.quiz_em_andamento(NO, ANA, banco)

    assert resposta["quiz"]["id"] == quiz["id"]
    assert [q["prompt"] for q in resposta["quiz"]["questions"]] == ["Pergunta 0", "Pergunta 1"]
    assert resposta["rascunho"]["index"] == 1 and resposta["rascunho"]["answers"] == {questoes[0]["id"]: 2}
    texto = str(resposta)
    assert "correct" not in texto and "porque sim" not in texto, "o gabarito não sai antes de a tentativa existir"
    assert "draft" not in resposta["quiz"], "o rascunho vai à parte, não dentro do quiz"


def test_o_mais_recente_sem_tentativa_e_o_que_volta():
    velho, novo = _quiz(ANA, "2026-09-01T10:00:00+00:00"), _quiz(ANA, "2026-09-10T10:00:00+00:00")
    banco = FakeSupabase(pathr_quiz=[velho, novo], pathr_question=_questoes(velho) + _questoes(novo), pathr_attempt=[])
    assert quizzes.quiz_em_andamento(NO, ANA, banco)["quiz"]["id"] == novo["id"]


def test_quiz_ja_enviado_nao_volta_como_aberto():
    respondido, aberto = _quiz(ANA, "2026-09-10T10:00:00+00:00"), _quiz(ANA, "2026-09-01T10:00:00+00:00")
    banco = FakeSupabase(
        pathr_quiz=[respondido, aberto], pathr_question=_questoes(respondido) + _questoes(aberto),
        pathr_attempt=[_tentativa(respondido, ANA, "2026-09-10T10:30:00+00:00")],
    )
    assert quizzes.quiz_em_andamento(NO, ANA, banco)["quiz"]["id"] == aberto["id"]


def test_sem_quiz_no_modulo_devolve_vazio():
    banco = FakeSupabase(pathr_quiz=[], pathr_question=[], pathr_attempt=[])
    assert quizzes.quiz_em_andamento(NO, ANA, banco) == {"quiz": None, "rascunho": None}


def test_o_quiz_aberto_de_outra_conta_nunca_aparece():
    """Ataque: a Bia pede o módulo da Ana (mesmo `node_id`) para retomar o quiz e o rascunho dela."""
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00", draft={"index": 1, "answers": {"x": 1}, "updated_at": "t"})
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[])
    assert quizzes.quiz_em_andamento(NO, BIA, banco) == {"quiz": None, "rascunho": None}


def test_id_de_modulo_que_nao_e_uuid_e_404_e_nao_chega_ao_banco():
    banco = FakeSupabase()
    for ruim in ("' OR 1=1--", "../etc/passwd", "", "123"):
        with pytest.raises(HTTPException) as erro:
            quizzes.quiz_em_andamento(ruim, ANA, banco)
        assert erro.value.status_code == 404


# --- salvar o rascunho --------------------------------------------------------


def test_salva_a_posicao_e_so_as_respostas_de_questoes_do_quiz():
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00")
    questoes = _questoes(quiz)
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=questoes, pathr_attempt=[])
    corpo = quizzes.DraftIn(index=99, answers={questoes[0]["id"]: 2, "questao-de-outro-quiz": 1, questoes[1]["id"]: 500})

    resposta = quizzes.salvar_rascunho(quiz["id"], corpo, ANA, banco)

    assert resposta["salvo"] is True
    gravado = banco.linhas("pathr_quiz")[0]["draft"]
    assert gravado["answers"] == {questoes[0]["id"]: 2}, "resposta de questão alheia ou fora da faixa é descartada"
    assert gravado["index"] == 1, "a posição não passa da última questão"


def test_rascunho_de_quiz_de_outra_conta_e_404_e_nada_e_gravado():
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00")
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[])
    with pytest.raises(HTTPException) as erro:
        quizzes.salvar_rascunho(quiz["id"], quizzes.DraftIn(index=0, answers={}), BIA, banco)
    assert erro.value.status_code == 404
    assert banco.linhas("pathr_quiz")[0]["draft"] is None


def test_quiz_ja_enviado_nao_aceita_mais_rascunho():
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00")
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[_tentativa(quiz, ANA, "t")])
    assert quizzes.salvar_rascunho(quiz["id"], quizzes.DraftIn(index=0, answers={}), ANA, banco) == {"salvo": False}
    assert banco.linhas("pathr_quiz")[0]["draft"] is None


def test_falha_ao_gravar_o_rascunho_nao_derruba_a_tela():
    """A coluna `draft` ainda não migrada (ou o banco lento) não pode impedir ninguém de responder o quiz."""

    class BancoSemColuna(FakeSupabase):
        def table(self, nome):
            consulta = super().table(nome)
            if nome == "pathr_quiz":

                def update(payload):
                    raise RuntimeError("column pathr_quiz.draft does not exist")

                consulta.update = update  # type: ignore[method-assign]
            return consulta

    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00")
    banco = BancoSemColuna(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[])
    assert quizzes.salvar_rascunho(quiz["id"], quizzes.DraftIn(index=0, answers={}), ANA, banco) == {"salvo": False}


def test_rascunho_recusa_corpo_absurdo():
    with pytest.raises(ValueError):
        quizzes.DraftIn(index=-1, answers={})
    with pytest.raises(ValueError):
        quizzes.DraftIn(index=0, answers={str(i): 0 for i in range(101)})


# --- histórico ----------------------------------------------------------------


def test_historico_do_modulo_traz_as_tentativas_da_mais_nova_para_a_mais_antiga():
    q1, q2 = _quiz(ANA, "2026-09-01T10:00:00+00:00"), _quiz(ANA, "2026-09-10T10:00:00+00:00")
    banco = FakeSupabase(
        pathr_quiz=[q1, q2], pathr_question=[],
        pathr_attempt=[_tentativa(q1, ANA, "2026-09-01T11:00:00+00:00", 40.0), _tentativa(q2, ANA, "2026-09-10T11:00:00+00:00", 80.0)],
    )
    historico = quizzes.historico_do_modulo(NO, ANA, banco)
    assert [h["score"] for h in historico] == [80.0, 40.0]
    assert historico[0]["title"] == q2["title"] and historico[0]["total"] == 2
    assert {"attempt_id", "quiz_id", "duration_s", "finished_at", "correct_count"} <= set(historico[0])


def test_historico_nao_mistura_contas_nem_modulos():
    da_ana = _quiz(ANA, "2026-09-10T10:00:00+00:00")
    da_bia = _quiz(BIA, "2026-09-10T10:00:00+00:00")
    de_outro_modulo = _quiz(ANA, "2026-09-10T10:00:00+00:00", node_id=str(uuid.uuid4()))
    banco = FakeSupabase(
        pathr_quiz=[da_ana, da_bia, de_outro_modulo], pathr_question=[],
        pathr_attempt=[_tentativa(da_ana, ANA, "t1"), _tentativa(da_bia, BIA, "t2"), _tentativa(de_outro_modulo, ANA, "t3")],
    )
    assert [h["quiz_id"] for h in quizzes.historico_do_modulo(NO, ANA, banco)] == [da_ana["id"]]
    assert [h["quiz_id"] for h in quizzes.historico_do_modulo(NO, BIA, banco)] == [da_bia["id"]]


def test_historico_vazio_quando_nunca_houve_quiz():
    assert quizzes.historico_do_modulo(NO, ANA, FakeSupabase(pathr_quiz=[], pathr_attempt=[])) == []


# --- reabrir uma tentativa ----------------------------------------------------


def test_abre_uma_tentativa_antiga_com_questoes_e_correcao():
    quiz = _quiz(ANA, "2026-09-10T10:00:00+00:00")
    tentativa = _tentativa(quiz, ANA, "2026-09-10T11:00:00+00:00", 50.0)
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[tentativa])

    aberta = quizzes.tentativa(tentativa["id"], ANA, banco)

    assert aberta["quiz"]["id"] == quiz["id"] and len(aberta["quiz"]["questions"]) == 2
    assert aberta["result"]["attempt_id"] == tentativa["id"]
    assert aberta["result"]["score"] == 50.0 and aberta["result"]["results"][0]["correct_index"] == 1


def test_a_tentativa_de_outra_conta_e_404_e_o_gabarito_nao_vaza():
    """Ataque: a Bia pede a tentativa da Ana pelo id — e com ela o gabarito e as explicações."""
    quiz = _quiz(ANA, "2026-09-10T10:00:00+00:00")
    tentativa = _tentativa(quiz, ANA, "t")
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=_questoes(quiz), pathr_attempt=[tentativa])
    with pytest.raises(HTTPException) as erro:
        quizzes.tentativa(tentativa["id"], BIA, banco)
    assert erro.value.status_code == 404
    assert "porque sim" not in str(erro.value.detail)


def test_id_de_tentativa_que_nao_e_uuid_e_404():
    with pytest.raises(HTTPException) as erro:
        quizzes.tentativa("nao-e-uuid", ANA, FakeSupabase())
    assert erro.value.status_code == 404


# --- enviar limpa o rascunho, e gerar exige um módulo que é seu ----------------


def test_enviar_o_quiz_limpa_o_rascunho(monkeypatch):
    quiz = _quiz(ANA, "2026-09-20T10:00:00+00:00", draft={"index": 1, "answers": {"x": 1}, "updated_at": "t"})
    questoes = _questoes(quiz)
    banco = FakeSupabase(pathr_quiz=[quiz], pathr_question=questoes, pathr_attempt=[])
    monkeypatch.setattr(quizzes, "_recycle", lambda *a, **k: {})
    monkeypatch.setattr(quizzes, "_apply_result_to_tags", lambda *a, **k: None)
    monkeypatch.setattr(quizzes, "log_activity", lambda *a, **k: None)

    quizzes.submit_quiz(quiz["id"], quizzes.SubmitAnswers(answers={questoes[0]["id"]: 1}, duration_s=30), ANA, banco)

    assert banco.linhas("pathr_quiz")[0]["draft"] is None
    assert len(banco.linhas("pathr_attempt")) == 1


async def test_gerar_quiz_com_modulo_de_outra_conta_e_404_antes_de_gastar_a_ia(monkeypatch):
    """Ataque: a Bia passa o `node_id` do módulo da Ana — o quiz nasceria amarrado a ele e herdaria as tecnologias."""
    chamou_a_ia = []

    async def ia(*args, **kwargs):
        chamou_a_ia.append(1)
        raise AssertionError("a IA não deveria ser chamada")

    monkeypatch.setattr(quizzes, "generate_json", ia)
    roadmap_da_ana = str(uuid.uuid4())
    banco = FakeSupabase(
        pathr_roadmap=[{"id": roadmap_da_ana, "user_id": ANA["id"]}],
        pathr_roadmap_node=[{"id": NO, "roadmap_id": roadmap_da_ana, "title": "Docker", "tag_ids": [str(uuid.uuid4())]}],
        pathr_quiz=[],
    )
    with pytest.raises(HTTPException) as erro:
        await quizzes.generate_quiz(quizzes.GenerateQuiz(node_id=NO), BIA, banco)
    assert erro.value.status_code == 404
    assert chamou_a_ia == [] and banco.linhas("pathr_quiz") == []
