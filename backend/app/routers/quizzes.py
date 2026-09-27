"""Quizzes: gerar com IA, responder e realimentar o perfil.

O quiz não existe para dar nota. Ele existe porque é a única evidência real
de proficiência que o app consegue coletar — o currículo é o que a pessoa
escreveu sobre si, e concluir um módulo prova que ela estudou, não que
aprendeu. Por isso o resultado atualiza `pathr_user_tag` com confiança alta,
e é o único caminho que faz isso.

A resposta correta NUNCA vai junto com a pergunta: o cliente recebe enunciado
e alternativas, e só vê o gabarito depois de responder. Mandar tudo de uma vez
transformaria o quiz em decoração.
"""

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.services import conhecimento
from app.services.alternativas import numerar_de_um
from app.deps import get_current_user
from app.services import review
from app.services.progress import log_activity

router = APIRouter(prefix="/quizzes", tags=["quiz"])
_log_quiz = logging.getLogger("pathr.quizzes")

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "titulo": {"type": "STRING"},
        "questoes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "conceito": {"type": "STRING"},
                    "enunciado": {"type": "STRING"},
                    "codigo": {"type": "STRING"},
                    "linguagem": {"type": "STRING"},
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correta": {"type": "INTEGER"},
                    "explicacao": {"type": "STRING"},
                    # Um texto por alternativa, na ordem delas: por que está certa ou qual engano ela representa.
                    "analise": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "dificuldade": {"type": "STRING"},
                },
                "required": ["enunciado", "alternativas", "correta", "explicacao"],
            },
        },
    },
    "required": ["questoes"],
}

SYSTEM_PROMPT = """Você escreve quizzes técnicos em português do Brasil para avaliar competência real.

Regras:

1. Toda questão testa APLICAÇÃO, não memorização de definição. Prefira
   cenários (um trecho de código com um problema, uma decisão de projeto a
   tomar) a perguntas do tipo o que significa X.
2. Exatamente 4 alternativas. O campo correta é o índice de 0 a 3 (uso interno).
   Na explicação e na análise, refira-se às alternativas pelo próprio texto
   delas — NUNCA por número ou letra: a ordem é embaralhada depois de escrita.
3. As alternativas erradas precisam ser plausíveis: cada uma deve refletir um
   engano que uma pessoa real comete. Alternativa absurda entrega a resposta.
   As 4 alternativas têm o MESMO formato, o mesmo tamanho (diferença de no
   máximo 10% em caracteres) e o mesmo nível de detalhe técnico. A certa NÃO pode
   ser a mais longa, a mais específica nem a mais bem escrita: quem responde tende
   a marcar, sem perceber, a alternativa que parece mais elaborada. Dê às erradas o
   mesmo tipo de detalhe que a certa tem (nomes de comandos, termos técnicos,
   condições) e enxugue a certa se ela ficou maior. Não use "sempre", "nunca" ou
   "apenas" só nas erradas — a pessoa precisa SABER a resposta para acertar, e não
   poder deduzi-la pela forma.
4. Dois campos explicam a questão. `explicacao`: uma ou duas frases com a ideia
   central que ela testa. `analise`: um array com EXATAMENTE 4 textos, um por
   alternativa, NA MESMA ORDEM em que as alternativas foram escritas. Cada texto
   é UMA frase completa que diz por que aquela alternativa está certa — ou qual
   engano específico ela representa e por que está errada. Nunca cite o número da
   alternativa dentro do texto dela: a tela já o coloca na frente.
5. O campo codigo é opcional; quando existir, use o campo linguagem
   (java, python, javascript, sql...). Não coloque a resposta em comentário.
6. O campo dificuldade: facil, medio ou dificil. Distribua conforme o nível
   informado — não faça todas fáceis.
7. O campo conceito diz, em até 8 palavras, QUAL ideia a questão testa —
   "diferença entre COPY e ADD", "escopo de variável em closure". É o que
   permite reconhecer a mesma lacuna em perguntas escritas de formas
   diferentes, então descreva a ideia, nunca o enunciado.
8. Quando vier uma lista PARA REVISAR, escreva uma questão para cada conceito
   dela, na ordem, ANTES das questões novas. Elas cobram algo que a pessoa já
   errou, e por isso precisam ser REESCRITAS: outro enunciado, outro exemplo,
   outro ângulo de ataque. Repita o conceito, nunca a frase — quem decora o
   texto da pergunta não aprendeu a ideia. Copie o conceito tal como veio, no
   campo conceito, para o sistema reconhecê-lo.
9. Devolva EXATAMENTE a quantidade de questões pedida — nem uma a menos. Cada
   questão precisa ter as 4 alternativas e os 4 textos de `analise`.
10. Responda apenas o JSON."""

# Abaixo disto o quiz não é evidência de nada: 1 acerto em 1 questão dá 100% e sobe a proficiência da tag. É o
# mesmo piso que a rota já exige de quem pede (`question_count >= 3`).
MIN_QUESTOES = 3


class GenerateQuiz(BaseModel):
    tag_ids: list[str] = Field(default_factory=list, max_length=6)
    node_id: Optional[str] = None
    question_count: int = Field(default=6, ge=3, le=15)
    # "adaptativo" por padrão: quem chama normalmente não sabe o nível atual da
    # pessoa melhor que o histórico dela. Os três valores fixos continuam
    # aceitos para quem quiser forçar.
    difficulty: str = Field(default="adaptativo", pattern="^(facil|medio|dificil|adaptativo)$")


