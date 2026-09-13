"""O treino diário: o que entra, em que formato, e como se corrige.

Sem banco e sem IA — a regra, que é o que erra em silêncio.
"""

import random

import pytest

from app.services import proficiencia_idioma as P
from app.services import treino_idioma as T


def _quadro(fracos=(), niveis=None, respondidas=None):
    niveis = niveis or {}
    respondidas = respondidas or {}
    return {
        "overall": {"level": "B1"},
        "skills": [
            {
                "skill": h,
                "level": niveis.get(h, "B1"),
                "answered": respondidas.get(h, 0),
                "topics": [
                    {"topic": t, "score": 30, "status": "reforcar"} for (hh, t) in fracos if hh == h
                ],
            }
            for h in T.FORMATOS
        ],
    }


def _ponto(i, skill="grammar", repeticoes=0):
    return {"id": f"p{i}", "front": f"frase errada {i}", "back": "a certa", "skill": skill,
            "topic": "preposições", "band": "B1", "repetitions": repeticoes}


# --- tamanho e composição ----------------------------------------------------


@pytest.mark.parametrize("minutos,esperado", [(5, 8), (15, 12), (30, 20), (60, 20)])
def test_tamanho_acompanha_a_meta_diaria(minutos, esperado):
    assert T.quantos_exercicios(minutos) == esperado


def test_revisao_vem_primeiro_e_tem_teto():
    """Com 30 pontos vencidos o treino não vira só revisão: sobra espaço para o
    fraco e para o novo, senão ninguém sai do lugar."""
    plano = T.montar(_quadro(), [_ponto(i) for i in range(30)], 15, semente=1)
    revisoes = [e for e in plano if e.origem == "revisao"]
    assert len(plano) == 12
    assert len(revisoes) == round(12 * 0.4)
    assert plano[0].origem == "revisao"


def test_topico_a_reforcar_entra_no_treino():
    plano = T.montar(_quadro(fracos=[("listening", "números e datas")]), [], 15, semente=2)
    assert any(e.origem == "reforco" and e.topico == "números e datas" for e in plano)


def test_habilidade_nunca_treinada_vem_antes_no_novo():
    respondidas = {h: 50 for h in T.FORMATOS}
    respondidas["speaking"] = 0
    plano = T.montar(_quadro(respondidas=respondidas), [], 15, semente=3)
    assert any(e.habilidade == "speaking" for e in plano)


def test_parte_do_novo_fica_uma_banda_acima():
    plano = T.montar(_quadro(), [], 15, semente=4)
    assert any(e.banda == "B2" and e.origem == "novo" for e in plano)
    assert all(e.banda in ("B1", "B2") for e in plano)


def test_dois_formatos_iguais_quase_nunca_ficam_seguidos():
    for semente in range(40):
        plano = T.montar(_quadro(), [_ponto(i) for i in range(5)], 30, semente=semente)
        tipos = [e.tipo for e in plano]
        repetidos = sum(1 for a, b in zip(tipos, tipos[1:]) if a == b)
        # Guloso: só repete quando SÓ sobrou um formato no fim da fila.
        assert repetidos <= 1, (semente, tipos)


def test_nenhum_formato_domina_o_treino():
    """Sorteio puro dava 60% de múltipla escolha: treino de reconhecer, quase
    sem produção — o contrário das quatro vertentes."""
    from collections import Counter

    for semente in range(40):
        plano = T.montar(_quadro(), [_ponto(i) for i in range(5)], 30, semente=semente)
        tipo, vezes = Counter(e.tipo for e in plano).most_common(1)[0]
        assert vezes <= 0.4 * len(plano), (semente, tipo, vezes)
        producao = sum(1 for e in plano if e.tipo in ("reorder", "dictation", "speaking"))
        assert producao >= 3, (semente, [e.tipo for e in plano])


def test_revisoes_ficam_espalhadas_e_nao_amontoadas_no_fim():
    """A primeira versão empurrava as revisões todas para o fim do treino."""
    for semente in range(20):
        plano = T.montar(_quadro(), [_ponto(i) for i in range(8)], 30, semente=semente)
        posicoes = [i for i, e in enumerate(plano) if e.origem == "revisao"]
        assert posicoes[0] == 0
        assert max(b - a for a, b in zip(posicoes, posicoes[1:])) <= 4, posicoes
        assert posicoes[-1] < len(plano) - 1 or len(posicoes) == 1


