"""O treino diário pelo router: cria, persiste, corrige, recicla e resume.

Sem rede e sem banco: `FakeSupabase` no lugar do PostgREST e um `generate_json`
falso que devolve o exercício pedido para cada índice.
"""

import asyncio
import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import language_practice as router
from app.services import treino_idioma as T
from tests.fake_supabase import FakeSupabase

USUARIO = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "ana@exemplo.com",
    "name": "Ana",
    "timezone_name": "America/Sao_Paulo",
}


def _exercicio(pedido_linha: str) -> dict:
    """Um item válido para o tipo que o pedido nomeou."""
    indice = int(pedido_linha.split("indice ")[1].split(":")[0])
    tipo = pedido_linha.split("tipo ")[1].split(";")[0]
    base = {"indice": indice, "tipo": tipo, "explicacao": "porque é assim", "topico": "preposições"}
    escolha = {"enunciado": "Choose", "alternativas": ["in", "on", "at", "by"], "correta": 2}
    por_tipo = {
        "mcq": escolha,
        "gap": {**escolha, "frase": "See you ___ the meeting."},
        "image": {**escolha, "emoji": "🍎"},
        "listening": {**escolha, "texto": "Ana: See you at the meeting.\nMarc: Sure."},
        "reorder": {"enunciado": "Monte", "frase": "I will join the call later", "traducao": "x"},
        "match": {"enunciado": "Associe", "pares": [
            {"a": "meeting", "b": "reunião"}, {"a": "deadline", "b": "prazo"},
            {"a": "bug", "b": "defeito"}, {"a": "release", "b": "lançamento"}]},
        "dictation": {"enunciado": "Escreva", "texto": "The deploy finished five minutes ago"},
        "speaking": {"enunciado": "Leia", "texto": "I will send the report tomorrow morning"},
    }
    return {**base, **por_tipo[tipo]}


@pytest.fixture
def ia(monkeypatch):
    chamadas = []

    async def falso(_sistema, pedido, _schema):
        chamadas.append(pedido)
        linhas = [linha for linha in pedido.splitlines() if linha.startswith("- indice ")]
        return SimpleNamespace(content={"itens": [_exercicio(linha) for linha in linhas]})

    monkeypatch.setattr(router, "generate_json", falso)
    monkeypatch.setattr(router, "log_activity", lambda *a, **k: None)
    return chamadas


def _banco(**extra):
    tabelas = {
        "pathr_english_profile": [{"user_id": USUARIO["id"], "language": "en", "cefr_level": "B1",
                                   "daily_goal_min": 10, "enabled": True}],
        "pathr_english_item": [],
        "pathr_english_session": [],
        "pathr_review_item": [],
    }
    tabelas.update(extra)
    return FakeSupabase(**tabelas)


def _rodar(corotina):
    return asyncio.run(corotina)


def _linha(banco, item_id):
    return next(linha for linha in banco.linhas("pathr_english_item") if str(linha["id"]) == item_id)


def _resposta_certa(linha):
    tipo, gabarito = linha["type"], linha["correct"]
    if tipo in ("mcq", "gap", "image", "listening"):
        return {"indice": gabarito["indice"]}
    if tipo == "reorder":
        return {"tokens": gabarito["frases"][0].split()}
    if tipo == "match":
        return {"pares": gabarito["pares"]}
    return {"texto": gabarito["texto"]}


# --- criação e persistência --------------------------------------------------


def test_abrir_a_tela_nao_cria_treino(ia):
    banco = _banco()
    assert router.practice_today(language="en", current_user=USUARIO, supabase=banco) is None
    assert ia == []


def test_comecar_gera_o_primeiro_lote_e_esconde_o_gabarito(ia):
    banco = _banco()
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    assert treino["total"] == 8
    assert len(treino["items"]) == router._PRIMEIRO_LOTE
    assert treino["generating"] is True
    for item in treino["items"]:
        assert "correct" not in item
        assert "indice" not in item["payload"] and "frases" not in item["payload"]
        assert "pares" not in item["payload"]