class SubmitAnswers(BaseModel):
    # question_id -> índice escolhido
    answers: dict[str, int]
    duration_s: int = Field(default=0, ge=0, le=7200)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    payload: GenerateQuiz,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Gera um quiz sobre as tags pedidas, calibrado pelo nível atual."""
    user_id = str(current_user["id"])
    tag_ids = payload.tag_ids
    if payload.node_id:
        # O módulo é desta pessoa? `pathr_roadmap_node` não tem `user_id` (ele pertence ao roadmap), então a
        # consulta por `id` sozinha aceitava o módulo de QUALQUER conta: o quiz nascia amarrado ao módulo alheio
        # e ainda herdava as tecnologias dele. O `node_id` é gravado no quiz, e é por ele que a aba retoma e lista
        # o histórico — não pode ser um id que a pessoa não possui.
        from app.routers.roadmap import _owned_node

        node = _owned_node(supabase, payload.node_id, user_id)
        if not tag_ids:
            tag_ids = [str(tag) for tag in (node.get("tag_ids") or [])]
    if not tag_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Informe ao menos uma tecnologia."
        )

    tags = (
        supabase.table("pathr_tag").select("id,name").in_("id", tag_ids).execute().data or []
    )
    if not tags:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tecnologia não encontrada.")
    names = [tag["name"] for tag in tags]

    levels = (
        supabase.table("pathr_user_tag")
        .select("tag_id,proficiency")
        .eq("user_id", user_id)
        .in_("tag_id", tag_ids)
        .execute()
        .data
        or []
    )
    average = (
        sum(int(row.get("proficiency") or 0) for row in levels) / len(levels) if levels else 0
    )

    # O que a pessoa ja errou nestas tags e esta vencido. Vem antes de decidir
    # a dificuldade porque a quantidade de pendencias e o freio da escada.
    pendentes = _due_reviews(supabase, user_id, tag_ids)

    dificuldade = payload.difficulty
    if dificuldade == "adaptativo":
        dificuldade = review.next_difficulty(
            proficiency=average,
            recent_scores=_recent_scores(supabase, user_id),
            pending_reviews=len(pendentes),
        )

    revisar = ""
    if pendentes:
        # So o conceito viaja para o modelo, nunca o enunciado antigo. Mandar o
        # texto original convidaria a parafrasear a frase, e o que precisa
        # voltar e a ideia -- reescrita de verdade.
        linhas_revisao = "\n".join(f"- {item['front']}" for item in pendentes)
        revisar = (
            "\nPARA REVISAR (a pessoa errou estes conceitos; reescreva cada um "
            f"com outro enunciado e outro exemplo):\n{linhas_revisao}\n"
        )

    # A base de conhecimento completa o que a fila de revisão não tem: dúvidas
    # do "Perguntar", lacunas de atividades. Dentro do mesmo teto de 4, para o
    # quiz não virar só revisão.
    ja_na_fila = {review.concept_key(item.get("front")) for item in pendentes}
    da_base = [
        item["concept"]
        for item in conhecimento.pendentes(supabase, user_id, tag_ids=tag_ids, node_id=payload.node_id, limite=6)
        if review.concept_key(item.get("concept")) not in ja_na_fila
    ][: max(0, 4 - len(pendentes))]
    if da_base:
        revisar += (
            "\nDUVIDAS E ERROS DA PESSOA (da base de conhecimento dela; escreva uma "
            "questao para cada, aplicada, e copie o tema no campo conceito):\n"
            + "\n".join(f"- {tema}" for tema in da_base)
            + "\n"
        )

    # O que a pessoa JA CONSUMIU sobre estas tags. Sem isto, o quiz perguntava
    # o assunto no abstrato e ignorava que ela tinha acabado de assistir 40
    # minutos sobre exatamente aquilo -- e a pergunta caia longe do que ela
    # estudou, que e o oposto de exercitar o que se aprendeu.
    estudado = _materiais_concluidos(supabase, user_id, tag_ids)
    ja_viu = ""
    if estudado:
        linhas_material = "\n".join(f"- {titulo}" for titulo in estudado)
        ja_viu = (
            "\nJA ESTUDOU (a pessoa concluiu estes materiais; pergunte sobre o "
            f"que eles cobrem, aplicado, e nao definicao decorada):\n{linhas_material}\n"
        )

    prompt = (
        f"TECNOLOGIAS: {', '.join(names)}\n"
        f"NIVEL ATUAL DA PESSOA: {average:.1f} de 5\n"
        f"QUANTIDADE DE QUESTOES: {payload.question_count} (devolva exatamente esta quantidade)\n"
        f"DIFICULDADE PEDIDA: {dificuldade}\n"
        f"{ja_viu}"
        f"{revisar}\n"
        "Escreva questoes que uma pessoa neste nivel consiga responder pensando, "
        "mas nao consiga responder por eliminacao."
    )
    result = await generate_json(SYSTEM_PROMPT, prompt, QUIZ_SCHEMA)
    devolvidas = result.content.get("questoes")
    questions = _sem_repetidas(_clean_questions(devolvidas))
    pedidas = payload.question_count
    if len(questions) < pedidas:
        # Antes o que sobrava da limpeza era gravado como estava: pedidas 6, aproveitada 1, e o quiz saía com UMA
        # questão — sem log, sem aviso, e com "bom resultado, a proficiência subiu" em cima de um acerto só.
        _log_quiz.warning(
            "quiz: %d de %d questões aproveitadas (o modelo devolveu %d) em %s",
            len(questions), pedidas, len(devolvidas) if isinstance(devolvidas, list) else 0, result.model,
        )
        try:
            questions = _sem_repetidas(questions + await _completar(prompt, questions, pedidas - len(questions)))
        except (AiProviderError, HTTPException):
            # Cota do dia, provedor fora do ar: o que já há vale, se for o bastante (abaixo).
            pass
    questions = questions[:pedidas]
    if len(questions) < min(MIN_QUESTOES, pedidas):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA não devolveu questões suficientes. Tente de novo.",
        )
    # Só o quiz que vai ser gravado é conferido: a certa não pode ser a maior alternativa.
    questions = await _equilibrar(questions)

    quiz = (
        supabase.table("pathr_quiz")
        .insert(
            {
                "user_id": user_id,
                "title": str(result.content.get("titulo") or f"Quiz de {names[0]}")[:200],
                "kind": "practice",
                "node_id": payload.node_id,
                "tag_ids": tag_ids,
                "difficulty": dificuldade,
                "question_count": len(questions),
                "generated_by": result.model,
            }
        )
        .execute()
        .data[0]
    )

    # De qual item pendente cada questão nasceu. O modelo devolve o conceito
    # copiado da lista PARA REVISAR, e é por ele que se reconhece a origem —
    # o enunciado não serve, porque reescrevê-lo é o objetivo.
    por_conceito = {review.concept_key(item["front"]): item["id"] for item in pendentes}

    supabase.table("pathr_question").insert(
        [
            {
                "quiz_id": quiz["id"],
                "type": "single",
                "prompt": question["enunciado"],
                "code_snippet": question["codigo"] or None,
                "code_language": question["linguagem"] or None,
                "options": question["alternativas"],
                "correct": {"index": question["correta"]},
                "explanation": question["explicacao"],
                "concept": question["conceito"] or None,
                "review_item_id": por_conceito.get(review.concept_key(question["conceito"])),
                "difficulty": question["dificuldade"],
                "tag_ids": tag_ids,
                "order_index": index,
            }
            for index, question in enumerate(questions)
        ]
    ).execute()

    return get_quiz(str(quiz["id"]), current_user, supabase)


# --- A certa não pode se denunciar -------------------------------------------
#
# Quem responde escolhe, sem perceber, a alternativa que parece mais elaborada — e um modelo de IA escreve a certa
# mais longa e mais bem explicada quase sempre, porque é a que ele "sabe". O quiz virava um teste de "qual é a
# maior", e não de conhecimento. Três defesas, da mais barata para a mais cara: o prompt pede alternativas do mesmo
# tamanho; a ordem é sorteada (a certa não fica sempre no mesmo lugar); e o que ainda sair desequilibrado é reescrito.

# Sorteio do SO (`SystemRandom`), e não `random`: a posição da certa não pode ser previsível entre quizzes.
_ALEATORIO = secrets.SystemRandom()


def _misturar(itens: list) -> None:
    """Embaralha no lugar. Função à parte para os testes poderem trocar o sorteio por uma ordem conhecida."""
    _ALEATORIO.shuffle(itens)


# "a alternativa 2", "opção B", "letra C": o texto depende da ORDEM das alternativas, e embaralhar o deixaria errado.
_CITA_ALTERNATIVA = re.compile(
    r"\b(?:alternativas?|op[cç](?:ão|ao|ões|oes)|itens?|letras?|options?|choices?)\s*\(?\s*(?:[0-9]|[A-Da-d]\b)",
    re.IGNORECASE,
)


def _embaralhar(
    options: list[str], correct: int, analise: Optional[list[str]], resumo: str
) -> tuple[list[str], int, Optional[list[str]]]:
    """Sorteia a ordem das alternativas; o gabarito e o texto de cada uma acompanham a troca.

    Se o resumo ou a análise citam uma alternativa por número/letra, a ordem fica como veio: embaralhar faria o
    texto apontar para a alternativa errada, e uma explicação que contradiz o gabarito é pior que uma certa fixa.
    """
    if any(_CITA_ALTERNATIVA.search(texto) for texto in [resumo, *(analise or [])]):
        return options, correct, analise
    ordem = list(range(len(options)))
    _misturar(ordem)
    return (
        [options[i] for i in ordem],
        ordem.index(correct),
        [analise[i] for i in ordem] if analise else None,
    )


# Quanto a certa pode passar da maior das erradas, em tamanho, antes de a questão ser reescrita.
_TOLERANCIA_DE_TAMANHO = 1.10


def _razao_de_tamanho(questao: dict[str, Any]) -> float:
    """Tamanho da certa dividido pelo da MAIOR errada. Acima de 1 ela é a mais longa."""
    alternativas, correta = questao["alternativas"], questao["correta"]
    maior_errada = max(len(t) for i, t in enumerate(alternativas) if i != correta)
    return len(alternativas[correta]) / max(maior_errada, 1)


def _destoa(questao: dict[str, Any]) -> bool:
    return _razao_de_tamanho(questao) > _TOLERANCIA_DE_TAMANHO


EQUILIBRIO_PROMPT = """Você revisa as alternativas de questões de múltipla escolha para que a resposta certa não se denuncie.

