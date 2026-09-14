"""Módulo de idioma: nivelamento, prática e vocabulário.

Módulo ATIVÁVEL, não seção fixa: `pathr_english_profile.enabled` é o
interruptor, e enquanto ele estiver desligado nada aqui aparece no plano
diário. Foi assim que o recurso foi pedido, e é a diferença entre um app que
respeita quem já fala inglês e um que empurra prática que ninguém pediu.

O nivelamento é adaptativo: a dificuldade do próximo item sai do acerto do
anterior, então o teste converge no nível em ~20 itens em vez de precisar de
100.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services import languages, review, traducao
from app.services import treino_idioma as treino
from app.services.progress import log_activity

router = APIRouter(prefix="/languages", tags=["idioma"])

BANDS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# As habilidades que o nivelamento pontua.
#
# `listening` tem audio de verdade: a transcricao guardada aqui e lida em voz
# alta pelo navegador (speechSynthesis) na tela, e a transcricao so aparece se
# a pessoa pedir. A sintese e do proprio aparelho -- sem chave, sem requisicao
# e sem custo por caractere -- que foi o que permitiu o listening existir sem
# virar cobranca por uso, ja que o nivelamento gera itens novos a cada lote,
# para cada pessoa, em cada tentativa.
SKILLS = frozenset(
    {"grammar", "vocabulary", "reading", "listening", "writing", "speaking", "business"}
)

ITEMS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "itens": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "habilidade": {"type": "STRING"},
                    "topico": {"type": "STRING"},
                    "banda": {"type": "STRING"},
                    "contexto": {"type": "STRING"},
                    "enunciado": {"type": "STRING"},
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correta": {"type": "INTEGER"},
                    "explicacao": {"type": "STRING"},
                },
                "required": ["enunciado", "alternativas", "correta", "explicacao"],
            },
        }
    },
    "required": ["itens"],
}

SYSTEM_PROMPT = """Você cria itens de avaliação de inglês corporativo para profissionais de tecnologia.

Regras:

1. O enunciado e as alternativas ficam EM INGLÊS. A explicação fica em
   português do Brasil — a pessoa está aprendendo, e a explicação é o ensino.
2. Todo item nasce de uma situação real de trabalho em time distribuído:
   daily, code review, e-mail de prazo, entrevista técnica, apresentação,
   negociação de escopo. Nada de gramática solta sem contexto.
3. Exatamente 4 alternativas; o campo correta é o índice de 0 a 3. As erradas
   precisam ser erros que brasileiros realmente cometem em inglês (falso
   cognato, tradução literal, tom errado), não absurdos.
4. O campo habilidade: grammar, vocabulary, reading, listening, writing,
   speaking ou business.
5. O item se responde SÓ com o que está escrito nele. Não há áudio, vídeo
   nem anexo para abrir: nunca escreva "based on the audio", "listen to the
   recording", "in the video" ou equivalente. Se o item depende de uma fala,
   de um e-mail ou de um trecho de reunião, o texto INTEIRO vai no contexto.
6. Item de listening traz o DIÁLOGO no contexto, com quem fala em cada linha
   ("Ana: ...", "Marc: ..."), uma linha por fala — é esse texto que a tela lê
   em voz alta para a pessoa ouvir. O contexto é o diálogo, e não a descrição
   da cena: "Daily stand-up on Zoom" sozinho não diz a ninguém quem ficou com
   a tarefa. Escreva falas curtas e naturais, como gente fala numa reunião.
   Se a pergunta aponta um trecho ("replace the underlined part"), MARQUE o
   trecho no contexto entre colchetes duplos: "Can you please [[clean up]]
   this function?". A tela desenha isso sublinhado; texto sem a marca não
   tem sublinhado nenhum, e a pergunta fica sem resposta.
7. O campo banda: A1, A2, B1, B2, C1 ou C2 — a dificuldade real do item.
8. A explicação diz por que a certa soa natural e por que a mais tentadora
   das erradas soa estranha para um falante nativo.
9. O campo topico: EXATAMENTE um dos tópicos listados no pedido para aquela
   habilidade. É com ele que a tela mostra como a pessoa foi em cada tópico.