def test_mesmo_dia_monta_o_mesmo_treino():
    a = T.montar(_quadro(), [_ponto(1)], 15, semente=20260912)
    b = T.montar(_quadro(), [_ponto(1)], 15, semente=20260912)
    assert [x.para_json() for x in a] == [y.para_json() for y in b]


def test_formato_combina_com_a_habilidade():
    for e in T.montar(_quadro(), [_ponto(i, "vocabulary") for i in range(4)], 30, semente=5):
        assert e.tipo in T.FORMATOS[e.habilidade]


# --- o ponto de melhora volta lapidado ----------------------------------------


def test_ponto_sobe_de_reconhecer_para_produzir():
    rng = random.Random(0)
    assert T.formato_do_ponto(0, "grammar", rng) == "mcq"
    assert T.formato_do_ponto(1, "grammar", rng) == "gap"
    assert T.formato_do_ponto(2, "grammar", rng) == "reorder"
    assert T.formato_do_ponto(3, "listening", rng) == "dictation"
    assert T.formato_do_ponto(9, "speaking", rng) == "speaking"


def test_degrau_que_a_habilidade_nao_tem_cai_no_mais_exigente_possivel():
    """Leitura só tem múltipla escolha: não há como pedir ditado de leitura."""
    assert T.formato_do_ponto(3, "reading", random.Random(0)) == "mcq"
    assert T.formato_do_ponto(1, "listening", random.Random(0)) in T.FORMATOS["listening"]


def test_revisao_que_repete_a_frase_do_erro_e_recusada():
    """Caso real da primeira geração: o erro voltou com 93% das palavras."""
    lembrete = "We discussed about the deadline in the meeting.\n→ We discussed the deadline"
    repetida = {"frase": "We discussed the deadline in the meeting."}
    nova = {"frase": "Let's discuss the budget tomorrow morning."}
    assert T.repete_o_erro(repetida, lembrete)
    assert not T.repete_o_erro(nova, lembrete)
    # Exercício que não é revisão nunca é recusado por isso.
    assert not T.repete_o_erro(repetida, None)


def test_revisao_que_reaproveita_as_alternativas_do_erro_e_recusada():
    """Caso de produção: a pergunta de fechamento de e-mail voltou com as
    mesmas alternativas, incluindo a resposta certa do erro."""
    lembrete = (
        "Choose the best closing sentence for your email.\n"
        "→ Looking forward to seeing you. Depois de 'look forward to' vem -ing."
    )
    copia = {"enunciado": "Choose", "alternativas": [
        "Looking forward to see you.", "Looking forward to seeing you.", "I look forward see you.", "Looking to forward you."]}
    nova = {"enunciado": "Choose", "alternativas": [
        "We are looking forward to hear from the client.", "We are looking forward to hearing from the client.",
        "We look forward hearing from the client.", "We are looking to forward the client."]}
    assert T.repete_o_erro(copia, lembrete)
    assert not T.repete_o_erro(nova, lembrete)


def test_pergunta_longa_identica_a_do_erro_e_copia():
    """Caso de produção: a pergunta voltou palavra por palavra, com as
    alternativas mal disfarçadas."""
    lembrete = (
        "Choose the most natural way to say that the requested feature is out of scope.\n"
        "→ That feature is out of scope. A expressão idiomática é out of scope."
    )
    copia = {
        "enunciado": "Choose the most natural way to say that the requested feature is out of scope.",
        "alternativas": ["The feature you asked for is out of scope.", "The feature you asked for is out of the scope.",
                         "The feature you asked for is beyond the scope.", "The feature you asked for is out of scope's."],
    }
    assert T.repete_o_erro(copia, lembrete)