Em cada questão a alternativa CERTA ficou mais longa e mais elaborada que as erradas, e quem responde tende a marcar
justamente a que parece mais bem escrita. Reescreva as 4 alternativas de cada questão de modo que:

1. Tenham praticamente o MESMO tamanho (diferença de no máximo 10% em caracteres), o mesmo formato e o mesmo nível de
   detalhe técnico.
2. Nenhum sentido mude: a certa continua certa, e cada errada continua errada pelo MESMO engano. Não troque a resposta.
3. A certa NÃO seja a mais longa nem a mais específica. Enxugue a certa e dê às erradas o mesmo tipo de detalhe
   (nomes de comandos, termos técnicos, condições) — sem torná-las corretas.
4. Nunca cite número ou letra de alternativa nos textos.

Devolva as questões na MESMA ORDEM e a MESMA QUANTIDADE recebidas. Cada uma com `alternativas` (4 textos, na mesma
ordem em que vieram) e `analise` (4 textos, um por alternativa, na mesma ordem: uma frase dizendo por que está certa ou
errada). Responda apenas o JSON."""

EQUILIBRIO_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "questoes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "analise": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["alternativas"],
            },
        }
    },
    "required": ["questoes"],
}


async def _equilibrar(questoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reescreve, numa ÚNICA chamada, as questões em que a certa é a mais longa. As outras não são tocadas.

    Nunca piora nem derruba o quiz: se a IA falhar, devolver algo inválido ou não melhorar o tamanho, a questão
    original fica como estava. Só roda quando há questão desequilibrada, e conta uma vez na cota diária de IA.
    """
    indices = [i for i, q in enumerate(questoes) if _destoa(q)]
    if not indices:
        return questoes
    blocos = []
    for n, i in enumerate(indices, 1):
        q = questoes[i]
        alternativas = "\n".join(f"{k + 1}. {texto}" for k, texto in enumerate(q["alternativas"]))
        blocos.append(f"QUESTAO {n}\nEnunciado: {q['enunciado']}\nAlternativas:\n{alternativas}\nCORRETA: {q['correta'] + 1}\n")
    try:
        resultado = await generate_json(EQUILIBRIO_PROMPT, "\n".join(blocos), EQUILIBRIO_SCHEMA)
    except (AiProviderError, HTTPException):
        _log_quiz.warning("quiz: %d questão(ões) com a certa mais longa ficaram como vieram (IA indisponível)", len(indices))
        return questoes
    novas = resultado.content.get("questoes")
    if not isinstance(novas, list) or len(novas) != len(indices):
        _log_quiz.warning("quiz: o equilíbrio das alternativas voltou com o formato errado; questões mantidas")
        return questoes

    saida = list(questoes)
    reescritas = 0
    for i, nova in zip(indices, novas):
        antiga = questoes[i]
        alternativas = [str(t).strip() for t in (nova.get("alternativas") or [])] if isinstance(nova, dict) else []
        if len(alternativas) != 4 or not all(alternativas):
            continue
        analise = _analise_valida(nova.get("analise"), 4) or antiga.get("analise")
        candidata = {
            **antiga,
            "alternativas": alternativas,
            "analise": analise,
            "explicacao": _explicacao_formatada(antiga.get("resumo", ""), analise, antiga["correta"]),
        }
        if _razao_de_tamanho(candidata) > _razao_de_tamanho(antiga):
            continue  # a reescrita deixou a certa ainda mais destacada: fica a original
        saida[i] = candidata
        reescritas += 1
    _log_quiz.info("quiz: %d de %d questão(ões) desequilibradas foram reescritas", reescritas, len(indices))
    return saida