10. Responda apenas o JSON."""


# Um item que manda ouvir alguma coisa é um item sem resposta: o app não
# reproduz som, e a coluna `audio_url` nunca foi preenchida por ninguém. O
# prompt já proíbe essa formulação, mas o modelo é o modelo — a guarda é o que
# garante que ela não chegue à tela.
_REMETE_A_MIDIA = re.compile(
    r"(?:based on|according to|in|from)\s+the\s+(?:audio|recording|video|clip|conversation you)"
    r"|listen(?:ing)?\s+to\s+the"
    r"|you\s+(?:just\s+)?(?:heard|hear)"
    r"|no\s+áudio|na\s+gravação",
    re.IGNORECASE,
)

# O enunciado aponta para um trecho destacado ("replace the underlined part").
# Texto puro não tem sublinhado: o trecho precisa vir marcado com [[ ]], que a
# tela desenha sublinhado. Sem a marca, a pergunta não tem resposta.
_REMETE_A_DESTAQUE = re.compile(
    r"\b(?:underlined|highlighted|in\s+bold|bolded|in\s+italics)\b|sublinhad|destacad|em\s+negrito",
    re.IGNORECASE,
)
_TRECHO_MARCADO = re.compile(r"\[\[[^\[\]]+\]\]")

# Uma fala transcrita começa por quem fala: "Ana: I'll push it after lunch."
# Duas ou mais dessas linhas são um diálogo; nenhuma é a descrição de cena que
# deixou a pergunta sem resposta ("Daily stand-up meeting on Zoom.").
#
# O sinal é a marcação de quem fala, e não o tamanho do texto. Medir por
# comprimento reprovava diálogo curto e legítimo — "Ana: I'll push it after
# lunch.\nMarc: Thanks." tem duas falas e menos de 60 caracteres — enquanto
# deixava passar qualquer descrição longa que tivesse dois-pontos no meio.
#
# O casamento é por linha porque o prompt pede uma fala por linha. Um diálogo
# escrito todo numa linha só é reprovado, e o lote é gerado de novo: é o erro
# barato dos dois, já que o outro lado é cobrar uma resposta que não está no
# item.
_FALA = re.compile(r"^[^\n:]{1,40}:\s*\S", re.MULTILINE)


def _tem_transcricao(contexto: str) -> bool:
    return len(_FALA.findall(contexto)) >= 2


def _respondivel(prompt: str, skill: str, contexto: str) -> bool:
    """O item traz tudo que a pergunta cobra?

    Vale para qualquer habilidade que remeta a uma mídia inexistente, e vale
    sempre para `listening`: ali a transcrição não é enfeite, é o enunciado.
    """
    # Lacuna no diálogo que vai para a voz: ela leria "underscore" no lugar
    # da palavra que a pergunta cobra.
    if skill == "listening" and (not _tem_transcricao(contexto) or "__" in contexto):
        return False
    if _REMETE_A_DESTAQUE.search(prompt) and not _TRECHO_MARCADO.search(f"{contexto} {prompt}"):
        return False
    return not (_REMETE_A_MIDIA.search(prompt) and not _tem_transcricao(contexto))


class EnglishSettings(BaseModel):
    enabled: Optional[bool] = None
    target_level: Optional[str] = Field(default=None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    focus_areas: Optional[list[Any]] = None
    daily_goal_min: Optional[int] = Field(default=None, ge=5, le=180)
    # A regua escolhida (cefr, ielts, toefl_ibt, jlpt...) e a meta NELA. O
    # equivalente em CEFR e derivado no router, nao enviado pelo cliente: a
    # tabela de conversao e do servidor, e aceitar os dois do cliente deixaria
    # alguem declarar "7.0 = A1".
    exam: Optional[str] = Field(default=None, max_length=32)
    exam_target: Optional[str] = Field(default=None, max_length=40)


class AnswerItem(BaseModel):
    item_id: str
    answer: int = Field(ge=0, le=3)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _idioma_valido(language: str) -> str:
    """Recusa idioma fora do catalogo antes de tocar no banco.

    Sem isto, um `?language=xx` qualquer criaria uma linha de perfil para um
    idioma que a tela nao sabe mostrar e o nivelamento nao sabe gerar."""
    codigo = (language or "en").strip().lower()
    if not languages.existe(codigo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idioma nao suportado: {codigo}.",
        )
    return codigo


def _com_exame(perfil: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta o nivel medido TRADUZIDO para a regua escolhida.

    O banco guarda `cefr_level` sempre — e a unica escala em que o app mede.
    `exam_level` e derivado na leitura, e nao guardado, porque trocar de exame
    tem que reapresentar o mesmo resultado, nao invalida-lo."""
    idioma = perfil.get("language") or "en"
    exame = perfil.get("exam") or "cefr"
    medido = perfil.get("cefr_level")
    perfil["exam_level"] = languages.meta_no_exame(idioma, exame, medido) if medido else None
    perfil["target_cefr"] = (
        languages.cefr_da_meta(idioma, exame, perfil.get("exam_target") or "")
        or perfil.get("target_level")
    )
    return perfil


def _profile(supabase: Client, user_id: str, language: str = "en") -> dict[str, Any]:
    rows = (
        supabase.table("pathr_english_profile")
        .select("*")
        .eq("user_id", user_id)
        .eq("language", language)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]
    # Primeira visita a este idioma — cria em vez de responder 404 por algo
    # que e responsabilidade nossa.
    return (
        supabase.table("pathr_english_profile")
        .insert({"user_id": user_id, "language": language})
        .execute()
        .data[0]
    )


@router.get("/catalog")
def catalog(_current_user: dict = Depends(get_current_user)):
    """Os idiomas e as provas de cada um, com a equivalencia em CEFR.

    Vem do servidor e nao de uma copia no frontend: a tabela de equivalencia e
    a mesma que converte a meta, e duas copias divergiriam na primeira correcao
    feita so de um lado."""
    return languages.catalogo()