def test_enunciado_repetido_nao_e_copia():
    """"Choose the best option" se repete entre exercícios diferentes: compará-lo
    recusava revisões boas."""
    lembrete = "Choose the best option.\n→ Could you clarify?"
    item = {"enunciado": "Choose the best option.",
            "alternativas": ["Can you walk me through the rollback plan?", "Can you walk me the rollback plan?",
                             "Can you explain me the rollback plan?", "Can you pass me through the rollback?"]}
    assert not T.repete_o_erro(item, lembrete)


def test_revisao_leva_o_erro_original_para_ser_reescrito():
    plano = T.montar(_quadro(), [_ponto(7)], 15, semente=6)
    revisao = next(e for e in plano if e.origem == "revisao")
    assert "frase errada 7" in revisao.lembrete
    assert revisao.ponto_id == "p7"


# --- validação ----------------------------------------------------------------


def _enc(tipo, habilidade="grammar"):
    return T.Encomenda(0, tipo, habilidade, "preposições", "B1", "novo")


BASE = {
    "enunciado": "Choose",
    "explicacao": "porque sim",
    "alternativas": ["in", "on", "at", "by"],
    "correta": 2,
}


def test_gabarito_nao_vai_para_a_tela():
    pronto = T.validar(dict(BASE), _enc("mcq"))
    assert "correta" not in pronto["payload"] and "indice" not in pronto["payload"]
    assert pronto["gabarito"] == {"indice": 2}


@pytest.mark.parametrize(
    "tipo,extra",
    [
        ("mcq", {"alternativas": ["a", "b", "c"]}),
        ("mcq", {"alternativas": ["a", "A", "b", "c"]}),
        ("gap", {"frase": "I live São Paulo."}),
        ("gap", {"frase": "I ___ in ___."}),
        ("image", {"emoji": "apple"}),
        ("listening", {"texto": "Hi"}),
        ("reorder", {"frase": "Hi there"}),
        ("match", {"pares": [{"a": "x", "b": "y"}]}),
        ("dictation", {"texto": "ok"}),
        ("mcq", {"explicacao": ""}),
    ],
)
def test_item_ruim_e_descartado(tipo, extra):
    assert T.validar({**BASE, **extra}, _enc(tipo)) is None


def test_ditado_nao_mostra_o_texto_e_a_fala_mostra():
    frase = "The build failed again today"
    ditado = T.validar({**BASE, "texto": frase}, _enc("dictation", "listening"))
    fala = T.validar({**BASE, "texto": frase}, _enc("speaking", "speaking"))
    assert "texto" not in ditado["payload"] and ditado["payload"]["audio"]
    assert fala["payload"]["texto"] == frase


def test_frase_para_montar_chega_embaralhada():
    frase = "I have already merged the pull request"
    pronto = T.validar({**BASE, "frase": frase}, _enc("reorder"))
    assert pronto["payload"]["pecas"] != frase.split()
    assert sorted(pronto["payload"]["pecas"]) == sorted(frase.split())


def test_topico_fora_do_catalogo_fica_com_o_pedido():
    assert T.validar({**BASE, "topico": "Preposições!"}, _enc("mcq"))["topico"] == "preposições"
    assert T.validar({**BASE, "topico": "coisas aleatórias"}, _enc("mcq"))["topico"] == "preposições"


# --- correção -----------------------------------------------------------------


def test_montar_frase_aceita_ordem_alternativa_e_ignora_pontuacao():
    pronto = T.validar(
        {**BASE, "frase": "Yesterday I fixed the bug.", "aceitas": ["I fixed the bug yesterday."]},
        _enc("reorder"),
    )
    g, p = pronto["gabarito"], pronto["payload"]
    assert T.corrigir("reorder", g, p, {"tokens": ["I", "fixed", "the", "bug", "yesterday."]}).acertou
    assert T.corrigir("reorder", g, p, {"tokens": ["Yesterday", "I", "fixed", "the", "bug"]}).acertou
    assert not T.corrigir("reorder", g, p, {"tokens": ["I", "the", "fixed", "bug", "yesterday"]}).acertou