async def _completar(prompt: str, ja_escritas: list[dict[str, Any]], faltam: int) -> list[dict[str, Any]]:
    """Uma segunda chamada, só para o que faltou, dizendo o que já foi escrito para o modelo não repetir.

    Só roda quando a primeira devolveu MENOS que o pedido depois da limpeza. Cada chamada conta na cota diária de
    IA da pessoa, então não é um laço: uma tentativa, e o que vier junto com o que já há é o que se tem.
    """
    temas = "\n".join(f"- {q['conceito'] or q['enunciado'][:90]}" for q in ja_escritas)
    pedido = (
        f"{prompt}\n"
        f"JA ESCRITAS (nao repita estes temas nem estes enunciados):\n{temas or '- (nenhuma)'}\n"
        f"ESCREVA MAIS {faltam} QUESTOES, DIFERENTES DAS ACIMA.\n"
    )
    resultado = await generate_json(SYSTEM_PROMPT, pedido, QUIZ_SCHEMA)
    return _clean_questions(resultado.content.get("questoes"))


def _analise_valida(bruto: Any, quantas: int) -> Optional[list[str]]:
    """Os textos por alternativa, se vieram completos: um por alternativa e nenhum vazio. Senão None.

    Modelo mais fraco às vezes ignora o campo ou devolve menos textos que alternativas. Um texto faltando não pode
    ser "adivinhado" nem deixar uma alternativa sem explicação no meio das outras — nesse caso a questão fica só com
    o resumo, como era antes.
    """
    if not isinstance(bruto, list):
        return None
    textos = [str(texto).strip() for texto in bruto]
    if len(textos) != quantas or not all(textos):
        return None
    return [texto[:400] for texto in textos]


def _explicacao_formatada(resumo: str, analise: Optional[list[str]], correta: int) -> str:
    """A explicação em Markdown: o resumo e, para CADA alternativa, por que ela está certa ou errada.

    Só dizer por que a certa está certa deixava a pessoa sem saber por que a que ela escolheu estava errada — e é
    o engano específico de cada alternativa que ensina. Numera de 1, como a tela mostra as opções.
    Sem `analise` (modelo que a omitiu), fica o resumo sozinho, como antes.
    """
    if not analise or len(analise) != 4:
        return resumo
    linhas = [
        f"- **Alternativa {posicao + 1} — {'correta' if posicao == correta else 'errada'}.** {texto}"
        for posicao, texto in enumerate(analise)
    ]
    partes = [resumo] if resumo else []
    partes.append("**Por que cada alternativa:**\n" + "\n".join(linhas))
    return "\n\n".join(partes)


