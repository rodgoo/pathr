"""Reciclagem do erro e escada de dificuldade.

Offline, como o resto da suíte: são funções puras, e é de propósito — a regra
que decide quando um conceito volta é a coisa mais fácil de quebrar sem
ninguém notar, porque o efeito só aparece semanas depois na vida de quem usa.
"""

from datetime import datetime, timezone

import pytest

from app.services import review


AGORA = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def _dias_ate(iso: str) -> int:
    return (datetime.fromisoformat(iso) - AGORA).days


# --- errar ------------------------------------------------------------------


def test_errar_faz_o_conceito_vencer_hoje():
    """"Essa pergunta precisa voltar novamente" — hoje, não amanhã. Um
    intervalo de 1 dia perderia a sessão de estudo em andamento."""
    novo = review.schedule({"ease": 2.5, "repetitions": 3, "interval_days": 15}, 2, now=AGORA)
    assert novo["interval_days"] == 0
    assert _dias_ate(novo["due_at"]) == 0


def test_errar_zera_a_sequencia_e_conta_a_recaida():
    novo = review.schedule(
        {"ease": 2.5, "repetitions": 4, "interval_days": 30, "lapses": 1}, 2, now=AGORA
    )
    assert novo["repetitions"] == 0
    assert novo["lapses"] == 2


def test_errar_derruba_o_ease_mais_do_que_acertar_levanta():
    """A assimetria é do SM-2 e faz sentido: uma falha é evidência mais forte
    de que o intervalo estava errado do que um acerto é de que estava certo."""
    queda = 2.5 - review.schedule({"ease": 2.5}, 2, now=AGORA)["ease"]
    subida = review.schedule({"ease": 2.0}, 5, now=AGORA)["ease"] - 2.0
    assert queda > subida


def test_ease_tem_piso():
    card = {"ease": 1.3}
    for _ in range(5):
        card = {"ease": review.schedule(card, 2, now=AGORA)["ease"]}
    assert card["ease"] >= 1.3


# --- acertar ----------------------------------------------------------------


def test_acertos_seguidos_afastam_o_conceito_progressivamente():
    """É isto que faz o item parar de aparecer: cada acerto empurra a próxima
    aparição para mais longe."""
    card = {"ease": 2.5, "repetitions": 0, "interval_days": 0}
    intervalos = []
    for _ in range(4):
        proximo = review.schedule(card, 5, now=AGORA)
        intervalos.append(proximo["interval_days"])
        card = proximo
    assert intervalos == sorted(intervalos)
    assert intervalos[0] == 1 and intervalos[1] == 6
    assert intervalos[-1] > intervalos[-2]


def test_ease_tem_teto_para_o_intervalo_nao_explodir():
    """Sem teto, uma sequência longa de acertos faria o conceito voltar daqui a
    anos — tarde demais para um plano que dura meses."""
    card = {"ease": 2.5}
    for _ in range(10):
        card = {"ease": review.schedule(card, 5, now=AGORA)["ease"]}
    assert card["ease"] <= 2.5


def test_acerto_nao_conta_recaida():
    novo = review.schedule({"ease": 2.5, "lapses": 2}, 5, now=AGORA)
    assert "lapses" not in novo


# --- agrupamento por conceito -----------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("Diferença entre COPY e ADD", "diferenca entre copy e add"),
        ("Escopo de variável em closure", "ESCOPO DE VARIAVEL EM CLOSURE!"),
        ("índices parciais", "indices   parciais"),
    ],
)
def test_mesma_ideia_escrita_de_formas_diferentes_e_uma_so(a, b):
    assert review.concept_key(a) == review.concept_key(b)


def test_ideias_diferentes_nao_colidem():
    assert review.concept_key("COPY vs ADD") != review.concept_key("ENTRYPOINT vs CMD")


def test_conceito_vazio_nao_vira_chave():
    assert review.concept_key(None) == ""
    assert review.concept_key("   ") == ""


# --- escada de dificuldade ---------------------------------------------------


def test_sem_historico_comeca_no_meio():
    assert review.next_difficulty(proficiency=3, recent_scores=[]) == review.MEDIO


def test_sem_historico_iniciante_comeca_facil():
    assert review.next_difficulty(proficiency=1, recent_scores=[]) == review.FACIL


def test_indo_bem_e_com_nivel_a_dificuldade_sobe():
    assert review.next_difficulty(proficiency=3, recent_scores=[90, 85, 80]) == review.DIFICIL


def test_indo_mal_a_dificuldade_cai():
    assert review.next_difficulty(proficiency=2, recent_scores=[40, 30]) == review.FACIL


def test_nota_alta_sem_nivel_ainda_nao_e_dificil():
    """Uma boa nota em tag que a pessoa mal conhece pode ser sorte em questão
    fácil. O nível da tag precisa acompanhar."""
    assert review.next_difficulty(proficiency=1, recent_scores=[95, 90]) == review.FACIL


def test_pendencia_acumulada_trava_a_subida():
    """O freio: sem ele, quem tem média alta e cinco lacunas abertas receberia
    questão difícil — a média esconde exatamente o que a revisão quer fechar."""
    sem_pendencia = review.next_difficulty(proficiency=4, recent_scores=[95, 90])
    com_pendencia = review.next_difficulty(proficiency=4, recent_scores=[95, 90], pending_reviews=3)
    assert sem_pendencia == review.DIFICIL
    assert com_pendencia == review.MEDIO


def test_pendencia_trava_mas_nao_rebaixa_quem_vai_bem():
    """Só impede subir. Rebaixar puniria a pessoa pelo que ela já está
    corrigindo."""
    assert (
        review.next_difficulty(proficiency=3, recent_scores=[85], pending_reviews=9)
        == review.MEDIO
    )


def test_pendencia_em_iniciante_mantem_facil():
    assert (
        review.next_difficulty(proficiency=0, recent_scores=[30], pending_reviews=5)
        == review.FACIL
    )


# --- compatibilidade com o baralho de inglês --------------------------------


def test_agendador_serve_ao_vocabulario_que_nao_tem_lapses():
    """`pathr_english_vocab` não tem coluna `lapses` nem `last_reviewed_at`. O
    router de inglês descarta as duas; o resto do payload precisa bater."""
    novo = review.schedule({"ease": 2.5, "repetitions": 1, "interval_days": 1}, 5, now=AGORA)
    novo.pop("lapses", None)
    novo.pop("last_reviewed_at", None)
    assert set(novo) == {"ease", "repetitions", "interval_days", "due_at"}
