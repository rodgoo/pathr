"""O nível de idioma por habilidade, e como a pessoa vai em cada tópico.

## O que estava errado

O "Por habilidade" mostrava a PORCENTAGEM de acerto de cada habilidade, e a
tela a desenhava como se fosse nível. Com os dados reais da conta: 100% em
"Corporativo" saiu de duas perguntas, 33% em "Vocabulário" de três. Três
defeitos, todos de medida:

1. **Porcentagem não é nível.** Acertar 3 de 3 itens A2 e acertar 3 de 3
   itens C1 davam o mesmo 100%. O próprio nivelamento já sabia disso para a
   nota geral ("acertar 90% de itens A2 não faz ninguém B2") e esqueceu na
   quebra por habilidade.
2. **Chute não era descontado.** Numa múltipla escolha de quatro alternativas,
   25% de acerto é o que se tira sem ler a pergunta.
3. **Amostra pequena parecia certeza.** Vinte itens em sete habilidades dão
   menos de três por habilidade, e a tela mostrava o resultado com a mesma
   firmeza de um teste de cem.

## O que se faz agora

A estimativa é a de um teste adaptativo de verdade (TRI, modelo de três
parâmetros): a chance de acertar um item depende da distância entre o nível
da pessoa e o nível do item, e nunca cai abaixo da chance de chute. Em vez de
uma conta sobre a porcentagem, procura-se o nível que torna as respostas que
aconteceram mais prováveis — acertar itens difíceis puxa para cima, errar
itens fáceis puxa para baixo, e um acerto que podia ser chute pesa menos.

A saída é uma distribuição, não um número: a média é o nível estimado e o
desvio é a INCERTEZA. Com três respostas o desvio é grande e a tela diz
"estimativa inicial"; é o que impede dois acertos de virarem "100%".

## Progresso contínuo

Resposta antiga pesa menos (meia-vida de 30 dias). Sem isso, quem estudou
dois meses carregaria para sempre os erros do primeiro dia, e o nível não
subiria nunca por mais que a pessoa melhorasse — que é o contrário do que o
treino diário existe para mostrar.

## A escala

Uma unidade por banda CEFR: A1 vai de 0 a 1, A2 de 1 a 2 … C2 de 5 a 6. Um item
de banda B1 tem dificuldade 2,5, o centro da faixa. Assim o nível lê direto da
parte inteira, e a parte fracionária é "quanto já andou dentro da banda".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

BANDAS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Quanto um degrau de banda separa quem acerta de quem erra. Com 1,7, alguém
# uma banda acima do item acerta ~85% (fora o chute), duas bandas acima ~97%.
# É o valor clássico que aproxima a curva logística da normal na TRI.
_DISCRIMINACAO = 1.7

# A grade onde a distribuição é calculada: de 0 a 6, de 0,05 em 0,05.
_PASSOS = 121
_GRADE = [6.0 * i / (_PASSOS - 1) for i in range(_PASSOS)]

# Sem resposta nenhuma, a estimativa parte de B1 com incerteza larga — não é
# um palpite sobre a pessoa, é o meio da escala. Quando há nivelamento, o
# ponto de partida vira o nível medido nele.
#
# O desvio foi escolhido por simulação, e não por gosto: com 1,25, alunos C1
# com três respostas saíam como C1 em 0% das vezes (o ponto de partida em B1
# puxava tudo para o meio, viés de -1,06 banda). Com 1,6, 56% e viés de -0,84;
# com vinte respostas, 72% e -0,18. Mais largo que isso quase não melhora o
# viés e deixa a estimativa inicial nervosa.
_CENTRO_PADRAO = 2.5
_DESVIO_INICIAL = 1.6

_MEIA_VIDA_DIAS = 30.0

# Abaixo destes desvios a estimativa é firme o bastante para o rótulo dizer.
_DESVIO_ALTA = 0.35
_DESVIO_MEDIA = 0.6

# Tópico: com menos de tantas respostas não há o que afirmar.
_MINIMO_TOPICO = 2
_JANELA_RECENTE = 5


@dataclass(frozen=True)
class Resposta:
    skill: str
    topic: str
    band: str
    correct: bool
    # Chance de acertar sem saber: 1/4 numa múltipla escolha de quatro, zero
    # num ditado ou numa frase montada. É o que separa acerto de chute.
    chance: float = 0.25
    answered_at: Optional[datetime] = None


@dataclass
class Estimativa:
    nivel: str
    theta: float
    desvio: float
    respostas: int

    @property
    def dentro_da_banda(self) -> float:
        """Quanto já andou dentro da banda, de 0 a 1."""
        return round(min(max(self.theta - math.floor(min(self.theta, 5.999)), 0.0), 1.0), 2)

    @property
    def confianca(self) -> str:
        if self.respostas == 0:
            return "sem_dados"
        if self.desvio <= _DESVIO_ALTA:
            return "alta"
        if self.desvio <= _DESVIO_MEDIA:
            return "media"
        return "inicial"


@dataclass
class Topico:
    topic: str
    respostas: int
    acertos: int
    recentes: list[bool] = field(default_factory=list)
    ultimo_em: Optional[datetime] = None

    @property
    def nota(self) -> int:
        """De 0 a 100, suavizada: (acertos + 1) / (respostas + 2).

        A suavização é o que impede "1 de 1" de virar 100 e "0 de 1" de virar
        zero — o mesmo defeito da quebra por habilidade, só que em tamanho
        menor.
        """
        return round(100 * (self.acertos + 1) / (self.respostas + 2))

    @property
    def situacao(self) -> str:
        if self.respostas < _MINIMO_TOPICO:
            return "poucos_dados"
        recentes = self.recentes[-_JANELA_RECENTE:]
        taxa_recente = sum(recentes) / len(recentes)
        # Errar a última vem ANTES de "dominado": é o estado de agora, e é o
        # que o treino de amanhã precisa cobrar. Na ordem inversa, quatro
        # acertos seguidos de um erro contavam como domínio — e o tópico que a
        # pessoa acabou de errar sumia do treino.
        if taxa_recente < 0.6 or not recentes[-1]:
            return "reforcar"
        if len(recentes) >= 4 and taxa_recente >= 0.8:
            return "dominado"
        return "progredindo"


def indice_da_banda(banda: Optional[str]) -> int:
    return BANDAS.index(banda) if banda in BANDAS else 2


def dificuldade(banda: Optional[str]) -> float:
    return indice_da_banda(banda) + 0.5


def banda_do_theta(theta: float) -> str:
    return BANDAS[max(0, min(len(BANDAS) - 1, math.floor(theta)))]


def probabilidade_de_acerto(theta: float, banda: str, chance: float) -> float:
    """Três parâmetros: dificuldade (banda), discriminação e chute."""
    chance = min(max(chance, 0.0), 0.95)
    logistica = 1.0 / (1.0 + math.exp(-_DISCRIMINACAO * (theta - dificuldade(banda))))
    return chance + (1.0 - chance) * logistica


def _peso(resposta: Resposta, agora: datetime) -> float:
    if resposta.answered_at is None:
        return 1.0
    quando = resposta.answered_at
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    dias = max((agora - quando).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (dias / _MEIA_VIDA_DIAS)


def estimar(
    respostas: Iterable[Resposta],
    *,
    centro: Optional[float] = None,
    agora: Optional[datetime] = None,
) -> Estimativa:
    """A distribuição do nível dadas as respostas, resumida em média e desvio.

    Calculada numa grade, e não por uma fórmula fechada: a grade aceita o
    peso por recência e o chute sem aproximação nenhuma, e 121 pontos custam
    nada. É a mesma pontuação EAP de testes adaptativos computadorizados.
    """
    agora = agora or datetime.now(timezone.utc)
    lista = list(respostas)
    mu = _CENTRO_PADRAO if centro is None else centro

    # Em log para não estourar com centenas de respostas multiplicadas.
    log_post = [-((t - mu) ** 2) / (2 * _DESVIO_INICIAL**2) for t in _GRADE]
    for resposta in lista:
        peso = _peso(resposta, agora)
        for i, theta in enumerate(_GRADE):
            p = probabilidade_de_acerto(theta, resposta.band, resposta.chance)
            p = min(max(p, 1e-9), 1 - 1e-9)
            log_post[i] += peso * math.log(p if resposta.correct else 1.0 - p)

    maior = max(log_post)
    pesos = [math.exp(valor - maior) for valor in log_post]
    total = sum(pesos)
    media = sum(t * w for t, w in zip(_GRADE, pesos)) / total
    variancia = sum(((t - media) ** 2) * w for t, w in zip(_GRADE, pesos)) / total

    # Não se prova um nível sem item daquele nível. Dez ditados B2 certos davam
    # C2: acertar tudo empurra a curva para o topo da escala, porque nada ali
    # contradiz. Mas o que as respostas mostram é "acima de B2", não "C2". O
    # teto é uma banda acima do item mais difícil acertado; o piso, uma banda
    # abaixo do mais fácil errado — pela mesma razão, ao contrário.
    acertados = [indice_da_banda(r.band) for r in lista if r.correct]
    errados = [indice_da_banda(r.band) for r in lista if not r.correct]
    if acertados:
        media = min(media, max(acertados) + 1.999)
    if errados:
        media = max(media, min(errados) - 1.0)
    media = min(max(media, 0.0), 5.999)
    return Estimativa(
        nivel=banda_do_theta(media),
        theta=round(media, 3),
        desvio=round(math.sqrt(variancia), 3),
        respostas=len(lista),
    )


def topicos(respostas: Iterable[Resposta]) -> list[Topico]:
    """Os tópicos de uma habilidade, do que mais precisa de reforço ao mais firme."""
    por_topico: dict[str, Topico] = {}
    ordenadas = sorted(
        respostas, key=lambda r: r.answered_at or datetime.min.replace(tzinfo=timezone.utc)
    )
    for resposta in ordenadas:
        nome = (resposta.topic or "geral").strip() or "geral"
        atual = por_topico.setdefault(nome, Topico(topic=nome, respostas=0, acertos=0))
        atual.respostas += 1
        atual.acertos += int(resposta.correct)
        atual.recentes.append(resposta.correct)
        atual.ultimo_em = resposta.answered_at or atual.ultimo_em

    ordem = {"reforcar": 0, "progredindo": 1, "poucos_dados": 2, "dominado": 3}
    return sorted(por_topico.values(), key=lambda t: (ordem[t.situacao], t.nota, -t.respostas))


def quadro(
    respostas: Iterable[Resposta],
    habilidades: Iterable[str],
    *,
    nivel_medido: Optional[str] = None,
    agora: Optional[datetime] = None,
) -> dict[str, Any]:
    """Tudo que a tela "Por habilidade" mostra, pronto para JSON.

    O ponto de partida de cada habilidade é o nível GERAL estimado com todas
    as respostas. Sem isso, uma habilidade com uma resposta só partiria de B1
    para alguém que é C1 em tudo o mais — e a estimativa inicial seria ruim
    justamente onde há menos dados.
    """
    lista = list(respostas)
    centro = dificuldade(nivel_medido) if nivel_medido in BANDAS else None
    geral = estimar(lista, centro=centro, agora=agora)

    saida = []
    for habilidade in habilidades:
        daquela = [r for r in lista if r.skill == habilidade]
        estimativa = estimar(daquela, centro=geral.theta, agora=agora)
        saida.append(
            {
                "skill": habilidade,
                "level": estimativa.nivel if daquela else None,
                "theta": estimativa.theta,
                "progress_in_band": estimativa.dentro_da_banda,
                "uncertainty": estimativa.desvio,
                "confidence": estimativa.confianca,
                "answered": estimativa.respostas,
                "topics": [
                    {
                        "topic": t.topic,
                        "answered": t.respostas,
                        "correct": t.acertos,
                        "score": t.nota,
                        "status": t.situacao,
                        "last_seen": t.ultimo_em.isoformat() if t.ultimo_em else None,
                    }
                    for t in topicos(daquela)
                ],
            }
        )
    return {
        "overall": {
            "level": geral.nivel if lista else nivel_medido,
            "theta": geral.theta,
            "progress_in_band": geral.dentro_da_banda,
            "uncertainty": geral.desvio,
            "confidence": geral.confianca,
            "answered": geral.respostas,
        },
        "skills": saida,
    }
