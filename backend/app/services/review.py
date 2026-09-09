"""Reciclagem do erro e a escada de dificuldade.

Duas regras, e as duas nascem da mesma ideia: o que a pessoa errou é a única
coisa que o sistema sabe com certeza que ela não domina.

## 1. Errou, volta — reescrito

Uma questão errada vira um item em `pathr_review_item`, vencendo HOJE. A
próxima geração de quiz sobre aquela tag recebe o conceito e a instrução de
perguntar de novo com outra escrita, outro exemplo, outro ângulo. Repetir o
enunciado testaria memória da frase; reescrever testa a ideia, que é o que
importa. Acertar a versão reescrita empurra o item para frente pelo SM-2, e
depois de algumas repetições ele para de aparecer. Errar de novo zera a
contagem e ele volta hoje.

O agrupamento é por CONCEITO, não por questão — é o que o docstring de
`PathrReviewItem` já pedia. Como a reciclagem reescreve o enunciado de
propósito, agrupar pelo texto criaria um item novo a cada reformulação e a
pessoa responderia a mesma lacuna cinco vezes em paralelo.

## 2. Acertou, aperta

A dificuldade do próximo quiz sai da evidência acumulada: o nível da tag mais
as notas recentes. Mas com um freio — quem tem erros antigos pendentes não
recebe questão mais difícil. Subir o nível de alguém que ainda deve as lacunas
anteriores é como aumentar a carga de quem não terminou a série: parece
progresso e não é.

## Por que o SM-2 mora aqui

Ele já existia, escrito à mão dentro de `routers/english.py` para os cartões de
vocabulário. Um segundo SM-2 para o quiz seriam duas cópias do mesmo algoritmo
em arquivos diferentes — que divergem na primeira correção que alguém fizer só
de um lado. As duas tabelas (`pathr_english_vocab` e `pathr_review_item`)
carregam exatamente os mesmos campos, então a mesma função serve às duas.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Piso do E-Factor no SM-2 original. Abaixo disto o intervalo praticamente não
# cresce e o item vira ruído diário.
_EASE_FLOOR = 1.3
# Teto que o SM-2 original não tem. Sem ele, uma sequência longa de acertos faz
# o intervalo explodir (o ease sobe, e o intervalo é multiplicado por ele) e um
# conceito volta a aparecer daqui a anos — tarde demais para um plano de
# estudos que dura meses.
_EASE_CEILING = 2.5

# Qualidade da lembrança na escala do SM-2 (0 esqueci, 5 lembrei na hora).
# O quiz só tem dois desfechos, então só dois valores importam: 5 recupera
# ease perdida em erros passados, 2 a derruba o suficiente para o conceito
# voltar denso na rotação.
QUALITY_HIT = 5
QUALITY_MISS = 2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# SM-2
# ---------------------------------------------------------------------------


def schedule(card: dict[str, Any], quality: int, now: Optional[datetime] = None) -> dict[str, Any]:
    """O próximo estado de um cartão depois de uma resposta.

    Recebe e devolve dicionário — não um modelo — porque os dois chamadores
    leem do PostgREST, que entrega dict, e porque assim a regra é testável sem
    banco nenhum.

    Devolve só os campos que mudam: quem chama faz `update` com isso. `lapses`
    entra apenas no erro, para não zerar o histórico de quem acertou.
    """
    agora = now or utcnow()
    ease = float(card.get("ease") or 2.5)
    repetitions = int(card.get("repetitions") or 0)
    interval = int(card.get("interval_days") or 0)

    if quality < 3:
        # Zera o intervalo em vez de reduzi-lo: o conceito volta HOJE, que é o
        # que "essa pergunta precisa voltar novamente" quer dizer. Um intervalo
        # de 1 dia adiaria a próxima chance para amanhã, e quem está estudando
        # agora perderia a sessão de hoje.
        proximo = {
            "ease": round(_ajusta_ease(ease, quality), 2),
            "repetitions": 0,
            "interval_days": 0,
            "lapses": int(card.get("lapses") or 0) + 1,
        }
        interval = 0
    else:
        repetitions += 1
        # 1 e 6 dias nas duas primeiras repetições são do SM-2 original; da
        # terceira em diante o intervalo passa a ser multiplicado pelo ease,
        # que é onde o algoritmo se adapta a cada pessoa e cada conceito.
        interval = 1 if repetitions == 1 else 6 if repetitions == 2 else round(interval * ease)
        proximo = {
            "ease": round(_ajusta_ease(ease, quality), 2),
            "repetitions": repetitions,
            "interval_days": interval,
        }

    proximo["due_at"] = (agora + timedelta(days=max(interval, 0))).isoformat()
    proximo["last_reviewed_at"] = agora.isoformat()
    return proximo


def _ajusta_ease(ease: float, quality: int) -> float:
    """A fórmula do E-Factor do SM-2, presa entre piso e teto.

    Com quality=5 sobe 0.1; com 2, cai 0.32. A assimetria é do algoritmo e faz
    sentido: uma falha é evidência mais forte de que o intervalo estava errado
    do que um acerto é de que estava certo.
    """
    ajustado = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return min(_EASE_CEILING, max(_EASE_FLOOR, ajustado))


# ---------------------------------------------------------------------------
# Conceito
# ---------------------------------------------------------------------------

_ESPACOS = re.compile(r"\s+")
_SIMBOLOS = re.compile(r"[^\w\s]")


def concept_key(text: Optional[str]) -> str:
    """Chave estável para agrupar o mesmo conceito escrito de formas diferentes.

    Minúsculas, sem acento e sem pontuação: "Diferença entre COPY e ADD" e
    "diferenca entre copy e add" são a mesma lacuna. Não tenta ser semântica —
    duas frases realmente diferentes sobre a mesma ideia continuam virando dois
    itens, e isso é aceitável: o custo é uma revisão a mais, não uma perdida.
    """
    if not text:
        return ""
    sem_acento = unicodedata.normalize("NFKD", text.strip().lower())
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return _ESPACOS.sub(" ", _SIMBOLOS.sub(" ", sem_acento)).strip()


# ---------------------------------------------------------------------------
# Escada de dificuldade
# ---------------------------------------------------------------------------

FACIL, MEDIO, DIFICIL = "facil", "medio", "dificil"

# Acima de quantos erros pendentes a dificuldade para de subir. Três é o ponto
# em que a lista de pendências deixa de ser um deslize e vira uma lacuna real.
_TETO_DE_PENDENCIAS = 3


def next_difficulty(
    proficiency: float,
    recent_scores: list[float],
    pending_reviews: int = 0,
) -> str:
    """A dificuldade do próximo quiz, a partir da evidência acumulada.

    `proficiency` é a média de `pathr_user_tag.proficiency` (0..5) nas tags do
    quiz; `recent_scores` são as notas das últimas tentativas; `pending_reviews`
    é quanto a pessoa ainda deve de erro antigo.

    O freio das pendências é a parte que não é óbvia: sem ele, alguém com nota
    alta e cinco conceitos pendentes receberia questão difícil, porque a média
    esconde exatamente as lacunas que a revisão está tentando fechar.
    """
    if pending_reviews >= _TETO_DE_PENDENCIAS:
        # Nunca "facil": rebaixar quem está indo bem em média seria punir pelo
        # que ela já está corrigindo. Só não deixa subir.
        return MEDIO if proficiency > 1 else FACIL

    media = sum(recent_scores) / len(recent_scores) if recent_scores else None

    if media is None:
        # Sem histórico, o currículo é a única evidência — e ele vale pouco,
        # porque é o que a pessoa escreveu sobre si. Começa no meio, exceto
        # para quem se declarou iniciante.
        return FACIL if proficiency <= 1 else MEDIO

    if media >= 80 and proficiency >= 3:
        return DIFICIL
    if media < 50 or proficiency <= 1:
        return FACIL
    return MEDIO