@router.get("/profiles")
def list_profiles(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Todos os idiomas que esta pessoa estuda. A tela precisa dos varios de
    uma vez para desenhar a lista; pedir um por um seriam nove requisicoes."""
    rows = (
        supabase.table("pathr_english_profile")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .execute()
        .data
        or []
    )
    return [_com_exame(linha) for linha in rows]


@router.get("/profile")
def get_english_profile(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _com_exame(_profile(supabase, str(current_user["id"]), _idioma_valido(language)))


@router.patch("/profile")
def update_english_profile(
    payload: EnglishSettings,
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    codigo = _idioma_valido(language)
    user_id = str(current_user["id"])
    update = payload.model_dump(exclude_unset=True)
    if not update:
        return _com_exame(_profile(supabase, user_id, codigo))

    if "exam" in update and not languages.exame(codigo, update["exam"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exame nao existe para {codigo}.",
        )

    # A meta na escala do exame vira tambem meta em CEFR: e nela que o
    # nivelamento mede, e sem a conversao a meta seria texto sem efeito.
    if "exam_target" in update:
        exame_atual = update.get("exam") or _profile(supabase, user_id, codigo).get("exam") or "cefr"
        equivalente = languages.cefr_da_meta(codigo, exame_atual, update["exam_target"] or "")
        if equivalente:
            update["target_level"] = equivalente

    update["updated_at"] = _now().isoformat()
    _profile(supabase, user_id, codigo)
    linha = (
        supabase.table("pathr_english_profile")
        .update(update)
        .eq("user_id", user_id)
        .eq("language", codigo)
        .execute()
        .data[0]
    )
    return _com_exame(linha)


@router.post("/assessment", status_code=status.HTTP_201_CREATED)
async def start_assessment(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Abre um nivelamento e gera o primeiro lote de itens.

    Gera em lote de 5, não os 20 de uma vez: o teste é adaptativo, e os itens
    seguintes só podem ser calibrados depois de ver como a pessoa foi nos
    primeiros. Gerar tudo antes desperdiçaria cota em itens de dificuldade
    errada.
    """
    codigo = _idioma_valido(language)
    user_id = str(current_user["id"])
    profile = _profile(supabase, user_id, codigo)

    # Começar um novo encerra o anterior explicitamente. Sem isto, o de antes
    # ficaria "in_progress" para sempre e `/assessment/active` continuaria
    # oferecendo a retomada de um teste que a pessoa já decidiu refazer.
    supabase.table("pathr_english_assessment").update({"status": "abandoned"}).eq(
        "user_id", user_id
    ).eq("language", codigo).eq("status", "in_progress").execute()

    assessment = (
        supabase.table("pathr_english_assessment")
        .insert(
            {
                "user_id": user_id,
                "kind": "placement",
                "item_count": 20,
                "language": codigo,
                # Explícito, e não herdado do default da coluna: é este campo
                # que decide se a tela oferece retomar o teste, e um default
                # de banco é longe demais de onde a decisão é lida.
                "status": "in_progress",
            }
        )
        .execute()
        .data[0]
    )
    start_band = profile.get("cefr_level") or "B1"
    await _generate_items(
        supabase, user_id, str(assessment["id"]), start_band, count=5, offset=0, language=codigo
    )
    return _assessment_payload(supabase, str(assessment["id"]), user_id)


async def _generate_items(
    supabase: Client,
    user_id: str,
    assessment_id: str,
    band: str,
    count: int,
    offset: int,
    language: str = "en",
) -> None:
    alvo = languages.idioma(language)
    nome = alvo.nome if alvo else "Ingles"
    nativo = alvo.nativo if alvo else "English"
    pedido = (
        # O idioma vai explicito e duas vezes (nome em portugues e endonimo):
        # so o codigo ISO fazia o modelo escrever em ingles de qualquer jeito,
        # que e o idioma em que ele viu mais itens de nivelamento.
        f"IDIOMA AVALIADO: {nome} ({nativo}). O enunciado, o contexto e as "
        f"alternativas sao em {nome}; so a explicacao e em portugues do Brasil.\n"
        f"Gere {count} itens de nivel {band} para um profissional de tecnologia "
        "brasileiro. Varie a habilidade entre eles.\n"
        # O catalogo vai no pedido para o topico nao sair escrito livre: cada
        # grafia diferente abriria uma linha nova no placar por topico.
        "TOPICOS POR HABILIDADE:\n"
        + "\n".join(f"- {h}: {', '.join(t)}" for h, t in treino.TOPICOS.items())
    )

    rows: list[dict[str, Any]] = []
    # Descartar item impossivel abre a chance de um lote inteiro cair, e um
    # lote vazio trava a tela em "Preparando as proximas perguntas...". Uma
    # segunda tentativa custa uma chamada e evita o beco sem saida.
    for tentativa in range(2):
        result = await generate_json(SYSTEM_PROMPT, pedido, ITEMS_SCHEMA)
        rows = _linhas_de_itens(
            result.content.get("itens") or [], assessment_id, user_id, band, offset, language
        )
        if rows or tentativa:
            break

    if rows:
        supabase.table("pathr_english_item").insert(rows).execute()


def _linhas_de_itens(
    itens: list[Any],
    assessment_id: str,
    user_id: str,
    band: str,
    offset: int,
    language: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Os itens do modelo virados em linhas da tabela, sem os que nao servem.

    Item malformado (alternativas de menos, indice fora da faixa) sempre caiu
    aqui. O que passou a cair tambem e o item que cobra uma midia que o app
    nao tem — ver `_respondivel`.
    """
    rows: list[dict[str, Any]] = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        options = [str(option).strip() for option in (item.get("alternativas") or []) if str(option).strip()]
        try:
            correct = int(item.get("correta"))
        except (TypeError, ValueError):
            continue
        prompt = str(item.get("enunciado") or "").strip()
        if not prompt or len(options) != 4 or not 0 <= correct <= 3:
            continue
        skill = str(item.get("habilidade") or "grammar").strip().lower()
        if skill not in SKILLS:
            skill = "grammar"
        contexto = str(item.get("contexto") or "").strip()[:1000]
        if not _respondivel(prompt, skill, contexto):
            continue
        item_band = str(item.get("banda") or band).strip().upper()
        rows.append(
            {
                "assessment_id": assessment_id,
                "user_id": user_id,
                "skill": skill,
                "type": "mcq",
                "cefr_band": item_band if item_band in BANDS else band,
                "prompt": prompt[:2000],
                "context": contexto or None,
                "options": options,
                "correct": {"index": correct},
                "feedback": str(item.get("explicacao") or "").strip()[:1500],
                # A posicao vem da linha aceita, e nao do indice cru: com item
                # descartado no meio, o indice cru abriria buracos e, na
                # segunda tentativa, repetiria ordem ja usada.
                "order_index": offset + len(rows),
                # Sem topico o nivelamento nao somava no placar por topico, e
                # sem idioma a resposta nao entrava no nivel por habilidade.
                "topic": treino.canonico(item.get("topico"), skill, "geral"),
                "language": language,
                "origin": "nivelamento",
            }
        )
    return rows


def _assessment_payload(supabase: Client, assessment_id: str, user_id: str) -> dict[str, Any]:
    """O nivelamento com os itens ainda não respondidos — sem gabarito."""
    rows = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("id", assessment_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nivelamento não encontrado.")
    items = (
        supabase.table("pathr_english_item")
        .select("id,skill,type,cefr_band,prompt,context,options,order_index,is_correct")
        .eq("assessment_id", assessment_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    pendentes = [item for item in items if item.get("is_correct") is None]
    return {**rows[0], "items": _sem_impossiveis(supabase, pendentes)}


def _sem_impossiveis(supabase: Client, pendentes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Descarta item que cobra o que não está nele, e APAGA a linha.

    A guarda de `_respondivel` filtra na geração, mas item ruim gerado antes
    dela continuava gravado e chegava à tela — foi o que aconteceu: a correção
    subiu e a pessoa seguiu vendo "Based on the audio…" sem áudio nenhum,
    porque aquele item já estava no banco.

    Apagar, e não só esconder: o item pendente entra na contagem que decide
    quando gerar o próximo lote, então escondê-lo travaria o teste esperando
    resposta de algo que a tela nunca mostra.

    Best-effort na escrita — não poder apagar não pode impedir de esconder.
    """
    bons, lixo = [], []
    for item in pendentes:
        if _respondivel(
            str(item.get("prompt") or ""),
            str(item.get("skill") or ""),
            str(item.get("context") or ""),
        ):
            bons.append(item)
        else:
            lixo.append(str(item["id"]))
    if lixo:
        try:
            supabase.table("pathr_english_item").delete().in_("id", lixo).execute()
        except Exception:  # noqa: BLE001
            pass
    return bons


@router.get("/improvements")
def improvements(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    # Por último: os testes chamam esta função por posição.
    language: str = "en",
):
    """O que a pessoa errou e ainda não recuperou, do mais atrasado ao mais
    recente.

    É a contrapartida do nivelamento: a nota diz onde ela está, isto diz o que
    fazer a respeito. Ordena por vencimento porque o que venceu há mais tempo
    é o que corre mais risco de virar lacuna permanente.

    Filtrada por idioma: sem o filtro, a lista de quem estuda inglês e
    espanhol misturava os dois, e o treino de espanhol cobraria erro de inglês.
    """
    linhas = (
        supabase.table("pathr_review_item")
        .select("id,front,back,due_at,lapses,repetitions,skill,topic")
        .eq("user_id", str(current_user["id"]))
        .eq("kind", "language")
        .eq("language", _idioma_valido(language))
        .order("due_at")
        .limit(50)
        .execute()
        .data
        or []
    )
    agora = _now().isoformat()
    return {
        "items": linhas,
        # Quantos já venceram — é este número que a tela mostra, e não o total:
        # ponto agendado para semana que vem não é dívida de hoje.
        "due_count": sum(1 for linha in linhas if str(linha.get("due_at") or "") <= agora),
    }


@router.get("/assessment/active")
def active_assessment(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O nivelamento em andamento deste idioma, ou `null`.

    O id do nivelamento só existia na memória da tela: trocar de aba ou dar
    F5 apagava o caminho de volta, e o progresso ficava gravado no banco sem
    nada que soubesse alcançá-lo. Com esta rota a tela pergunta "há um teste
    aberto?" e oferece a retomada — e o `answered_count` que vem junto é o que
    ela usa para dizer quanto já foi respondido.

    Declarada ANTES de `/assessment/{assessment_id}`: as rotas são casadas em
    ordem, e o caminho variável engoliria "active" como se fosse um id.
    """
    codigo = _idioma_valido(language)
    rows = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .eq("language", codigo)
        .eq("status", "in_progress")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    return _assessment_payload(supabase, str(rows[0]["id"]), str(current_user["id"]))


@router.get("/assessment/{assessment_id}")
def get_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return _assessment_payload(supabase, assessment_id, str(current_user["id"]))


@router.post("/assessment/{assessment_id}/answer")
async def answer_assessment(
    assessment_id: str,
    payload: AnswerItem,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    # Por ULTIMO e com default. O FastAPI injeta BackgroundTasks pelo tipo, nao
    # pela posicao, entao pôr no meio so quebraria quem chama esta funcao
    # direto -- os testes, que a exercitam sem servidor.
    background: BackgroundTasks = None,
):
    """Responde um item e devolve o gabarito NA HORA.

    A geração do próximo lote sai da requisição. Antes ela acontecia aqui
    dentro, e a cada cinco respostas a pessoa esperava uma chamada de LLM
    inteira — 2 a 15 segundos de "Carregando…" para saber se acertou uma
    alternativa que o servidor já tinha conferido em milissegundos.

    O lote é encomendado quando ainda restam DOIS itens, e não um: gerar com
    um item de folga dá tempo de a chamada terminar enquanto a pessoa lê o
    penúltimo. Só quando não sobra item nenhum a geração volta a ser síncrona,
    porque aí não há o que mostrar enquanto se espera.
    """
    user_id = str(current_user["id"])
    items = (
        supabase.table("pathr_english_item")
        .select("*")
        .eq("id", payload.item_id)
        .eq("user_id", user_id)
        .eq("assessment_id", assessment_id)
        .limit(1)
        .execute()
        .data
    )
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado.")
    item = items[0]
    expected = int((item.get("correct") or {}).get("index", -1))

    if item.get("is_correct") is not None:
        # Já respondido: devolve o MESMO desfecho em vez de 409.
        #
        # O 409 criava um beco sem saída real. A gravação acontece antes da
        # resposta chegar ao navegador, então bastava a conexão cair, a aba
        # trocar ou a pessoa clicar duas vezes para o item ficar respondido no
        # servidor e sem gabarito na tela — e o clique seguinte só dizia "item
        # já respondido", sem gabarito e sem "Próxima". O nivelamento travava
        # ali, com o progresso preso.
        #
        # Repetir o desfecho gravado não inventa nem perde nada: a resposta
        # aceita continua sendo a primeira, e uma segunda escolha diferente é
        # ignorada em vez de sobrescrever.
        return _resultado_gravado(supabase, current_user, assessment_id, item, expected)
    is_correct = payload.answer == expected

    supabase.table("pathr_english_item").update(
        {
            "user_answer": str(payload.answer),
            "is_correct": is_correct,
            "answered_at": _now().isoformat(),
        }
    ).eq("id", item["id"]).execute()

    if not is_correct:
        _guarda_ponto_de_melhora(supabase, user_id, item)

    assessment = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("id", assessment_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data[0]
    )
    answered = int(assessment.get("answered_count") or 0) + 1
    correct_count = int(assessment.get("correct_count") or 0) + int(is_correct)
    supabase.table("pathr_english_assessment").update(
        {"answered_count": answered, "correct_count": correct_count}
    ).eq("id", assessment_id).execute()

    remaining = (
        supabase.table("pathr_english_item")
        .select("id", count="exact")
        .eq("assessment_id", assessment_id)
        .is_("is_correct", "null")
        .execute()
    )
    pending = remaining.count or 0

    finished = answered >= int(assessment.get("item_count") or 20)
    if finished:
        result = _finish_assessment(supabase, current_user, assessment_id, answered, correct_count)
        return {"is_correct": is_correct, "correct_index": expected,
                "explanation": item.get("feedback"), "finished": True, "result": result}

    # Acertou -> sobe a banda; errou -> desce. É isto que faz o teste
    # convergir: cada resposta move o alvo em direção ao nível real.
    if pending <= 2:
        band = _next_band(item.get("cefr_band") or "B1", is_correct)
        # O idioma vem da tentativa, e nao de um parametro: trocar de idioma no
        # meio de um nivelamento invalidaria as respostas ja dadas.
        idioma_da_tentativa = assessment.get("language") or "en"
        if pending == 0:
            # Nao ha proximo item para mostrar. Aqui esperar e o unico caminho
            # honesto -- devolver antes deixaria a tela sem pergunta nenhuma.
            await _generate_items(
                supabase, user_id, assessment_id, band, 5, answered, idioma_da_tentativa
            )
        elif background is None:
            # Chamada direta, sem o ciclo de requisicao do FastAPI (teste). Nao
            # ha fila de tarefas para onde mandar, e gerar aqui gastaria uma
            # chamada de IA num caminho que nao precisa dela.
            pass
        else:
            background.add_task(
                _generate_items,
                supabase,
                user_id,
                assessment_id,
                band,
                5,
                answered,
                idioma_da_tentativa,
            )

    return {
        "is_correct": is_correct,
        "correct_index": expected,
        "explanation": item.get("feedback"),
        "finished": False,
        "answered": answered,
        "total": int(assessment.get("item_count") or 20),
    }


def _guarda_ponto_de_melhora(supabase: Client, user_id: str, item: dict[str, Any]) -> None:
    """O item errado vira um ponto de melhora, vencendo hoje.

    Errar era o único desfecho que o nivelamento descartava: o acerto virava
    nota e o erro não virava nada, então a lacuna que o teste acabou de provar
    era justamente a que ninguém guardava. O quiz técnico já reciclava o erro
    em `pathr_review_item` (ver `routers/quizzes.py`); aqui é a mesma mesa e o
    mesmo SM-2, com `kind="language"` para separar o que é de idioma.

    Best-effort, como o `log_activity`: perder um ponto de melhora custa uma
    repetição; derrubar a correção que a pessoa acabou de responder custa a
    resposta dela.
    """
    try:
        enunciado = str(item.get("prompt") or "").strip()
        if not enunciado:
            return
        if _melhora_ja_pendente(supabase, user_id, enunciado):
            return
        alternativas = item.get("options") or []
        indice = int((item.get("correct") or {}).get("index", -1))
        certa = str(alternativas[indice]) if 0 <= indice < len(alternativas) else ""
        supabase.table("pathr_review_item").insert(
            {
                "user_id": user_id,
                "kind": "language",
                # Idioma, habilidade, tópico e banda: é o que deixa o treino
                # diário devolver este ponto no idioma certo e no formato certo.
                "language": item.get("language"),
                "skill": item.get("skill"),
                "topic": item.get("topic"),
                "band": item.get("cefr_band"),
                "front": enunciado[:2000],
                "back": " ".join(
                    parte for parte in [certa, str(item.get("feedback") or "")] if parte
                )[:2000],
                # Vence agora: é uma lacuna confirmada, não uma suspeita.
                "due_at": _now().isoformat(),
                "lapses": 1,
            }
        ).execute()
    except Exception:  # noqa: BLE001
        return


def _melhora_ja_pendente(supabase: Client, user_id: str, enunciado: str) -> bool:
    """Este ponto já está na fila?

    Sem a checagem, refazer o nivelamento e errar a mesma ideia criaria uma
    segunda linha, e a pessoa reveria a mesma lacuna duas vezes em paralelo —
    o que o docstring de `PathrReviewItem` pede para evitar. A comparação usa
    a chave normalizada de `services/review.py`, a mesma do quiz.
    """
    chave = review.concept_key(enunciado)
    existentes = (
        supabase.table("pathr_review_item")
        .select("front")
        .eq("user_id", user_id)
        .eq("kind", "language")
        .limit(200)
        .execute()
        .data
        or []
    )
    return any(review.concept_key(linha.get("front")) == chave for linha in existentes)


def _resultado_gravado(
    supabase: Client,
    user: dict,
    assessment_id: str,
    item: dict[str, Any],
    expected: int,
) -> dict[str, Any]:
    """O desfecho de um item que JÁ foi respondido, no formato que a tela lê.

    Só relê o que está gravado: não conta a resposta de novo, não mexe na
    banda do próximo lote e não fecha o nivelamento por conta própria. Se o
    nivelamento já terminou, devolve o resultado dele junto — é o que a tela
    precisa para mostrar o nível em vez de pedir a próxima pergunta.
    """
    assessment = (
        supabase.table("pathr_english_assessment")
        .select("*")
        .eq("id", assessment_id)
        .eq("user_id", str(user["id"]))
        .limit(1)
        .execute()
        .data[0]
    )
    answered = int(assessment.get("answered_count") or 0)
    total = int(assessment.get("item_count") or 20)
    base = {
        "is_correct": bool(item.get("is_correct")),
        "correct_index": expected,
        "explanation": item.get("feedback"),
    }
    if assessment.get("status") == "done":
        return {
            **base,
            "finished": True,
            "result": _com_exame(_perfil_do_idioma(supabase, user, assessment)),
        }
    return {**base, "finished": False, "answered": answered, "total": total}


def _perfil_do_idioma(supabase: Client, user: dict, assessment: dict[str, Any]) -> dict[str, Any]:
    """O perfil do idioma em que este nivelamento foi feito."""
    return _profile(supabase, str(user["id"]), assessment.get("language") or "en")


def _next_band(current: str, went_up: bool) -> str:
    index = BANDS.index(current) if current in BANDS else 2
    return BANDS[max(0, min(len(BANDS) - 1, index + (1 if went_up else -1)))]


def _finish_assessment(
    supabase: Client, user: dict, assessment_id: str, answered: int, correct_count: int
) -> dict[str, Any]:
    """Fecha o nivelamento e grava o nível resultante.

    O nível sai da banda MÉDIA dos itens acertados, não do percentual de
    acerto: acertar 90% de itens A2 não faz ninguém B2, e é exatamente esse o
    erro que um teste não adaptativo comete.
    """
    items = (
        supabase.table("pathr_english_item")
        .select("cefr_band,is_correct,skill")
        .eq("assessment_id", assessment_id)
        .execute()
        .data
        or []
    )
    # De qual idioma foi este nivelamento. Vem da tentativa, e nao de um
    # parametro, porque o resultado pertence ao idioma em que foi medido.
    tentativa = (
        supabase.table("pathr_english_assessment")
        .select("language")
        .eq("id", assessment_id)
        .limit(1)
        .execute()
        .data
    )
    idioma_da_tentativa = (tentativa[0].get("language") if tentativa else None) or "en"
    correct_bands = [
        BANDS.index(item["cefr_band"])
        for item in items
        if item.get("is_correct") and item.get("cefr_band") in BANDS
    ]
    level = BANDS[round(sum(correct_bands) / len(correct_bands))] if correct_bands else "A1"

    sub_scores: dict[str, Any] = {}
    for skill in {item.get("skill") for item in items if item.get("skill")}:
        of_skill = [item for item in items if item.get("skill") == skill]
        hits = sum(1 for item in of_skill if item.get("is_correct"))
        sub_scores[skill] = round(100 * hits / len(of_skill))

    supabase.table("pathr_english_assessment").update(
        {
            "status": "done",
            "cefr_result": level,
            "sub_scores": sub_scores,
            "finished_at": _now().isoformat(),
        }
    ).eq("id", assessment_id).execute()

    # O nivel medido vai para a linha DAQUELE idioma. Sem o filtro, terminar
    # o nivelamento de espanhol sobrescreveria o nivel de ingles -- as duas
    # linhas tem o mesmo user_id.
    supabase.table("pathr_english_profile").update(
        {
            "cefr_level": level,
            "sub_scores": sub_scores,
            "last_assessment_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
        }
    ).eq("user_id", str(user["id"])).eq("language", idioma_da_tentativa).execute()

    log_activity(
        supabase,
        user=user,
        kind="english_assessment",
        title=f"Nivelamento concluído — {level}",
        ref_id=assessment_id,
        minutes=12,
        detail={"level": level, "correct": correct_count, "answered": answered},
    )
    return {"cefr_level": level, "sub_scores": sub_scores,
            "correct": correct_count, "answered": answered}


@router.get("/vocab")
def list_vocab(
    language: str = "en",
    due_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Baralho de vocabulário. `due_only` traz só o que vence hoje — é a
    única visão que importa numa sessão de revisão."""
    query = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("user_id", str(current_user["id"]))
        .eq("language", _idioma_valido(language))
    )
    if due_only:
        query = query.lte("due_at", _now().isoformat())
    return query.order("due_at").limit(max(1, min(limit, 200))).execute().data or []


class VocabReview(BaseModel):
    # Qualidade da lembrança, na escala do SM-2: 0 esqueci, 5 lembrei na hora.
    quality: int = Field(ge=0, le=5)


@router.post("/vocab/{vocab_id}/review")
def review_vocab(
    vocab_id: str,
    payload: VocabReview,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Aplica o SM-2 e reagenda o cartão.

    SM-2 e não um intervalo fixo porque o que consolida vocabulário é revisar
    ANTES de esquecer, e esse ponto é diferente para cada palavra e cada
    pessoa. Um erro (quality < 3) zera o intervalo: a palavra volta hoje.

    O cálculo mora em services/review.py desde que o quiz passou a reciclar
    erro pelo mesmo algoritmo. Duas cópias divergiriam na primeira correção
    feita só de um lado — e as duas tabelas têm os mesmos campos.
    """
    rows = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("id", vocab_id)
        .eq("user_id", str(current_user["id"]))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartão não encontrado.")
    card = rows[0]

    # `pathr_english_vocab` não tem coluna `lapses`; o agendador devolve o
    # campo só no erro, e mandá-lo ao PostgREST daria erro de coluna
    # inexistente. As outras chaves são as mesmas nas duas tabelas.
    proximo = review.schedule(card, payload.quality)
    proximo.pop("lapses", None)
    proximo.pop("last_reviewed_at", None)

    updated = (
        supabase.table("pathr_english_vocab")
        .update(proximo)
        .eq("id", vocab_id)
        .execute()
        .data[0]
    )
    return updated

# ---------------------------------------------------------------------------
# A palavra que a pessoa nao sabia
# ---------------------------------------------------------------------------

_TERMO_VALIDO = re.compile(r"^[^\W\d_][\w'’-]{0,59}$", re.UNICODE)

_LOOKUP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "traducao": {"type": "STRING"},
        "sinonimos": {"type": "ARRAY", "items": {"type": "STRING"}},
        "definicao": {"type": "STRING"},
        "exemplo": {"type": "STRING"},
        "fonetica": {"type": "STRING"},
        "cefr": {"type": "STRING"},
    },
    "required": ["traducao", "sinonimos", "definicao"],
}


class VocabLookup(BaseModel):
    term: str = Field(min_length=1, max_length=60)
    language: str = "en"
    # A frase em que a palavra apareceu. "Book" num e-mail de reserva nao e o
    # "book" de uma estante, e sem a frase o modelo escolhe a acepcao mais
    # comum -- que e justamente a que a pessoa ja conhecia.
    context: Optional[str] = Field(default=None, max_length=600)


@router.post("/lookup")
async def lookup_word(
    payload: VocabLookup,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O que a palavra quer dizer — e o registro de que ela foi consultada.

    Duas coisas ao mesmo tempo, e a segunda é a que importa a longo prazo.

    A primeira é responder à pessoa: durante o nivelamento, travar numa
    palavra faz o item medir vocabulário quando queria medir compreensão, e a
    saída honesta de quem não sabe é chutar. Poder olhar troca o chute por
    uma leitura.

    A segunda é que **consultar é evidência**. É a única vez em que a pessoa
    diz, sem ser perguntada, "esta eu não tenho". O termo entra no baralho
    vencendo HOJE, e quem já o tinha leva o cartão de volta ao início — como
    um erro de revisão, porque foi isso que aconteceu: a palavra estava
    agendada como sabida e não estava. É assim que o app aprende o que ainda
    falta sem precisar de um teste a mais.
    """
    termo = payload.term.strip()
    if not _TERMO_VALIDO.match(termo):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecione uma palavra para consultar.",
        )

    idioma = _idioma_valido(payload.language)
    user_id = str(current_user["id"])

    # Já consultada antes: o cartão guarda o que a consulta respondeu. Sem
    # isto, reabrir a mesma palavra refazia a chamada à IA e ao DeepL — a mesma
    # espera de segundos para uma resposta que o banco já tinha.
    guardado = _cartao_ja_consultado(supabase, user_id, idioma, termo)
    if guardado:
        significado = {
            "term": termo,
            "translation": guardado.get("translation"),
            # A tabela não guarda sinônimos; perder só eles é melhor que esperar.
            "synonyms": [],
            "definition": guardado.get("definition"),
            "example": guardado.get("example"),
            "phonetic": guardado.get("phonetic"),
            "cefr_band": guardado.get("cefr_band") or "B1",
        }
        significado["card"] = _registra_consulta(
            supabase, user_id, idioma, {**significado, "term": guardado["term"]}
        )
        return significado

    alvo = languages.idioma(idioma)
    nome = alvo.nome if alvo else "Ingles"

    contexto = (payload.context or "").strip()
    pedido = (
        f"IDIOMA: {nome}. Explique a palavra ou expressao \"{termo}\" para um "
        "profissional de tecnologia brasileiro.\n"
        "- traducao: a traducao em portugues do Brasil, uma a tres palavras.\n"
        "- sinonimos: de dois a quatro sinonimos NO IDIOMA ORIGINAL.\n"
        "- definicao: uma frase curta em portugues do Brasil.\n"
        "- exemplo: uma frase no idioma original usando a palavra.\n"
        "- fonetica: a pronuncia em AFI, se souber.\n"
        "- cefr: a faixa CEFR da palavra (A1 a C2).\n"
        "- termos de programacao ficam em ingles na traducao quando usados no "
        "sentido tecnico (\"branch\" do git, e nao \"ramo\"); no sentido comum, "
        f"traduza: {', '.join(traducao.TERMOS_UNIVERSAIS)}.\n"
        + (f"\nEla apareceu nesta frase, use a acepcao QUE CABE AQUI:\n{contexto}\n" if contexto else "")
    )

    # O DeepL traduz e o modelo explica, AO MESMO TEMPO: em sequência, a
    # consulta somaria as duas esperas. A tradução do DeepL tem preferência
    # (ver services/traducao.py); a do modelo é a reserva.
    pelo_deepl = asyncio.create_task(traducao.traduzir([termo], idioma, contexto=contexto or None))
    pela_ia = asyncio.create_task(_explicacao_da_ia(pedido))
    traduzidas = await pelo_deepl
    traducao_deepl = traduzidas[0] if traduzidas else None
    try:
        # Com a tradução do DeepL em mãos, a explicação é complemento: a IA tem
        # alguns segundos, não o orçamento inteiro da rotação. Era essa espera
        # — um provedor lento, depois outro — que deixava a consulta travada.
        conteudo = await asyncio.wait_for(
            pela_ia, timeout=_ESPERA_DA_EXPLICACAO if traducao_deepl else None
        )
    except asyncio.TimeoutError:
        conteudo = {}

    if not conteudo and not traducao_deepl:
        # Sem consulta a pessoa perde a ajuda, mas nao perde o nivelamento: a
        # tela mostra que nao deu e o item continua respondivel. Levantar aqui
        # transformaria uma consulta opcional num erro no meio do teste.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não consegui consultar esta palavra agora.",
        )

    significado = {
        "term": termo,
        # Com a IA fora do ar e o DeepL de pé, a pessoa ainda leva a tradução —
        # antes, a consulta inteira caía.
        "translation": traducao_deepl or str(conteudo.get("traducao") or "").strip() or None,
        "synonyms": [
            str(item).strip()
            for item in (conteudo.get("sinonimos") or [])
            if str(item).strip()
        ][:4],
        "definition": str(conteudo.get("definicao") or "").strip() or None,
        "example": str(conteudo.get("exemplo") or "").strip() or None,
        "phonetic": str(conteudo.get("fonetica") or "").strip() or None,
        "cefr_band": str(conteudo.get("cefr") or "B1").strip().upper()[:2] or "B1",
    }

    significado["card"] = _registra_consulta(supabase, user_id, idioma, significado)
    return significado


_ESPERA_DA_EXPLICACAO = 6.0


async def _explicacao_da_ia(pedido: str) -> dict[str, Any]:
    try:
        resultado = await generate_json(SYSTEM_PROMPT, pedido, _LOOKUP_SCHEMA)
        return resultado.content or {}
    except AiProviderError:
        return {}


def _cartao_ja_consultado(
    supabase: Client, user_id: str, idioma: str, termo: str
) -> Optional[dict[str, Any]]:
    """O cartão da palavra, se ele já tem tradução. "Book" no começo da frase e
    "book" no meio são a mesma consulta."""
    variantes = list({termo, termo.lower(), termo[:1].upper() + termo[1:].lower()})
    linhas = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("user_id", user_id)
        .eq("language", idioma)
        .in_("term", variantes)
        .limit(1)
        .execute()
        .data
        or []
    )
    return linhas[0] if linhas and linhas[0].get("translation") else None


