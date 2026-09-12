"""O treino diário de idioma: o que praticar hoje, em que formato, e como corrigir.

Funções puras — sem banco, sem IA. O router (routers/language_practice.py)
busca o estado, pede os itens ao modelo e grava; aqui mora a regra, que é o
que precisa ser testável e é o que erra em silêncio.

## Por que o treino é montado assim

Cada escolha abaixo vem de um método com evidência, e não de gosto:

- **Recuperação ativa.** Todo exercício pede para a pessoa PRODUZIR ou
  RECONHECER, nunca para reler. Buscar a resposta na memória é o que fixa;
  reler dá a sensação de saber sem o saber.
- **Repetição espaçada (SM-2).** O que venceu na fila de pontos de melhora
  entra primeiro. É a mesma fila e o mesmo algoritmo do quiz técnico.
- **Entrada compreensível, i+1 (Krashen).** O grosso fica no nível da pessoa
  naquela habilidade, e uma parte fica uma banda acima — difícil o bastante
  para esticar, fácil o bastante para ainda ser entendida.
- **As quatro vertentes (Nation).** Entrada com foco no sentido (leitura,
  escuta), produção (montar frase, ditado, falar), foco na forma (lacuna,
  gramática) e fluência (associar pares do que já se sabe). Um treino só de
  múltipla escolha treina uma vertente e meia.
- **Intercalação.** Habilidades e formatos se alternam; dois exercícios
  seguidos nunca têm o mesmo formato. Treino em bloco rende mais na hora e
  menos uma semana depois.
- **Codificação dupla.** Vocabulário concreto vem com imagem: palavra e
  figura juntas se fixam melhor que a palavra sozinha.
- **Feedback corretivo imediato, explicado.** Cada resposta é corrigida na
  hora, com o porquê em português — ao contrário do quiz técnico, que corrige
  no fim: em idioma, o erro não corrigido na hora vira hábito.
- **Do reconhecer ao produzir.** Um ponto de melhora não volta sempre igual.
  Na primeira vez que volta, a pessoa reconhece a forma certa entre
  alternativas; acertando, na seguinte completa a lacuna; depois monta a frase;
  por fim escreve de ouvido ou diz em voz alta. É isso que "lapidar" quer dizer
  aqui: cada acerto troca por um formato que exige mais. Errar volta um degrau.

## Imagens

As imagens são emoji, e não fotos. É uma escolha, não uma limitação
escondida: emoji desenha em qualquer aparelho, sem rede, sem chave de API,
sem direito autoral e sem imagem quebrada (o defeito que acabou de sair do
leitor de artigos). O custo é que só serve para vocabulário concreto — "maçã",
"reunião", "notebook" — e é só para esse que o prompt o pede.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

from app.services import proficiencia_idioma as P
from app.services import review

TIPOS = ("mcq", "gap", "reorder", "match", "listening", "dictation", "image", "speaking")

# Chance de acertar sem saber. Alimenta a estimativa de nível: acertar um
# ditado diz muito mais que acertar uma alternativa entre quatro.
CHANCE = {
    "mcq": 0.25,
    "gap": 0.25,
    "image": 0.25,
    "listening": 0.25,
    # Acertar os quatro pares no chute: 1 em 24.
    "match": 0.04,
    "reorder": 0.0,
    "dictation": 0.0,
    "speaking": 0.0,
}

# Que formatos cada habilidade aceita. A ordem é a de preferência.
FORMATOS = {
    "grammar": ("gap", "reorder", "mcq"),
    "vocabulary": ("image", "match", "gap", "mcq"),
    "reading": ("mcq",),
    "listening": ("listening", "dictation"),
    "writing": ("reorder", "gap"),
    "speaking": ("speaking", "reorder"),
    "business": ("mcq", "gap"),
}

# Os formatos em ordem de exigência: reconhecer, completar, montar, produzir.
# Um ponto de melhora sobe um degrau a cada acerto (repetitions do SM-2) e
# volta ao começo quando erra, porque o SM-2 zera as repetições no erro.
DEGRAUS = (("mcq",), ("gap",), ("reorder",), ("dictation", "speaking"))

# Um vocabulário comum de tópicos por habilidade. O modelo escolhe DAQUI:
# tópico escrito livre fragmenta a contagem ("present perfect", "Present
# Perfect simple", "presente perfeito") e o placar por tópico viraria uma lista
# de cem linhas com uma resposta cada.
TOPICOS = {
    "grammar": (
        "tempos do presente", "tempos do passado", "futuro e condicionais", "verbos modais",
        "preposições", "artigos e determinantes", "pronomes", "ordem das palavras",
        "perguntas", "voz passiva", "discurso indireto", "comparativos", "conectores",
    ),
    "vocabulary": (
        "reuniões e agenda", "código e revisão", "e-mails e mensagens", "entrevistas",
        "números e datas", "falsos cognatos", "expressões e verbos frasais",
        "tecnologia e ferramentas", "rotina de escritório", "viagens e deslocamento",
    ),
    "reading": (
        "e-mails e mensagens", "documentação técnica", "artigos e notícias",
        "contratos e políticas",
    ),
    "listening": (
        "reuniões diárias", "números e datas", "instruções", "conversas informais",
        "apresentações",
    ),
    "writing": (
        "e-mails formais", "mensagens curtas", "relatórios e tickets",
        "pontuação e ortografia",
    ),
    "speaking": ("pronúncia", "apresentação pessoal", "reuniões", "entrevistas"),
    "business": ("negociação", "prazos e escopo", "feedback", "apresentações"),
}

# Um exercício a cada ~75 segundos, contando ler a explicação.
_SEGUNDOS_POR_EXERCICIO = 75
_MINIMO = 8
_MAXIMO = 20

_FRACAO_REVISAO = 0.4
_FRACAO_REFORCO = 0.4


@dataclass
class Encomenda:
    """Um exercício a gerar: o que o modelo precisa saber para escrevê-lo."""

    indice: int
    tipo: str
    habilidade: str
    topico: str
    banda: str
    origem: str  # revisao | reforco | novo
    ponto_id: Optional[str] = None
    # O que a pessoa errou, para ser cobrado de novo COM OUTRAS PALAVRAS.
    lembrete: Optional[str] = None

    def para_json(self) -> dict[str, Any]:
        return {
            "indice": self.indice,
            "tipo": self.tipo,
            "habilidade": self.habilidade,
            "topico": self.topico,
            "banda": self.banda,
            "origem": self.origem,
            "ponto_id": self.ponto_id,
            "lembrete": self.lembrete,
        }

    @classmethod
    def de_json(cls, dado: dict[str, Any]) -> "Encomenda":
        return cls(
            indice=int(dado["indice"]),
            tipo=str(dado["tipo"]),
            habilidade=str(dado["habilidade"]),
            topico=str(dado["topico"]),
            banda=str(dado["banda"]),
            origem=str(dado["origem"]),
            ponto_id=dado.get("ponto_id"),
            lembrete=dado.get("lembrete"),
        )


def quantos_exercicios(minutos_por_dia: int) -> int:
    segundos = max(minutos_por_dia, 1) * 60
    return max(_MINIMO, min(_MAXIMO, round(segundos / _SEGUNDOS_POR_EXERCICIO)))


def formato_do_ponto(repeticoes: int, habilidade: str, rng: random.Random) -> str:
    """O degrau de exigência em que um ponto de melhora volta.

    Se o degrau não combina com a habilidade (ditado para "leitura"), usa o
    mais exigente que ela aceita até aquele degrau — nunca um mais fácil que
    o necessário.
    """
    aceitos = FORMATOS.get(habilidade, ("mcq",))
    degrau = min(max(repeticoes, 0), len(DEGRAUS) - 1)
    for nivel in range(degrau, -1, -1):
        candidatos = [tipo for tipo in DEGRAUS[nivel] if tipo in aceitos]
        if candidatos:
            return rng.choice(candidatos)
    return aceitos[0]


def _formato_equilibrado(habilidade: str, usados: list[Encomenda], rng: random.Random) -> str:
    """O formato da habilidade que menos apareceu no treino até aqui.

    Sorteio puro entre os formatos deixava o treino com 60% de múltipla
    escolha — as revisões recém-criadas começam nela, e leitura e corporativo
    quase só têm ela. Um treino assim treina reconhecimento e quase nada de
    produção, e nenhuma intercalação separa doze exercícios iguais em vinte.
    """
    contagem: dict[str, int] = {}
    for encomenda in usados:
        contagem[encomenda.tipo] = contagem.get(encomenda.tipo, 0) + 1
    aceitos = list(FORMATOS[habilidade])
    rng.shuffle(aceitos)
    return min(aceitos, key=lambda tipo: contagem.get(tipo, 0))


def _banda_da_habilidade(quadro: dict[str, Any], habilidade: str) -> str:
    for linha in quadro.get("skills", []):
        if linha["skill"] == habilidade and linha.get("level"):
            return linha["level"]
    return quadro.get("overall", {}).get("level") or "B1"


def _uma_acima(banda: str) -> str:
    return P.BANDAS[min(P.indice_da_banda(banda) + 1, len(P.BANDAS) - 1)]


def montar(
    quadro: dict[str, Any],
    pontos_vencidos: list[dict[str, Any]],
    minutos_por_dia: int,
    semente: int = 0,
) -> list[Encomenda]:
    """O treino de hoje: revisão do que venceu, reforço do fraco, e algo novo.

    Determinístico pela semente (o dia), para que duas chamadas no mesmo dia
    montem o mesmo treino — gerar outro no meio da sessão trocaria os
    exercícios de quem saiu e voltou.
    """
    rng = random.Random(semente)
    total = quantos_exercicios(minutos_por_dia)
    encomendas: list[Encomenda] = []

    # 1. Revisão: os pontos de melhora vencidos, o mais atrasado primeiro.
    for ponto in pontos_vencidos[: round(total * _FRACAO_REVISAO)]:
        habilidade = ponto.get("skill") if ponto.get("skill") in FORMATOS else "grammar"
        encomendas.append(
            Encomenda(
                indice=0,
                tipo=formato_do_ponto(int(ponto.get("repetitions") or 0), habilidade, rng),
                habilidade=habilidade,
                # "geral" e não o primeiro tópico do catálogo: ponto gravado
                # antes de existir tópico voltava rotulado "tempos do
                # presente" sem ter nada a ver com isso, e somava no placar
                # errado. Com "geral", o tópico sai do que o modelo reconhecer.
                topico=ponto.get("topic") or "geral",
                banda=ponto.get("band") or _banda_da_habilidade(quadro, habilidade),
                origem="revisao",
                ponto_id=str(ponto["id"]),
                lembrete=f"{ponto.get('front') or ''}\n→ {ponto.get('back') or ''}".strip()[:600],
            )
        )

    # 2. Reforço: os tópicos a reforçar, do de nota mais baixa para cima.
    fracos: list[tuple[float, str, str]] = []
    for linha in quadro.get("skills", []):
        for topico in linha.get("topics", []):
            if topico["status"] == "reforcar":
                fracos.append((topico["score"], linha["skill"], topico["topic"]))
    fracos.sort()
    vagas_reforco = round(total * _FRACAO_REFORCO)
    ja = {(e.habilidade, e.topico) for e in encomendas}
    for _, habilidade, topico in fracos:
        if vagas_reforco <= 0:
            break
        if habilidade not in FORMATOS or (habilidade, topico) in ja:
            continue
        encomendas.append(
            Encomenda(0, _formato_equilibrado(habilidade, encomendas, rng), habilidade, topico,
                      _banda_da_habilidade(quadro, habilidade), "reforco")
        )
        ja.add((habilidade, topico))
        vagas_reforco -= 1

    # 3. Novo: o resto, começando pelas habilidades MENOS praticadas — quem
    #    nunca treinou escuta precisa de escuta antes de mais gramática.
    praticadas = {linha["skill"]: linha.get("answered", 0) for linha in quadro.get("skills", [])}
    habilidades = sorted(FORMATOS, key=lambda h: (praticadas.get(h, 0), rng.random()))
    i = 0
    while len(encomendas) < total:
        habilidade = habilidades[i % len(habilidades)]
        banda = _banda_da_habilidade(quadro, habilidade)
        # Um em cada três novos fica uma banda acima: o i+1.
        if i % 3 == 2:
            banda = _uma_acima(banda)
        encomendas.append(
            Encomenda(0, _formato_equilibrado(habilidade, encomendas, rng), habilidade,
                      rng.choice(TOPICOS[habilidade]), banda, "novo")
        )
        i += 1

    ordenadas = intercalar(encomendas[:total], rng)
    for posicao, encomenda in enumerate(ordenadas):
        encomenda.indice = posicao
    return ordenadas


def intercalar(encomendas: list[Encomenda], rng: random.Random) -> list[Encomenda]:
    """Revisão espalhada em intervalos regulares, e nunca dois formatos iguais seguidos.

    As posições das revisões são fixadas primeiro — 0, n/k, 2n/k… — e o resto
    preenche os vãos. A versão anterior só "adiava a próxima revisão", o que a
    empurrava inteira para o FIM: o teste flagrou quatro "reconheça a forma
    certa" seguidos na última parte do treino, justamente onde a atenção já
    caiu. Começar por uma revisão aquece com o que a pessoa já viu.
    """
    revisoes = [e for e in encomendas if e.origem == "revisao"]
    demais = [e for e in encomendas if e.origem != "revisao"]
    rng.shuffle(revisoes)
    rng.shuffle(demais)
    total = len(encomendas)
    vagas_de_revisao = (
        {round(i * total / len(revisoes)) for i in range(len(revisoes))} if revisoes else set()
    )

    # 1. As revisões ocupam as vagas delas, sem exceção. Ceder a vaga quando o
    #    formato repetia foi o que as amontoava no fim na tentativa anterior.
    fila: list[Optional[Encomenda]] = [None] * total
    for vaga in sorted(vagas_de_revisao):
        fila[vaga] = revisoes.pop()
    sobra = revisoes  # só sobra se duas vagas arredondaram para a mesma

    # 2. O resto preenche os vãos olhando os DOIS vizinhos: o de antes já está
    #    decidido, e o de depois pode ser uma revisão já fixada.
    #    Entre os que servem, vai o formato que MAIS sobrou: gastar primeiro o
    #    abundante é o que evita chegar ao fim só com três lacunas para três
    #    posições seguidas (o que o guloso simples fazia).
    pendentes = demais + sobra
    for posicao in range(total):
        if fila[posicao] is not None:
            continue
        antes = fila[posicao - 1].tipo if posicao > 0 and fila[posicao - 1] else None
        depois = fila[posicao + 1].tipo if posicao + 1 < total and fila[posicao + 1] else None
        restam: dict[str, int] = {}
        for encomenda in pendentes:
            restam[encomenda.tipo] = restam.get(encomenda.tipo, 0) + 1
        mais_sobrou = sorted(pendentes, key=lambda e: -restam[e.tipo])
        escolha = (
            next((e for e in mais_sobrou if e.tipo not in (antes, depois)), None)
            or next((e for e in mais_sobrou if e.tipo != antes), None)
            or mais_sobrou[0]
        )
        pendentes.remove(escolha)
        fila[posicao] = escolha
    return [e for e in fila if e is not None]


# ---------------------------------------------------------------------------
# Tópico canônico
# ---------------------------------------------------------------------------


def canonico(topico: Optional[str], habilidade: str, pedido: str) -> str:
    """O tópico do catálogo igual ao que o modelo escreveu, ou o pedido.

    Se não reconhecer, fica com o que foi PEDIDO para aquele exercício — nunca
    com um texto livre, que abriria uma linha nova no placar.
    """
    chave = review.concept_key(topico)
    for candidato in TOPICOS.get(habilidade, ()):
        if review.concept_key(candidato) == chave:
            return candidato
    return pedido


# ---------------------------------------------------------------------------
# Validação do que o modelo escreveu
# ---------------------------------------------------------------------------

LACUNA = "___"
_TEM_LETRA_OU_DIGITO = re.compile(r"[A-Za-z0-9]")
_FALA = re.compile(r"^[^\n:]{1,40}:\s*\S", re.MULTILINE)


def _palavras(texto: str) -> list[str]:
    return [p for p in texto.split() if p.strip()]


def _alternativas(item: dict[str, Any]) -> Optional[tuple[list[str], int]]:
    opcoes = [str(o).strip() for o in (item.get("alternativas") or []) if str(o).strip()]
    try:
        correta = int(item.get("correta"))
    except (TypeError, ValueError):
        return None
    if len(opcoes) != 4 or len({o.lower() for o in opcoes}) != 4 or not 0 <= correta <= 3:
        return None
    return opcoes, correta


def validar(item: dict[str, Any], encomenda: Encomenda) -> Optional[dict[str, Any]]:
    """O exercício pronto para gravar, ou None se não servir.

    Devolve `payload` (o que a tela mostra) e `gabarito` (o que só o servidor
    vê) separados: mandar o gabarito junto ao navegador deixaria a resposta a
    um F12 de distância.
    """
    tipo = encomenda.tipo
    enunciado = str(item.get("enunciado") or "").strip()
    explicacao = str(item.get("explicacao") or "").strip()
    if not explicacao:
        return None
    payload: dict[str, Any] = {"enunciado": enunciado[:600]}
    gabarito: dict[str, Any] = {}

    if tipo in ("mcq", "gap", "image", "listening"):
        par = _alternativas(item)
        if not par or not enunciado:
            return None
        opcoes, correta = par
        payload["alternativas"] = opcoes
        gabarito["indice"] = correta
        if tipo == "gap":
            frase = str(item.get("frase") or "").strip()
            if frase.count(LACUNA) != 1:
                return None
            payload["frase"] = frase[:400]
        if tipo == "image":
            emoji = str(item.get("emoji") or "").strip()
            # Um emoji é curto e não tem letra nem dígito. Texto no lugar da
            # imagem ("apple") entregaria a resposta.
            if not emoji or len(emoji) > 8 or _TEM_LETRA_OU_DIGITO.search(emoji):
                return None
            payload["emoji"] = emoji
        if tipo == "listening":
            audio = str(item.get("texto") or "").strip()
            if len(_palavras(audio)) < 3:
                return None
            # O texto falado vai ao navegador: é o que a síntese de voz lê.
            # A tela o esconde até a pessoa pedir a transcrição.
            payload["audio"] = audio[:800]
            payload["dialogo"] = len(_FALA.findall(audio)) >= 2

    elif tipo == "reorder":
        frase = " ".join(_palavras(str(item.get("frase") or "")))
        pedacos = _palavras(frase)
        if not 3 <= len(pedacos) <= 14:
            return None
        aceitas = [frase] + [
            " ".join(_palavras(str(a))) for a in (item.get("aceitas") or []) if str(a).strip()
        ]
        embaralhadas = pedacos[:]
        rng = random.Random(frase)
        for _ in range(10):
            rng.shuffle(embaralhadas)
            if embaralhadas != pedacos:
                break
        payload["pecas"] = embaralhadas
        payload["traducao"] = str(item.get("traducao") or "").strip()[:300]
        gabarito["frases"] = aceitas[:4]

    elif tipo == "match":
        pares = []
        for par in item.get("pares") or []:
            if isinstance(par, dict):
                a, b = str(par.get("a") or "").strip(), str(par.get("b") or "").strip()
                if a and b:
                    pares.append((a, b))
        esquerdas = {a.lower() for a, _ in pares}
        direitas = {b.lower() for _, b in pares}
        if not 4 <= len(pares) <= 6 or len(esquerdas) != len(pares) or len(direitas) != len(pares):
            return None
        ordem = list(range(len(pares)))
        rng = random.Random("|".join(a for a, _ in pares))
        for _ in range(10):
            rng.shuffle(ordem)
            if ordem != sorted(ordem):
                break
        payload["esquerda"] = [a for a, _ in pares]
        payload["direita"] = [pares[i][1] for i in ordem]
        # posição à esquerda -> posição, na coluna embaralhada, do par dela
        gabarito["pares"] = {str(i): ordem.index(i) for i in range(len(pares))}

    elif tipo in ("dictation", "speaking"):
        texto = " ".join(_palavras(str(item.get("texto") or "")))
        if not 3 <= len(_palavras(texto)) <= 20:
            return None
        gabarito["texto"] = texto
        payload["traducao"] = str(item.get("traducao") or "").strip()[:300]
        if tipo == "speaking":
            # Na fala a pessoa LÊ a frase em voz alta: precisa ver o texto.
            payload["texto"] = texto
        else:
            # No ditado ela OUVE e escreve: o texto vai só para a síntese de
            # voz, e a tela não o mostra até a correção.
            payload["audio"] = texto
    else:
        return None

    return {
        "payload": payload,
        "gabarito": gabarito,
        "explicacao": explicacao[:1500],
        "topico": canonico(item.get("topico"), encomenda.habilidade, encomenda.topico),
    }


# ---------------------------------------------------------------------------
# Correção
# ---------------------------------------------------------------------------

_PONTUACAO = re.compile(r"[^\w\s']", re.UNICODE)

# O ditado exige quase tudo; a fala, menos, porque o reconhecimento de voz do
# navegador erra sozinho — cobrar 90% ali reprovaria pronúncia boa por culpa
# do microfone.
LIMIAR_DITADO = 0.9
LIMIAR_FALA = 0.75


def normalizar(texto: str, *, sem_acento: bool = False) -> str:
    texto = unicodedata.normalize("NFKC", texto or "").lower().replace("’", "'")
    if sem_acento:
        texto = "".join(
            c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
        )
    return " ".join(_PONTUACAO.sub(" ", texto).split())


def semelhanca(esperado: str, dito: str, *, sem_acento: bool = False) -> float:
    """Semelhança por PALAVRA, de 0 a 1.

    Por palavra e não por letra: no ditado, "their" no lugar de "there" é um
    erro inteiro, e medir por letras daria 80% a uma palavra errada.
    """
    a = normalizar(esperado, sem_acento=sem_acento).split()
    b = normalizar(dito, sem_acento=sem_acento).split()
    if not a:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _palavras_que_faltaram(esperado: str, dito: str) -> list[str]:
    a = normalizar(esperado).split()
    b = normalizar(dito).split()
    faltas: list[str] = []
    for operacao, i1, i2, _, _ in SequenceMatcher(None, a, b).get_opcodes():
        if operacao != "equal":
            faltas.extend(a[i1:i2])
    return faltas[:12]


@dataclass
class Correcao:
    acertou: bool
    # Fala sem resposta = navegador sem microfone ou pessoa que pulou. Não é
    # erro: não entra na estimativa e não vira ponto de melhora.
    pulado: bool = False
    detalhe: Optional[dict[str, Any]] = None
    certa: Optional[Any] = None


def corrigir(
    tipo: str, gabarito: dict[str, Any], payload: dict[str, Any], resposta: dict[str, Any]
) -> Correcao:
    if tipo in ("mcq", "gap", "image", "listening"):
        certa = payload["alternativas"][gabarito["indice"]]
        try:
            escolhida = int(resposta.get("indice"))
        except (TypeError, ValueError):
            return Correcao(False, certa=certa)
        return Correcao(escolhida == gabarito["indice"], certa=certa)

    if tipo == "reorder":
        montada = " ".join(str(t) for t in (resposta.get("tokens") or []))
        acertou = any(normalizar(montada) == normalizar(f) for f in gabarito["frases"])
        return Correcao(acertou, certa=gabarito["frases"][0])

    if tipo == "match":
        dada: dict[str, int] = {}
        for chave, valor in (resposta.get("pares") or {}).items():
            try:
                dada[str(chave)] = int(valor)
            except (TypeError, ValueError):
                continue
        certos = sum(1 for k, v in gabarito["pares"].items() if dada.get(k) == v)
        return Correcao(
            certos == len(gabarito["pares"]),
            detalhe={"certos": certos, "total": len(gabarito["pares"])},
            certa=gabarito["pares"],
        )

    if tipo in ("dictation", "speaking"):
        dito = str(resposta.get("texto") or "")
        esperado = gabarito["texto"]
        if tipo == "speaking" and not dito.strip():
            return Correcao(False, pulado=True, certa=esperado)
        limiar = LIMIAR_DITADO if tipo == "dictation" else LIMIAR_FALA
        exata = semelhanca(esperado, dito)
        acertou = exata >= limiar
        detalhe: dict[str, Any] = {
            "semelhanca": round(exata, 2),
            "faltaram": _palavras_que_faltaram(esperado, dito),
        }
        # Tudo certo menos os acentos: conta como acerto, e avisa. Quem
        # escreve de ouvido num teclado brasileiro para francês não deveria
        # perder o exercício por um "é" sem acento — mas precisa saber.
        if not acertou and semelhanca(esperado, dito, sem_acento=True) >= limiar:
            acertou = True
            detalhe["acentos"] = True
        return Correcao(acertou, detalhe=detalhe, certa=esperado)

    return Correcao(False)


# A partir desta fração das palavras de um trecho do exercício aparecendo, em
# sequência, no erro original, o exercício está reaproveitando o erro.
LIMIAR_REPETICAO = 0.75
# Trecho mais curto que isto não conta: "in", "on", "at" aparecem em qualquer
# frase, e acusá-los de cópia recusaria toda revisão de preposição.
_PALAVRAS_MINIMAS = 4


def _contido(trecho: str, referencia: str) -> float:
    """Quanto do trecho aparece, em sequência, dentro da referência (0 a 1).

    Contenção e não semelhança: a resposta certa do erro ("Looking forward to
    seeing you") some dentro da referência longa, que traz também a
    explicação — medida por semelhança ela passaria; por contenção, não.
    """
    a = normalizar(trecho).split()
    b = normalizar(referencia).split()
    if not a or not b:
        return 0.0
    blocos = SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    return sum(bloco.size for bloco in blocos) / len(a)


def repete_o_erro(item: dict[str, Any], lembrete: Optional[str]) -> bool:
    """O exercício de revisão reaproveitou o CONTEÚDO do que a pessoa errou?

    O prompt pede situação nova, e o modelo não obedeceu em duas gerações
    reais: o erro "We discussed ABOUT the deadline in the meeting" voltou como
    "We discussed the deadline in the meeting"; e em produção, a pergunta
    "Choose the best closing sentence for your email" voltou com as mesmas
    alternativas ("Looking forward to see/seeing you"). Assim basta decorar a
    resposta, e o ponto de melhora deixa de medir se a regra foi aprendida.

    Compara só o conteúdo — frase, texto, alternativas, pares —, e NÃO o
    enunciado: "Choose the best option" se repete legitimamente entre
    exercícios diferentes, e compará-lo recusava revisões boas.
    """
    if not lembrete:
        return False
    candidatos = [str(item.get(campo) or "") for campo in ("frase", "texto")]
    candidatos += [str(a) for a in (item.get("alternativas") or [])]
    for par in item.get("pares") or []:
        if isinstance(par, dict):
            candidatos.append(f"{par.get('a') or ''} {par.get('b') or ''}")
    return any(
        len(normalizar(candidato).split()) >= _PALAVRAS_MINIMAS
        and _contido(candidato, lembrete) >= LIMIAR_REPETICAO
        for candidato in candidatos
    )


def respostas_para_estimativa(linhas: Iterable[dict[str, Any]]) -> list[P.Resposta]:
    """Linhas respondidas de `pathr_english_item` → respostas do estimador."""
    saida = []
    for linha in linhas:
        if linha.get("is_correct") is None or linha.get("skipped"):
            continue
        quando = None
        if linha.get("answered_at"):
            try:
                quando = datetime.fromisoformat(str(linha["answered_at"]).replace("Z", "+00:00"))
            except ValueError:
                quando = None
        saida.append(
            P.Resposta(
                skill=str(linha.get("skill") or "grammar"),
                topic=str(linha.get("topic") or "geral"),
                band=str(linha.get("cefr_band") or "B1"),
                correct=bool(linha.get("is_correct")),
                chance=CHANCE.get(str(linha.get("type") or "mcq"), 0.25),
                answered_at=quando,
            )
        )
    return saida
