"""O nível por habilidade está certo? Conferido contra alunos de nível CONHECIDO.

Não dá para saber se uma estimativa de nível acerta olhando para ela: é
preciso alguém de nível sabido respondendo. Aqui esse alguém é simulado com o
mesmo modelo de resposta (dificuldade, chute de 25%), com semente fixa para o
resultado não variar entre execuções.

O que as simulações mostraram, e o que estes testes seguram:

- No NIVELAMENTO (itens adaptativos, 20 respostas), o método antigo não era
  ruim para a nota geral — acertava a banda em 65-76% dos alunos, perto do
  teto possível com tão poucas respostas. O defeito estava na quebra por
  habilidade, que era porcentagem e não nível.
- No TREINO DIÁRIO, que não é adaptativo, o método antigo nunca reconhece a
  melhora: alguém que subiu para B2 treinando itens B1 continuava B1 em 100%
  das simulações, mesmo com 60 respostas. É o caso que o progresso contínuo
  precisa acertar.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest

from app.services import proficiencia_idioma as P

AGORA = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def _escada(theta: float, n: int, rng: random.Random) -> list[P.Resposta]:
    """O nivelamento: acertou sobe uma banda, errou desce."""
    banda, saida = "B1", []
    for _ in range(n):
        acertou = rng.random() < P.probabilidade_de_acerto(theta, banda, 0.25)
        saida.append(P.Resposta("grammar", "t", banda, acertou, 0.25))
        banda = P.BANDAS[max(0, min(5, P.indice_da_banda(banda) + (1 if acertou else -1)))]
    return saida


def _treino_fixo(theta: float, n: int, rng: random.Random, banda: str) -> list[P.Resposta]:
    saida = []
    for _ in range(n):
        b = P.BANDAS[min(5, P.indice_da_banda(banda) + rng.choice([0, 0, 1]))]
        acertou = rng.random() < P.probabilidade_de_acerto(theta, b, 0.25)
        saida.append(P.Resposta("grammar", "t", b, acertou, 0.25))
    return saida


def _metodo_antigo(respostas: list[P.Resposta]) -> str:
    certos = [P.indice_da_banda(r.band) for r in respostas if r.correct]
    return P.BANDAS[round(sum(certos) / len(certos))] if certos else "A1"


# --- os três defeitos da tela antiga ----------------------------------------


def test_porcentagem_nao_e_nivel():
    """3 de 3 em itens A2 e 3 de 3 em itens C1 davam o mesmo "100%"."""
    faceis = [P.Resposta("reading", "t", "A2", True, 0.25)] * 3
    dificeis = [P.Resposta("reading", "t", "C1", True, 0.25)] * 3
    assert P.estimar(dificeis).theta > P.estimar(faceis).theta + 1


def test_chute_pesa_menos_que_resposta_sem_alternativas():
    """Acertar uma múltipla escolha de quatro podia ser sorte; acertar um
    ditado, não."""
    com_chute = P.estimar([P.Resposta("reading", "t", "B2", True, 0.25)])
    sem_chute = P.estimar([P.Resposta("reading", "t", "B2", True, 0.0)])
    assert sem_chute.theta > com_chute.theta


def test_duas_respostas_nao_viram_certeza():
    """O "Corporativo: 100%" da conta real saiu de duas perguntas."""
    duas = P.estimar([P.Resposta("business", "t", "B1", True, 0.25)] * 2)
    assert duas.confianca == "inicial"


def test_nao_se_prova_nivel_sem_item_daquele_nivel():
    """Dez ditados B2 certos davam C2. Mostram "acima de B2", não C2."""
    certos = [P.Resposta("listening", "t", "B2", True, 0.0)] * 10
    assert P.estimar(certos).nivel == "C1"
    errados = [P.Resposta("listening", "t", "B2", False, 0.0)] * 10
    assert P.estimar(errados).nivel == "B1"


def test_sem_respostas_nao_inventa_nivel():
    quadro = P.quadro([], ["listening"])
    assert quadro["skills"][0]["level"] is None
    assert quadro["skills"][0]["confidence"] == "sem_dados"


# --- verificação contra alunos de nível conhecido ----------------------------


@pytest.mark.parametrize("real", ["A2", "B1", "B2", "C1"])
def test_nivelamento_de_vinte_itens_acerta_a_banda(real):
    rng = random.Random(2026)
    theta = P.dificuldade(real)
    exatos = perto = 0
    for _ in range(200):
        estimativa = P.estimar(_escada(theta, 20, rng))
        exatos += estimativa.nivel == real
        perto += abs(P.indice_da_banda(estimativa.nivel) - P.indice_da_banda(real)) <= 1
    # Com 20 respostas o erro natural é ~meia banda: acertar a banda exata em
    # bem mais de 70% seria sorte da semente, não mérito do método.
    assert exatos >= 0.62 * 200, exatos
    assert perto >= 0.97 * 200, perto


def test_treino_diario_reconhece_quem_melhorou():
    """Subiu para B2 e o treino ainda cobra B1. O antigo travava em B1."""
    rng = random.Random(3)
    novo = antigo = 0
    for _ in range(200):
        respostas = _treino_fixo(P.dificuldade("B2"), 60, rng, "B1")
        novo += P.estimar(respostas).nivel == "B2"
        antigo += _metodo_antigo(respostas) == "B2"
    assert novo >= 0.85 * 200, novo
    assert antigo <= 0.05 * 200, antigo


def test_resposta_antiga_pesa_menos():
    """Quem errou tudo há quatro meses e acerta tudo hoje está melhor hoje."""
    velhos_erros = [
        P.Resposta("grammar", "t", "B1", False, 0.25, AGORA - timedelta(days=120))
    ] * 8
    novos_acertos = [P.Resposta("grammar", "t", "B1", True, 0.25, AGORA)] * 8
    antes = P.estimar(velhos_erros, agora=AGORA)
    depois = P.estimar(velhos_erros + novos_acertos, agora=AGORA)
    assert depois.theta > P.dificuldade("B1")
    assert depois.theta - antes.theta > 1


# --- tópicos -----------------------------------------------------------------


def test_nota_do_topico_e_suavizada():
    assert P.Topico("t", respostas=1, acertos=1).nota == 67
    assert P.Topico("t", respostas=1, acertos=0).nota == 33
    assert P.Topico("t", respostas=10, acertos=10).nota == 92


@pytest.mark.parametrize(
    "historico,situacao",
    [
        ([True], "poucos_dados"),
        ([True, True, True, True, True], "dominado"),
        ([True, True, True, True, False], "reforcar"),  # errou a última
        ([False, False, True], "reforcar"),
        ([True, False, True, True], "progredindo"),
    ],
)
def test_situacao_do_topico(historico, situacao):
    topico = P.Topico("t", respostas=len(historico), acertos=sum(historico), recentes=historico)
    assert topico.situacao == situacao


def test_topicos_vem_do_mais_fraco_ao_mais_firme():
    respostas = []
    for i in range(5):
        respostas.append(
            P.Resposta("grammar", "present perfect", "B1", True, 0.25, AGORA + timedelta(minutes=i))
        )
    for i in range(3):
        respostas.append(
            P.Resposta("grammar", "preposições", "B1", False, 0.25, AGORA + timedelta(minutes=i))
        )
    nomes = [t.topic for t in P.topicos(respostas)]
    assert nomes == ["preposições", "present perfect"]


def test_quadro_separa_por_habilidade_e_parte_do_nivel_geral():
    respostas = [P.Resposta("reading", "e-mails", "C1", True, 0.25)] * 12 + [
        P.Resposta("listening", "reuniões", "C1", True, 0.25)
    ]
    quadro = P.quadro(respostas, ["reading", "listening", "writing"])
    por_habilidade = {s["skill"]: s for s in quadro["skills"]}
    # Uma resposta só em listening parte do nível geral (alto), não de B1.
    assert por_habilidade["listening"]["theta"] > P.dificuldade("B1")
    assert por_habilidade["writing"]["level"] is None
    assert por_habilidade["reading"]["topics"][0]["topic"] == "e-mails"