def _registra_consulta(
    supabase: Client, user_id: str, idioma: str, significado: dict[str, Any]
) -> dict[str, Any]:
    """Põe o termo no baralho vencendo hoje. Já estava lá? Volta ao início.

    `quality=0` no SM-2 é o erro que zera o intervalo. É a leitura certa do
    que aconteceu: o cartão estava agendado para daqui a semanas porque o
    app supunha a palavra sabida, e a consulta desmentiu a suposição.
    """
    existentes = (
        supabase.table("pathr_english_vocab")
        .select("*")
        .eq("user_id", user_id)
        .eq("term", significado["term"])
        .limit(1)
        .execute()
        .data
        or []
    )

    if existentes:
        card = existentes[0]
        proximo = review.schedule(card, 0)
        # A tabela de vocabulário não tem estas colunas; mandá-las ao
        # PostgREST daria erro de coluna inexistente. Mesmo motivo de
        # `review_vocab`.
        proximo.pop("lapses", None)
        proximo.pop("last_reviewed_at", None)
        atualizado = (
            supabase.table("pathr_english_vocab")
            .update(proximo)
            .eq("id", card["id"])
            .execute()
            .data
        )
        return (atualizado or [card])[0]

    linha = {
        "user_id": user_id,
        "language": idioma,
        "term": significado["term"],
        "translation": significado["translation"],
        "definition": significado["definition"],
        "example": significado["example"],
        "phonetic": significado["phonetic"],
        "cefr_band": significado["cefr_band"],
        # De onde veio. Um cartão de consulta conta uma história diferente de
        # um que nasceu de um item errado, e vale poder separá-los depois.
        "source": "consulta",
        "due_at": _now().isoformat(),
    }
    gravado = supabase.table("pathr_english_vocab").insert(linha).execute().data
    return (gravado or [linha])[0]