def _sem_repetidas(questoes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tira a questão que repete o enunciado de outra já aceita (comparado sem pontuação nem caixa)."""
    vistos: set[str] = set()
    unicas = []
    for questao in questoes:
        chave = "".join(c for c in questao["enunciado"].lower() if c.isalnum())[:200]
        if chave in vistos:
            continue
        vistos.add(chave)
        unicas.append(questao)
    return unicas


def _clean_questions(raw: Any) -> list[dict[str, Any]]:
    """Descarta o que não dá para usar em vez de gravar questão quebrada.

    Uma questão sem 4 alternativas ou com índice de resposta fora do intervalo
    seria uma questão impossível de acertar — e o usuário não teria como saber
    que o erro foi nosso.
    """
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("enunciado") or "").strip()
        options = [str(option).strip() for option in (item.get("alternativas") or []) if str(option).strip()]
        try:
            correct = int(item.get("correta"))
        except (TypeError, ValueError):
            continue
        # Alternativa a MAIS não derruba a questão: o gabarito está no intervalo, e cortar para 4 só perde uma
        # errada. Descartar tudo que não vinha com exatamente 4 era o que deixava um quiz de 6 com 1 questão.
        # Alternativa a MENOS ainda descarta: falta o que a pessoa escolher.
        analise = _analise_valida(item.get("analise"), len(options))
        if len(options) > 4 and 0 <= correct <= 3:
            options = options[:4]
            analise = analise[:4] if analise else None
        if not prompt or len(options) != 4 or not 0 <= correct <= 3:
            continue
        difficulty = str(item.get("dificuldade") or "").strip().lower()
        resumo = str(item.get("explicacao") or "").strip()[:1000]
        options, correct, analise = _embaralhar(options, correct, analise, resumo)
        cleaned.append(
            {
                "enunciado": prompt[:2000],
                "codigo": str(item.get("codigo") or "").strip()[:4000],
                "linguagem": str(item.get("linguagem") or "").strip()[:30],
                "alternativas": options,
                "correta": correct,
                # `resumo` e `analise` ficam junto: reescrever as alternativas (`_equilibrar`) refaz a explicação.
                "resumo": resumo,
                "analise": analise,
                "explicacao": _explicacao_formatada(resumo, analise, correct),
                "dificuldade": difficulty if difficulty in {"facil", "medio", "dificil"} else "medio",
                # Pode vir vazio: modelo mais fraco às vezes ignora o campo. A
                # questão continua utilizável — só não alimenta a revisão, o
                # que é melhor que descartá-la por falta de metadado.
                "conceito": str(item.get("conceito") or "").strip()[:200],
            }
        )
    return cleaned


# O que da questão sai ANTES de a tentativa existir. Filtrado aqui, no código, além do `select` da consulta: o
# gabarito (`correct`) e a explicação não podem depender de uma projeção de colunas que alguém edite sem perceber.
_CAMPOS_DA_QUESTAO = ("id", "prompt", "code_snippet", "code_language", "options", "difficulty", "order_index")


def _quiz_para_responder(supabase: Client, quiz: dict[str, Any]) -> dict[str, Any]:
    """O quiz com as questões, SEM gabarito e SEM explicação — e sem o rascunho, que é assunto da rota dele."""
    linhas = (
        supabase.table("pathr_question")
        .select(",".join(_CAMPOS_DA_QUESTAO))
        .eq("quiz_id", str(quiz["id"]))
        .order("order_index")
        .execute()
        .data
        or []
    )
    questions = [{campo: linha.get(campo) for campo in _CAMPOS_DA_QUESTAO} for linha in linhas]
    return {**{k: v for k, v in quiz.items() if k != "draft"}, "questions": questions}


def _id_valido(valor: str) -> str:
    try:
        return str(uuid.UUID(valor))
    except ValueError:
        # 404, e não 422: um id que não é UUID nunca existiu, e a resposta não deve distinguir isso de "não é seu".
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado.") from None


class DraftIn(BaseModel):
    """Onde a pessoa parou num quiz ainda aberto: a questão e as alternativas já escolhidas."""

    index: int = Field(ge=0, le=100)
    # question_id -> índice da alternativa. Vem de fora e vai para um jsonb: o tamanho é limitado aqui e as chaves
    # são conferidas contra as questões do quiz na hora de gravar.
    answers: dict[str, int] = Field(default_factory=dict, max_length=100)


def _rascunho_lido(draft: Any) -> Optional[dict[str, Any]]:
    if not isinstance(draft, dict) or not isinstance(draft.get("answers"), dict):
        return None
    return {"index": int(draft.get("index") or 0), "answers": draft["answers"], "updated_at": draft.get("updated_at")}


# As três rotas abaixo têm caminho de UM segmento e ficam ANTES de `/{quiz_id}`: depois dele, "em-andamento" e
# "historico" seriam lidos como o id de um quiz e devolveriam 404.


@router.get("/em-andamento")
def quiz_em_andamento(
    node_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O quiz deste módulo que foi gerado e ainda não foi enviado, com o que já foi respondido.

    É o que faz sair da aba e voltar continuar de onde parou. O quiz e as respostas moram no SERVIDOR: guardados
    só no navegador, sumiam com a limpeza de dados, uma aba anônima ou outro aparelho — e a pessoa recomeçava um
    quiz que a IA já tinha escrito e que ninguém mais ia ler.
    """
    user_id = str(current_user["id"])
    node_id = _id_valido(node_id)
    quizzes = (
        supabase.table("pathr_quiz").select("*")
        .eq("user_id", user_id).eq("node_id", node_id)
        .order("created_at", desc=True).limit(10).execute().data or []
    )
    if not quizzes:
        return {"quiz": None, "rascunho": None}
    respondidos = {
        str(linha["quiz_id"])
        for linha in (
            supabase.table("pathr_attempt").select("quiz_id")
            .eq("user_id", user_id).in_("quiz_id", [str(q["id"]) for q in quizzes]).execute().data or []
        )
    }
    aberto = next((q for q in quizzes if str(q["id"]) not in respondidos), None)
    if aberto is None:
        return {"quiz": None, "rascunho": None}
    return {"quiz": _quiz_para_responder(supabase, aberto), "rascunho": _rascunho_lido(aberto.get("draft"))}


@router.get("/historico")
def historico_do_modulo(
    node_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """As tentativas já enviadas neste módulo, da mais recente para a mais antiga."""
    user_id = str(current_user["id"])
    node_id = _id_valido(node_id)
    quizzes = (
        supabase.table("pathr_quiz").select("id,title,question_count")
        .eq("user_id", user_id).eq("node_id", node_id)
        .order("created_at", desc=True).limit(50).execute().data or []
    )
    if not quizzes:
        return []
    por_id = {str(q["id"]): q for q in quizzes}
    tentativas = (
        supabase.table("pathr_attempt")
        .select("id,quiz_id,score,correct_count,duration_s,finished_at,tag_breakdown")
        .eq("user_id", user_id).in_("quiz_id", list(por_id))
        .order("finished_at", desc=True).limit(30).execute().data or []
    )
    return [
        {
            "attempt_id": str(t["id"]),
            "quiz_id": str(t["quiz_id"]),
            "title": por_id[str(t["quiz_id"])].get("title"),
            "score": t.get("score"),
            "correct_count": t.get("correct_count"),
            "total": (t.get("tag_breakdown") or {}).get("total") or por_id[str(t["quiz_id"])].get("question_count"),
            "duration_s": t.get("duration_s"),
            "finished_at": t.get("finished_at"),
        }
        for t in tentativas
        if str(t["quiz_id"]) in por_id
    ]


@router.get("/tentativas/{attempt_id}")
def tentativa(
    attempt_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Uma tentativa já enviada, no formato da correção: as questões e, para cada uma, o que foi respondido, o
    gabarito e a explicação. O gabarito só sai daqui DEPOIS de a tentativa existir — quem ainda não respondeu não
    tem um `attempt_id` para pedir."""
    user_id = str(current_user["id"])
    linhas = (
        supabase.table("pathr_attempt").select("*")
        .eq("id", _id_valido(attempt_id)).eq("user_id", user_id).limit(1).execute().data or []
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tentativa não encontrada.")
    tentativa_ = linhas[0]
    quiz = _owned_quiz(supabase, str(tentativa_["quiz_id"]), user_id)
    resultados = tentativa_.get("answers") or []
    return {
        "quiz": _quiz_para_responder(supabase, quiz),
        "result": {
            "attempt_id": str(tentativa_["id"]),
            "score": tentativa_.get("score"),
            "correct_count": tentativa_.get("correct_count"),
            "total": len(resultados),
            "results": resultados,
        },
    }


@router.put("/{quiz_id}/rascunho")
def salvar_rascunho(
    quiz_id: str,
    payload: DraftIn,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Grava onde a pessoa parou. Substitui no lugar: o que importa é a posição atual, não cada clique.

    Nunca falha a tela: o rascunho é uma melhoria, e um erro aqui (coluna ainda sem migrar, banco lento) não pode
    impedir ninguém de responder o quiz. Devolve `salvo: false` e a tela segue com a cópia do navegador.
    """
    user_id = str(current_user["id"])
    quiz = _owned_quiz(supabase, _id_valido(quiz_id), user_id)
    ja_enviado = supabase.table("pathr_attempt").select("id").eq("quiz_id", str(quiz["id"])).limit(1).execute().data
    if ja_enviado:
        return {"salvo": False}
    ids = {
        str(linha["id"])
        for linha in (supabase.table("pathr_question").select("id").eq("quiz_id", str(quiz["id"])).execute().data or [])
    }
    agora = _now().isoformat()
    rascunho = {
        "index": min(payload.index, max(len(ids) - 1, 0)),
        "answers": {q: a for q, a in payload.answers.items() if q in ids and 0 <= a <= 20},
        "updated_at": agora,
    }
    try:
        supabase.table("pathr_quiz").update({"draft": rascunho}).eq("id", str(quiz["id"])).eq("user_id", user_id).execute()
    except Exception:  # noqa: BLE001
        logging.getLogger("pathr.quizzes").warning("rascunho do quiz não gravado", exc_info=True)
        return {"salvo": False}
    return {"salvo": True, "updated_at": agora}


@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O quiz para responder — SEM gabarito e SEM explicação."""
    quiz = _owned_quiz(supabase, quiz_id, str(current_user["id"]))
    return _quiz_para_responder(supabase, quiz)


def _owned_quiz(supabase: Client, quiz_id: str, user_id: str) -> dict[str, Any]:
    rows = (
        supabase.table("pathr_quiz")
        .select("*")
        .eq("id", quiz_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz não encontrado.")
    return rows[0]


@router.post("/{quiz_id}/submit")
def submit_quiz(
    quiz_id: str,
    payload: SubmitAnswers,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Corrige, devolve o gabarito com explicações e realimenta o perfil.

    A correção acontece aqui e não no cliente pelo motivo óbvio — o cliente
    não tem o gabarito — e por um menos óbvio: é este o momento em que a
    proficiência por tag pode ser atualizada com evidência.
    """
    user_id = str(current_user["id"])
    quiz = _owned_quiz(supabase, quiz_id, user_id)
    questions = (
        supabase.table("pathr_question")
        .select("*")
        .eq("quiz_id", quiz_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    if not questions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz sem questões.")

    results = []
    correct_count = 0
    for question in questions:
        given = payload.answers.get(str(question["id"]))
        expected = int((question.get("correct") or {}).get("index", -1))
        is_correct = given is not None and int(given) == expected
        correct_count += int(is_correct)
        results.append(
            {
                "question_id": str(question["id"]),
                "answer": given,
                "correct_index": expected,
                "is_correct": is_correct,
                "explanation": numerar_de_um(question.get("explanation")),
            }
        )

    score = round(100 * correct_count / len(questions), 1)
    tag_ids = [str(tag) for tag in (quiz.get("tag_ids") or [])]
    breakdown = {"score": score, "correct": correct_count, "total": len(questions)}
    # Só a PRIMEIRA tentativa rende XP e mexe no nível das tecnologias. Refazer
    # continua valendo como estudo (a tentativa é gravada e os erros voltam na
    # revisão), mas o gabarito já foi mostrado na primeira: repetir o mesmo quiz
    # em laço inflava XP e proficiência sem estudo nenhum.
    primeira_tentativa = not (
        supabase.table("pathr_attempt").select("id")
        .eq("quiz_id", quiz_id).eq("user_id", user_id).limit(1).execute().data
    )

    attempt = (
        supabase.table("pathr_attempt")
        .insert(
            {
                "quiz_id": quiz_id,
                "user_id": user_id,
                "finished_at": _now().isoformat(),
                "score": score,
                "correct_count": correct_count,
                "duration_s": payload.duration_s,
                "answers": results,
                "tag_breakdown": breakdown,
            }
        )
        .execute()
        .data[0]
    )

    # A tentativa fechou: o rascunho não tem mais o que guardar. Melhor esforço — a linha da tentativa já está
    # gravada, e uma coluna ainda sem migrar não pode desfazer a correção.
    try:
        supabase.table("pathr_quiz").update({"draft": None}).eq("id", quiz_id).eq("user_id", user_id).execute()
    except Exception:  # noqa: BLE001
        pass

    if primeira_tentativa:
        _apply_result_to_tags(supabase, user_id, tag_ids, score)
    reciclados = _recycle(supabase, user_id, questions, results)
    if primeira_tentativa:
        log_activity(
            supabase,
            user=current_user,
            kind="quiz_done",
            title=quiz.get("title") or "Quiz",
            ref_id=quiz_id,
            minutes=max(1, payload.duration_s // 60),
            tag_ids=tag_ids,
            detail=breakdown,
        )

    return {
        "attempt_id": str(attempt["id"]),
        "score": score,
        "correct_count": correct_count,
        "total": len(questions),
        "results": results,
        # O que vai voltar reescrito e o que foi dado como aprendido. A tela
        # mostra isso no fim do quiz: errar sem saber que a pergunta volta é o
        # que faz o erro parecer punição em vez de etapa.
        "review": reciclados,
    }


def _materiais_concluidos(
    supabase: Client, user_id: str, tag_ids: list[str], limite: int = 12
) -> list[str]:
    """Os titulos do que a pessoa terminou sobre estas tecnologias.

    So o TITULO viaja para o modelo, e nao o texto do artigo: o titulo ja diz
    o recorte ("CI/CD com GitHub Actions", "Git em 5 minutos") e mandar o
    conteudo inteiro encheria o prompt com milhares de palavras para ganhar
    pouco -- alem de custar em toda geracao de quiz.

    Best-effort: sem esta lista o quiz continua funcionando, so mais generico.
    """
    try:
        progresso = (
            supabase.table("pathr_user_resource")
            .select("resource_id")
            .eq("user_id", user_id)
            .eq("status", "done")
            .limit(200)
            .execute()
            .data
            or []
        )
        ids = [str(linha["resource_id"]) for linha in progresso]
        if not ids:
            return []
        recursos = (
            supabase.table("pathr_resource")
            .select("title,tag_ids")
            .in_("id", ids)
            .limit(200)
            .execute()
            .data
            or []
        )
        alvo = {str(t) for t in tag_ids}
        titulos = [
            str(r["title"])
            for r in recursos
            if alvo & {str(t) for t in (r.get("tag_ids") or [])}
        ]
        return titulos[:limite]
    except Exception:  # noqa: BLE001
        return []


def _due_reviews(supabase: Client, user_id: str, tag_ids: list[str], limit: int = 4) -> list[dict]:
    """Conceitos vencidos nestas tags, do mais atrasado para o menos.

    O teto de 4 existe para o quiz não virar só revisão: com 6 questões, quatro
    recicladas ainda deixam duas novas. Um plano que só repete o que a pessoa
    errou para de avançar, e um que nunca repete não consolida nada.
    """
    if not tag_ids:
        return []
    return (
        supabase.table("pathr_review_item")
        .select("id,front,back,tag_id,ease,repetitions,interval_days,lapses")
        .eq("user_id", user_id)
        .in_("tag_id", tag_ids)
        .lte("due_at", _now().isoformat())
        .order("due_at")
        .limit(limit)
        .execute()
        .data
        or []
    )


def _recent_scores(supabase: Client, user_id: str, limit: int = 3) -> list[float]:
    """As últimas notas, para a escada de dificuldade.

    Três tentativas: menos que isso e um dia ruim derruba o nível; mais e a
    escada demora demais a reagir a quem melhorou.
    """
    rows = (
        supabase.table("pathr_attempt")
        .select("score")
        .eq("user_id", user_id)
        .not_.is_("score", "null")
        .order("finished_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    return [float(row["score"]) for row in rows]


def _recycle(
    supabase: Client, user_id: str, questions: list[dict], results: list[dict]
) -> dict[str, list[str]]:
    """Fecha o ciclo do erro: o que caiu vira pendência, o que subiu se afasta.

    Três casos por questão, e é a combinação deles que produz a "linha de
    aprendizagem":

    - errou uma questão reciclada -> o item volta a vencer hoje, com ease menor;
    - acertou uma questão reciclada -> o SM-2 empurra a próxima aparição para
      frente, e depois de algumas repetições ela para de vir;
    - errou uma questão nova -> nasce um item, vencendo hoje.

    Best-effort como o `log_activity`: uma falha aqui não pode derrubar a
    correção que a pessoa acabou de terminar. Perder um item de revisão custa
    uma repetição; perder a nota custa o trabalho dela.
    """
    por_id = {str(q["id"]): q for q in questions}
    volta: list[str] = []
    aprendido: list[str] = []

    # As duas leituras que o laço precisava, feitas UMA vez.
    #
    # Antes eram duas consultas por questão: uma para carregar o item de
    # revisão e outra, dentro de `_ja_pendente`, para conferir se o conceito já
    # estava na fila. Num quiz de dez questões isso somava vinte idas ao
    # PostgREST enquanto a pessoa olhava para "Corrigindo…" — e o trabalho é o
    # mesmo com duas.
    ids_reciclados = [
        str(q["review_item_id"]) for q in questions if q.get("review_item_id")
    ]
    itens_reciclados: dict[str, dict] = {}
    if ids_reciclados:
        itens_reciclados = {
            str(linha["id"]): linha
            for linha in (
                supabase.table("pathr_review_item")
                .select("id,ease,repetitions,interval_days,lapses")
                .in_("id", ids_reciclados)
                .execute()
                .data
                or []
            )
        }

    tags_em_jogo = sorted(
        {str((q.get("tag_ids") or [None])[0]) for q in questions if (q.get("tag_ids") or [None])[0]}
    )
    pendentes: set[str] = set()
    if tags_em_jogo:
        pendentes = {
            review.concept_key(linha.get("front"))
            for linha in (
                supabase.table("pathr_review_item")
                .select("front")
                .eq("user_id", user_id)
                .in_("tag_id", tags_em_jogo)
                .execute()
                .data
                or []
            )
        }

    for resultado in results:
        questao = por_id.get(resultado["question_id"])
        if not questao:
            continue
        conceito = (questao.get("concept") or "").strip()
        item_id = questao.get("review_item_id")
        acertou = resultado["is_correct"]

        # Base de conhecimento: todo erro entra (reciclado ou não); acertar o que
        # voltava para revisão tira da lista de pendências.
        if conceito:
            if acertou and item_id:
                conhecimento.marcar_revisado(supabase, user_id, conceito)
            elif not acertou:
                conhecimento.registrar(
                    supabase, user_id, "quiz", conceito,
                    detalhe=questao.get("prompt"), tag_id=(questao.get("tag_ids") or [None])[0],
                    ref_id=str(questao.get("id") or ""),
                )

        try:
            if item_id:
                atual = itens_reciclados.get(str(item_id))
                if not atual:
                    continue
                proximo = review.schedule(
                    atual, review.QUALITY_HIT if acertou else review.QUALITY_MISS
                )
                supabase.table("pathr_review_item").update(proximo).eq(
                    "id", str(item_id)
                ).execute()
                (aprendido if acertou else volta).append(conceito or "conceito revisado")
                continue

            # Questão nova. Só o erro vira item — acertar de primeira não é
            # coisa a revisar, e criar item para tudo encheria a fila com o que
            # a pessoa já sabe.
            if acertou or not conceito:
                continue
            chave = review.concept_key(conceito)
            # Errar duas questões sobre a mesma ideia no mesmo quiz criaria dois
            # itens, e a pessoa responderia a mesma lacuna duas vezes em
            # paralelo. O conjunto acumula dentro do laço, então o segundo erro
            # já encontra o primeiro.
            if chave in pendentes:
                continue
            pendentes.add(chave)

            correta = int((questao.get("correct") or {}).get("index", -1))
            alternativas = questao.get("options") or []
            resposta = alternativas[correta] if 0 <= correta < len(alternativas) else ""
            supabase.table("pathr_review_item").insert(
                {
                    "user_id": user_id,
                    "kind": "question",
                    "tag_id": (questao.get("tag_ids") or [None])[0],
                    "question_id": str(questao["id"]),
                    "front": conceito,
                    "back": " ".join(
                        part for part in [str(resposta), numerar_de_um(questao.get("explanation")) or ""] if part
                    )[:2000],
                    # Vence agora: o próximo quiz sobre a tag já recicla.
                    "due_at": _now().isoformat(),
                    "lapses": 1,
                }
            ).execute()
            volta.append(conceito)
        except Exception:  # noqa: BLE001
            continue

    return {"volta": volta, "aprendido": aprendido}


def _apply_result_to_tags(
    supabase: Client, user_id: str, tag_ids: list[str], score: float
) -> None:
    """Traduz a nota em proficiência.

    Só mexe nos extremos, e de forma assimétrica: 80% ou mais sobe um nível
    (teto 4), abaixo de 40% desce um (piso 1). A faixa do meio não mexe em
    nada — um 60% não é evidência de nada em particular, e ficar oscilando o
    perfil a cada quiz faria o roadmap se reescrever sem motivo.

    A confiança sobe sempre: mesmo um resultado ambíguo é mais evidência do
    que a estimativa do currículo tinha.
    """
    if not tag_ids:
        return
    for tag_id in tag_ids:
        rows = (
            supabase.table("pathr_user_tag")
            .select("id,proficiency,confidence")
            .eq("user_id", user_id)
            .eq("tag_id", tag_id)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            continue
        row = rows[0]
        current = int(row.get("proficiency") or 0)
        if score >= 80:
            proficiency = min(4, current + 1)
        elif score < 40:
            proficiency = max(1, current - 1)
        else:
            proficiency = current
        supabase.table("pathr_user_tag").update(
            {
                "proficiency": proficiency,
                "confidence": min(1.0, float(row.get("confidence") or 0.5) + 0.25),
                "source": "quiz",
                "last_assessed_at": _now().isoformat(),
            }
        ).eq("id", row["id"]).execute()


@router.get("")
def list_quizzes(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return (
        supabase.table("pathr_quiz")
        .select("id,title,kind,difficulty,question_count,tag_ids,created_at")
        .eq("user_id", str(current_user["id"]))
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )


@router.get("/{quiz_id}/attempts")
def list_attempts(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _owned_quiz(supabase, quiz_id, str(current_user["id"]))
    return (
        supabase.table("pathr_attempt")
        .select("id,score,correct_count,duration_s,finished_at,tag_breakdown")
        .eq("quiz_id", quiz_id)
        .order("finished_at", desc=True)
        .execute()
        .data
        or []
    )