def test_associar_pares():
    pares = [{"a": "meeting", "b": "reunião"}, {"a": "deadline", "b": "prazo"},
             {"a": "bug", "b": "defeito"}, {"a": "release", "b": "lançamento"}]
    pronto = T.validar({**BASE, "pares": pares}, _enc("match", "vocabulary"))
    g, p = pronto["gabarito"], pronto["payload"]
    certa = {i: p["direita"].index(par["b"]) for i, par in enumerate(pares)}
    assert T.corrigir("match", g, p, {"pares": certa}).acertou
    trocada = dict(certa)
    trocada[0], trocada[1] = certa[1], certa[0]
    resultado = T.corrigir("match", g, p, {"pares": trocada})
    assert not resultado.acertou and resultado.detalhe == {"certos": 2, "total": 4}


def test_ditado_e_por_palavra_e_perdoa_so_acento():
    g = {"texto": "Je voudrais un café, s’il vous plaît."}
    assert T.corrigir("dictation", g, {}, {"texto": "je voudrais un café s’il vous plaît"}).acertou
    sem_acento = T.corrigir("dictation", g, {}, {"texto": "je voudrais un cafe s’il vous plait"})
    assert sem_acento.acertou and sem_acento.detalhe["acentos"] is True
    errado = T.corrigir("dictation", g, {}, {"texto": "je voudrais du thé s’il vous plaît"})
    assert not errado.acertou
    assert "un" in errado.detalhe["faltaram"] and "café" in errado.detalhe["faltaram"]


def test_there_no_lugar_de_their_e_erro_inteiro():
    g = {"texto": "They pushed their changes"}
    assert T.semelhanca(g["texto"], "They pushed there changes") == 0.75
    assert not T.corrigir("dictation", g, {}, {"texto": "They pushed there changes"}).acertou


def test_fala_tolera_o_microfone_e_vazio_e_pulo_nao_erro():
    g = {"texto": "I will send the report by Friday"}
    assert T.corrigir("speaking", g, {}, {"texto": "I will send a report by Friday"}).acertou
    vazio = T.corrigir("speaking", g, {}, {"texto": "  "})
    assert vazio.pulado and not vazio.acertou


def test_resposta_para_estimativa_usa_a_chance_do_formato_e_ignora_pulo():
    linhas = [
        {"skill": "listening", "topic": "números e datas", "cefr_band": "B1", "type": "dictation",
         "is_correct": True, "answered_at": "2026-09-12T10:00:00+00:00"},
        {"skill": "speaking", "cefr_band": "B1", "type": "speaking", "is_correct": False, "skipped": True},
        {"skill": "grammar", "cefr_band": "B1", "type": "mcq", "is_correct": None},
    ]
    respostas = T.respostas_para_estimativa(linhas)
    assert len(respostas) == 1 and respostas[0].chance == 0.0
    assert isinstance(respostas[0], P.Resposta)


# ---------------------------------------------------------------------------
# Texto que vai para a voz: nunca com lacuna escrita
# ---------------------------------------------------------------------------


def test_escuta_com_lacuna_no_audio_e_recusada():
    """A voz leria "underscore underscore" no lugar da palavra que a pergunta cobra."""
    item = {
        "enunciado": "What will Ana do?",
        "texto": "Ana: I ___ push it after lunch.\nMarc: Thanks.",
        "alternativas": ["will", "would", "was", "am"],
        "correta": 0,
        "explicacao": "x",
    }
    assert T.validar(item, T.Encomenda(0, "listening", "listening", "futuro", "B1", "novo")) is None


def test_ditado_com_lacuna_e_recusado():
    item = {"texto": "Please ___ the pull request today", "explicacao": "x"}
    assert T.validar(item, T.Encomenda(0, "dictation", "listening", "futuro", "B1", "novo")) is None


def test_audio_gravado_com_lacuna_sai_com_a_palavra_certa():
    payload = {"audio": "Ana: I __ push it after lunch.", "alternativas": ["would", "'ll", "was", "am"]}
    assert T.audio_para_voz(payload, {"indice": 1})["audio"] == "Ana: I 'll push it after lunch."


def test_audio_sem_gabarito_perde_so_o_simbolo():
    falado = T.audio_para_voz({"audio": "We __ and __ it."}, None)["audio"]
    assert "_" not in falado


def test_audio_sem_lacuna_nao_muda():
    payload = {"audio": "Marc: I'll review it."}
    assert T.audio_para_voz(payload, {"indice": 0}) is payload