def test_voltar_no_mesmo_dia_retoma_o_mesmo_treino(ia):
    banco = _banco()
    primeiro = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    chamadas = len(ia)
    segundo = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    assert segundo["id"] == primeiro["id"]
    assert len(banco.linhas("pathr_english_session")) == 1
    assert len(ia) == chamadas


def test_o_dia_e_o_da_pessoa_e_nao_o_do_servidor(monkeypatch):
    # 01:30 UTC de 13/09 ainda é 22:30 de 12/09 em São Paulo.
    monkeypatch.setattr(router, "_agora", lambda: datetime(2026, 9, 13, 1, 30, tzinfo=timezone.utc))
    assert router._hoje(USUARIO).isoformat() == "2026-09-12"


def test_treino_que_a_ia_nao_consegue_montar_e_apagado_para_poder_tentar_de_novo(monkeypatch):
    """Tudo descartado deixaria um treino vazio travando o dia inteiro: o
    índice único impediria criar outro até amanhã."""
    async def quebrada(_s, _p, _schema):
        return SimpleNamespace(content={"itens": []})

    monkeypatch.setattr(router, "generate_json", quebrada)
    banco = _banco()
    with pytest.raises(HTTPException) as erro:
        _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    assert erro.value.status_code == 503
    assert banco.linhas("pathr_english_session") == []


def test_provedor_fora_do_ar_nao_descarta_o_treino(monkeypatch):
    """Queda passageira não pode apagar exercícios: o treino fica salvo."""
    async def fora(_s, _p, _schema):
        raise router.AiProviderError("fora do ar")

    monkeypatch.setattr(router, "generate_json", fora)
    banco = _banco()
    with pytest.raises(HTTPException) as erro:
        _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    assert erro.value.status_code == 503
    sessao = banco.linhas("pathr_english_session")[0]
    assert not sessao["feedback"].get("descartados")


# --- correção e reciclagem ----------------------------------------------------


def _escolha(treino):
    return next(i for i in treino["items"] if i["type"] in ("mcq", "gap", "image", "listening"))


def test_erro_vira_ponto_de_melhora_com_idioma_habilidade_e_topico(ia):
    banco = _banco()
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    alvo = _escolha(treino)
    errada = (_linha(banco, alvo["id"])["correct"]["indice"] + 1) % 4

    resposta = _rodar(router.answer_practice(
        treino["id"], router.PracticeAnswer(item_id=alvo["id"], answer={"indice": errada}),
        current_user=USUARIO, supabase=banco,
    ))

    assert resposta["is_correct"] is False
    assert resposta["explanation"] == "porque é assim"
    assert resposta["improvement"] == "novo_ponto"
    ponto = banco.linhas("pathr_review_item")[0]
    # O tópico é o do exercício: "preposições" só vale onde está no catálogo
    # daquela habilidade; fora dele fica o tópico pedido.
    assert (ponto["language"], ponto["skill"], ponto["topic"]) == ("en", alvo["skill"], alvo["topic"])


def test_resposta_repetida_devolve_o_mesmo_desfecho(ia):
    """Clique duplo não pode trocar a resposta nem criar um segundo ponto."""
    banco = _banco()
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    alvo = _escolha(treino)
    certa_indice = _linha(banco, alvo["id"])["correct"]["indice"]
    errada = router.PracticeAnswer(item_id=alvo["id"], answer={"indice": (certa_indice + 1) % 4})
    _rodar(router.answer_practice(treino["id"], errada, current_user=USUARIO, supabase=banco))

    certa = router.PracticeAnswer(item_id=alvo["id"], answer={"indice": certa_indice})
    de_novo = _rodar(router.answer_practice(treino["id"], certa, current_user=USUARIO, supabase=banco))
    assert de_novo["is_correct"] is False
    assert len(banco.linhas("pathr_review_item")) == 1


def test_acerto_na_revisao_sobe_o_degrau_do_ponto(ia):
    """O ponto volta com repetitions 0 (reconhecer). Acertando, passa a 1 — e
    no próximo treino volta como lacuna, não mais como múltipla escolha."""
    agora = datetime.now(timezone.utc).isoformat()
    banco = _banco(pathr_review_item=[{
        "id": "22222222-2222-2222-2222-222222222222", "user_id": USUARIO["id"], "kind": "language",
        "language": "en", "skill": "grammar", "topic": "preposições", "band": "B1",
        "front": "See you in the meeting", "back": "at", "repetitions": 0, "ease": 2.5,
        "interval_days": 0, "lapses": 1, "due_at": "2020-01-01T00:00:00+00:00",
    }])
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    revisao = next(i for i in treino["items"] if i["origin"] == "revisao")
    assert revisao["type"] == "mcq"

    resposta = _rodar(router.answer_practice(
        treino["id"],
        router.PracticeAnswer(item_id=revisao["id"], answer=_resposta_certa(_linha(banco, revisao["id"]))),
        current_user=USUARIO, supabase=banco,
    ))
    ponto = banco.linhas("pathr_review_item")[0]
    assert resposta["improvement"] == "subiu"
    assert ponto["repetitions"] == 1 and ponto["due_at"] > agora
    assert T.formato_do_ponto(ponto["repetitions"], "grammar", random.Random(0)) == "gap"


def test_fala_sem_microfone_nao_e_erro_nem_ponto(ia):
    banco = _banco()
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    sessao = banco.linhas("pathr_english_session")[0]
    banco.tabelas["pathr_english_item"].append({
        "id": "33333333-3333-3333-3333-333333333333", "user_id": USUARIO["id"],
        "session_id": sessao["id"], "language": "en", "skill": "speaking", "type": "speaking",
        "cefr_band": "B1", "topic": "pronúncia", "prompt": "Leia", "options": [],
        "correct": {"texto": "I will send the report tomorrow"}, "feedback": "x",
        "payload": {"texto": "I will send the report tomorrow"}, "order_index": 99,
        "origin": "novo", "is_correct": None, "skipped": False,
    })
    resposta = _rodar(router.answer_practice(
        treino["id"],
        router.PracticeAnswer(item_id="33333333-3333-3333-3333-333333333333", answer={"texto": ""}),
        current_user=USUARIO, supabase=banco,
    ))
    assert resposta["skipped"] is True
    assert banco.linhas("pathr_review_item") == []


# --- fim do treino -----------------------------------------------------------


def test_treino_completo_fecha_com_resumo_de_topicos_e_niveis(ia):
    banco = _banco()
    treino = _rodar(router.start_practice(language="en", current_user=USUARIO, supabase=banco))
    sessao_id = treino["id"]
    # O segundo plano não roda no teste: a tela pediria o treino de novo, e a
    # geração acontece ali.
    for _ in range(20):
        atual = _rodar(router.get_practice(sessao_id, current_user=USUARIO, supabase=banco))
        if not atual["items"]:
            break
        for item in atual["items"]:
            _rodar(router.answer_practice(
                sessao_id,
                router.PracticeAnswer(item_id=item["id"], answer=_resposta_certa(_linha(banco, item["id"]))),
                current_user=USUARIO, supabase=banco,
            ))
    final = _rodar(router.get_practice(sessao_id, current_user=USUARIO, supabase=banco))
    assert final["status"] == "done"
    resumo = final["summary"]
    assert resumo["answered"] == 8 and resumo["correct"] == 8
    assert resumo["topics"] and all(t["answered"] >= 1 for t in resumo["topics"])
    assert resumo["levels"]


def test_nivel_por_habilidade_soma_nivelamento_e_treino(ia):
    banco = _banco(pathr_english_item=[
        {"id": f"i{n}", "user_id": USUARIO["id"], "language": "en", "skill": "listening",
         "topic": "números e datas", "cefr_band": "B2", "type": "dictation", "is_correct": True,
         "skipped": False, "answered_at": "2026-09-10T10:00:00+00:00"}
        for n in range(10)
    ])
    quadro = router.skills(language="en", current_user=USUARIO, supabase=banco)
    escuta = next(s for s in quadro["skills"] if s["skill"] == "listening")
    assert escuta["level"] in ("B2", "C1")
    assert escuta["topics"][0]["topic"] == "números e datas"
    assert escuta["topics"][0]["correct"] == 10
