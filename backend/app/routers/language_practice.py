"""O treino diário de idioma e o nível por habilidade.

A regra de O QUE treinar e COMO corrigir mora em services/treino_idioma.py; a
de COMO medir o nível, em services/proficiencia_idioma.py. Aqui fica o que fala
com o banco e com o modelo.

## Um treino por dia, e ele persiste

O treino do dia é criado na primeira abertura e fica gravado: sair no meio e
voltar retoma no exercício seguinte, em qualquer aparelho. O índice único
(usuário, idioma, dia) da migration 0017 é o que impede duas abas de gerarem
dois treinos.

## Geração em lotes, sem a pessoa esperar o treino inteiro

Doze exercícios numa chamada de IA levam de 20 a 40 segundos. Os quatro
primeiros saem na hora e o resto é gerado em segundo plano enquanto a pessoa
responde — o mesmo desenho do nivelamento. Se o segundo plano falhar, a tela
pede de novo e a geração acontece ali, porque só esperar é a saída honesta
quando não há o que mostrar.
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from app.ai_providers import AiProviderError, generate_json
from app.database import get_supabase
from app.deps import get_current_user
from app.services import languages, review
from app.services import proficiencia_idioma as proficiencia
from app.services import traducao
from app.services import treino_idioma as treino
from app.services.progress import log_activity

router = APIRouter(prefix="/languages", tags=["idioma"])
logger = logging.getLogger("pathr.language_practice")

HABILIDADES = tuple(treino.FORMATOS)
_PRIMEIRO_LOTE = 4
_LOTE = 6
_TEMPO_POR_PROVEDOR = 12

PRACTICE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "itens": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "indice": {"type": "INTEGER"},
                    "tipo": {"type": "STRING"},
                    "topico": {"type": "STRING"},
                    "enunciado": {"type": "STRING"},
                    "frase": {"type": "STRING"},
                    "aceitas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "texto": {"type": "STRING"},
                    "traducao": {"type": "STRING"},
                    "emoji": {"type": "STRING"},
                    "alternativas": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correta": {"type": "INTEGER"},
                    "pares": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {"a": {"type": "STRING"}, "b": {"type": "STRING"}},
                            "required": ["a", "b"],
                        },
                    },
                    "explicacao": {"type": "STRING"},
                },
                "required": ["indice", "tipo", "explicacao"],
            },
        }
    },
    "required": ["itens"],
}

PRACTICE_PROMPT = """Você escreve exercícios para o treino diário de idioma de um profissional de tecnologia brasileiro.

REGRAS GERAIS
1. Frases, textos, alternativas e pares ficam no IDIOMA ESTUDADO. O enunciado
   curto e a explicação ficam em português do Brasil. A explicação ENSINA: por
   que a resposta certa está certa e por que a errada mais tentadora soa errada
   para um nativo — em duas ou três frases.
2. Situações reais: reunião, e-mail, code review, entrevista, viagem, rotina.
3. Respeite o tipo, a habilidade, o tópico e a banda CEFR de cada pedido, e
   devolva o MESMO `indice` do pedido. A banda é a dificuldade real.
4. Quando o pedido trouxer ERRO ANTERIOR, cobre a MESMA regra numa situação
   NOVA: outro assunto, outras palavras, outra frase. É proibido reaproveitar
   a frase do erro, mesmo corrigida — "We discussed about the deadline" não
   pode voltar como "We discussed the deadline"; volta como "Let's discuss
   the budget tomorrow". Se decorar a frase bastasse, o exercício não mediria
   se a regra foi aprendida. Vale também para pergunta de múltipla escolha:
   não reaproveite a pergunta, as alternativas NEM a resposta certa do erro —
   escreva outra situação cujas alternativas testem a mesma regra.
5. As alternativas erradas são erros que brasileiros realmente cometem (falso
   cognato, tradução literal, preposição, tempo verbal) — não absurdos.
6. Na tradução e na explicação, termos de programação ficam em inglês quando
   usados no SENTIDO TÉCNICO, como se fala num time brasileiro: "fiz o merge da
   branch", nunca "fiz a fusão do ramo". No sentido comum, traduza: "release a
   new phone" é "lançar um celular", "put it on the stack" é "pôr na pilha".
   Os termos: {termos}.

POR TIPO (use SÓ os campos do tipo)
- mcq: enunciado com todo o contexto necessário; alternativas (4); correta (0 a 3).
- gap: frase com EXATAMENTE uma lacuna escrita ___ ; enunciado ("Complete com…");
  alternativas (4) para a lacuna; correta.
- reorder: frase = a frase correta, de 4 a 12 palavras, pontuação colada à
  palavra; aceitas = outras ordens igualmente corretas (se houver); traducao
  em português; enunciado "Monte a frase".
- match: pares = 4 a 6 objetos {a: termo no idioma, b: tradução em português},
  todos do tópico; enunciado "Associe".
- listening: texto = o que será FALADO em voz alta (uma fala curta, ou um
  diálogo com "Nome: fala", uma fala por linha), COMPLETO e sem lacuna — nunca
  "___": a voz leria o símbolo e a pessoa não ouviria a palavra; enunciado =
  pergunta que só se responde ouvindo o texto; alternativas (4); correta.
- dictation: texto = UMA frase de 5 a 14 palavras (conte: acima de 20 é
  recusada, ninguém escreve de ouvido uma frase desse tamanho); traducao;
  enunciado "Escreva o que ouvir".
- image: emoji = UM emoji que represente sem ambiguidade um SUBSTANTIVO
  CONCRETO (objeto, comida, animal, lugar, transporte, profissão, clima) —
  nunca verbo, sentimento ou ideia abstrata; enunciado "Qual é a palavra?";
  alternativas (4) no idioma, todas substantivos; correta.
- speaking: texto = UMA frase de 5 a 14 palavras, natural de dizer em voz alta
  (acima de 20 é recusada); traducao; enunciado "Leia em voz alta".

Todo item leva `topico` (o tópico pedido) e `explicacao`. Responda só o JSON."""

# A lista de termos vem de services/traducao.py, a mesma do glossário do DeepL:
# a tradução do modelo (reserva) e a do DeepL preservam os mesmos termos.
# `replace` e não `format`: o prompt tem chaves literais ({a: …, b: …}).
PRACTICE_PROMPT = PRACTICE_PROMPT.replace("{termos}", ", ".join(traducao.TERMOS_UNIVERSAIS))


class PracticeAnswer(BaseModel):
    item_id: str
    answer: dict[str, Any]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _idioma(language: str) -> str:
    codigo = (language or "").strip().lower()
    if not languages.existe(codigo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Idioma '{language}' não está no catálogo."
        )
    return codigo


def _hoje(user: dict[str, Any]) -> date:
    """O dia DA PESSOA. O servidor roda em UTC, e às 22h em São Paulo já é
    amanhã em UTC — o treino de hoje não pode virar o de amanhã às 21h."""
    try:
        fuso = ZoneInfo(user.get("timezone_name") or "America/Sao_Paulo")
    except (ZoneInfoNotFoundError, ValueError):
        fuso = ZoneInfo("America/Sao_Paulo")
    return _agora().astimezone(fuso).date()


def _perfil(supabase: Client, user_id: str, language: str) -> dict[str, Any]:
    linhas = (
        supabase.table("pathr_english_profile")
        .select("cefr_level,daily_goal_min,enabled")
        .eq("user_id", user_id)
        .eq("language", language)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else {}


def _quadro(supabase: Client, user_id: str, language: str) -> dict[str, Any]:
    respondidos = (
        supabase.table("pathr_english_item")
        .select("skill,topic,cefr_band,type,is_correct,skipped,answered_at")
        .eq("user_id", user_id)
        .eq("language", language)
        .not_.is_("is_correct", "null")
        .order("answered_at", desc=True)
        # A meia-vida de 30 dias já apaga quase tudo além disso.
        .limit(800)
        .execute()
        .data
        or []
    )
    perfil = _perfil(supabase, user_id, language)
    return proficiencia.quadro(
        treino.respostas_para_estimativa(respondidos),
        HABILIDADES,
        nivel_medido=perfil.get("cefr_level"),
    )


def _pontos_vencidos(supabase: Client, user_id: str, language: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_review_item")
        .select("id,front,back,skill,topic,band,repetitions")
        .eq("user_id", user_id)
        .eq("kind", "language")
        .eq("language", language)
        .lte("due_at", _agora().isoformat())
        .order("due_at")
        .limit(30)
        .execute()
        .data
        or []
    )


# ---------------------------------------------------------------------------
# Nível por habilidade
# ---------------------------------------------------------------------------


@router.get("/skills")
def skills(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O nível de cada habilidade, com a incerteza, e o placar por tópico.

    Calculado na hora a partir das respostas, e não gravado: um número gravado
    fica velho no primeiro exercício seguinte, e recalcular custa uma consulta.
    """
    codigo = _idioma(language)
    return _quadro(supabase, str(current_user["id"]), codigo)


# ---------------------------------------------------------------------------
# Treino do dia
# ---------------------------------------------------------------------------


def _sessao_de_hoje(supabase: Client, user_id: str, language: str, dia: date) -> Optional[dict]:
    linhas = (
        supabase.table("pathr_english_session")
        .select("*")
        .eq("user_id", user_id)
        .eq("language", language)
        .eq("mode", "treino")
        .eq("practice_day", dia.isoformat())
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def _sessao(supabase: Client, session_id: str, user_id: str) -> dict[str, Any]:
    linhas = (
        supabase.table("pathr_english_session")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .eq("mode", "treino")
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treino não encontrado.")
    return linhas[0]


def _itens(supabase: Client, session_id: str) -> list[dict[str, Any]]:
    return (
        supabase.table("pathr_english_item")
        .select("id,type,skill,topic,cefr_band,origin,payload,order_index,is_correct,skipped")
        .eq("session_id", session_id)
        .order("order_index")
        .execute()
        .data
        or []
    )


def _por_gerar(sessao: dict[str, Any], itens: list[dict[str, Any]]) -> list[int]:
    feito = {int(item["order_index"]) for item in itens}
    feedback = sessao.get("feedback") or {}
    descartados = set(feedback.get("descartados") or [])
    plano = feedback.get("plano") or []
    return [p["indice"] for p in plano if p["indice"] not in feito and p["indice"] not in descartados]


def _publico(sessao: dict[str, Any], itens: list[dict[str, Any]]) -> dict[str, Any]:
    feedback = sessao.get("feedback") or {}
    plano = feedback.get("plano") or []
    descartados = feedback.get("descartados") or []
    respondidos = [i for i in itens if i.get("is_correct") is not None]
    return {
        "id": str(sessao["id"]),
        "language": sessao.get("language"),
        "practice_day": sessao.get("practice_day"),
        "status": sessao.get("status"),
        "total": len(plano) - len(descartados),
        "answered": len(respondidos),
        "correct": sum(1 for i in respondidos if i.get("is_correct") and not i.get("skipped")),
        "generating": bool(_por_gerar(sessao, itens)),
        # Só os pendentes, e SEM gabarito: `correct` nunca sai daqui.
        "items": [
            {
                "id": str(i["id"]),
                "type": i["type"],
                "skill": i["skill"],
                "topic": i.get("topic"),
                "band": i.get("cefr_band"),
                "origin": i.get("origin"),
                "payload": treino.audio_para_voz(i.get("payload") or {}, i.get("correct")),
            }
            for i in itens
            if i.get("is_correct") is None
        ],
        "summary": feedback.get("resumo"),
    }


async def _gerar(supabase: Client, sessao: dict[str, Any], indices: list[int]) -> bool:
    """Gera os exercícios destes índices do plano e grava os que passarem.

    Duas tentativas. O que o modelo não entregar direito nas duas é
    DESCARTADO do plano, e não deixado pendente — um exercício que nunca chega
    travaria o treino em "preparando o próximo".

    Mas só se o modelo RESPONDEU. Provedor fora do ar é passageiro: descartar
    ali apagaria o treino do dia inteiro por causa de um minuto de queda.
    Devolve se algum provedor respondeu.
    """
    if not indices:
        return True
    respondeu = False
    feedback = dict(sessao.get("feedback") or {})
    plano = {p["indice"]: treino.Encomenda.de_json(p) for p in feedback.get("plano") or []}
    alvo = languages.idioma(sessao.get("language") or "en")
    nome = alvo.nome if alvo else "Inglês"
    nativo = alvo.nativo if alvo else "English"

    faltam = [i for i in indices if i in plano]
    for tentativa in range(2):
        if not faltam:
            break
        pedidos = []
        for indice in faltam:
            e = plano[indice]
            linha = (
                f"- indice {e.indice}: tipo {e.tipo}; habilidade {e.habilidade}; "
                f"topico \"{e.topico}\"; banda {e.banda}"
            )
            if e.lembrete:
                linha += f"\n  ERRO ANTERIOR a cobrar com outras palavras:\n  {e.lembrete}"
            pedidos.append(linha)
        pedido = (
            f"IDIOMA ESTUDADO: {nome} ({nativo}).\n"
            f"Escreva estes {len(faltam)} exercícios:\n" + "\n".join(pedidos)
        )
        try:
            # 12s por provedor. Medido na Fly: sem teto, o Gemini ficou 50s
            # calado e ninguém mais foi tentado; com 25s, a abertura levou 28s
            # (o teto dele mais a resposta do seguinte). Groq e Mistral
            # entregam um lote de quatro em 4 a 7s, então 12s ainda é folga.
            resultado = await generate_json(
                PRACTICE_PROMPT, pedido, PRACTICE_SCHEMA, per_attempt_timeout=_TEMPO_POR_PROVEDOR
            )
        except AiProviderError:
            logger.warning("geração do treino falhou (tentativa %s)", tentativa + 1, exc_info=True)
            continue
        respondeu = True

        gerados = [i for i in (resultado.content or {}).get("itens") or [] if isinstance(i, dict)]
        aceitos: list[tuple[int, treino.Encomenda, dict[str, Any]]] = []
        for item in gerados:
            try:
                indice = int(item.get("indice"))
            except (TypeError, ValueError):
                continue
            if indice not in faltam or any(indice == a[0] for a in aceitos):
                continue
            encomenda = plano[indice]
            pronto = treino.validar(item, encomenda)
            # Revisão que repete a frase do erro não é revisão: volta para a
            # segunda tentativa, que recebe o mesmo pedido de outras palavras.
            if pronto is None or treino.repete_o_erro(item, encomenda.lembrete):
                continue
            aceitos.append((indice, encomenda, pronto))

        await _traduz_pelo_deepl(sessao.get("language") or "en", [a[2] for a in aceitos])

        for indice, encomenda, pronto in aceitos:
            linha = {
                "user_id": str(sessao["user_id"]),
                "session_id": str(sessao["id"]),
                "language": sessao.get("language"),
                "skill": encomenda.habilidade,
                "type": encomenda.tipo,
                "cefr_band": encomenda.banda,
                "topic": pronto["topico"],
                "prompt": pronto["payload"].get("enunciado") or encomenda.tipo,
                "options": pronto["payload"].get("alternativas") or [],
                "correct": pronto["gabarito"],
                "feedback": pronto["explicacao"],
                "payload": pronto["payload"],
                "order_index": indice,
                "origin": encomenda.origem,
                "review_item_id": encomenda.ponto_id,
            }
            try:
                supabase.table("pathr_english_item").insert(linha).execute()
            except Exception:  # noqa: BLE001
                # Já gerado por uma chamada concorrente (índice único): ok.
                pass
            faltam.remove(indice)

    if faltam and respondeu:
        feedback["descartados"] = sorted(set((feedback.get("descartados") or []) + faltam))
        supabase.table("pathr_english_session").update({"feedback": feedback}).eq(
            "id", sessao["id"]
        ).execute()
    return respondeu


async def _traduz_pelo_deepl(idioma: str, prontos: list[dict[str, Any]]) -> None:
    """Troca a tradução escrita pelo modelo pela do DeepL, onde houver.

    Uma chamada para o lote inteiro. O que o DeepL não devolver em português
    fica com a tradução do modelo — ver services/traducao.py, que também
    explica por que os termos de programação saem em inglês nas duas.
    """
    alvos: list[tuple[dict[str, Any], str]] = []
    for pronto in prontos:
        if "traducao" not in pronto["payload"]:
            continue
        gabarito = pronto["gabarito"]
        original = gabarito.get("texto") or (gabarito.get("frases") or [""])[0]
        if original:
            alvos.append((pronto, original))
    if not alvos:
        return
    traduzidas = await traducao.traduzir([original for _, original in alvos], idioma)
    if not traduzidas:
        return
    for (pronto, _), traduzida in zip(alvos, traduzidas):
        if traduzida:
            pronto["payload"]["traducao"] = traduzida[:300]


async def _com_exercicio_pronto(
    supabase: Client, user: dict[str, Any], sessao: dict[str, Any], lote: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Garante um exercício pronto para mostrar — ou diz, com 503, por que não há.

    Um lote inteiro descartado não pode deixar a tela vazia: gera o seguinte.
    E um treino em que TUDO foi descartado é apagado, porque o índice único do
    dia impediria criar outro até amanhã — a pessoa ficaria sem treino por
    culpa de uma resposta ruim do modelo.
    """
    user_id = str(user["id"])
    # Um lote por volta; o teto cobre o maior plano (20) no menor lote.
    for _ in range(1 + 20 // max(lote, 1)):
        itens = _itens(supabase, str(sessao["id"]))
        if any(i.get("is_correct") is None for i in itens):
            return sessao, itens
        pendentes = _por_gerar(sessao, itens)
        if not pendentes:
            # Nada pronto e nada por gerar: ou o treino acabou, ou tudo foi
            # descartado. A verificação abaixo separa os dois.
            break
        respondeu = await _gerar(supabase, sessao, pendentes[:lote])
        sessao = _sessao(supabase, str(sessao["id"]), user_id)
        if not respondeu:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A IA não respondeu agora. Seu treino continua salvo — tente de novo em instantes.",
            )

    itens = _itens(supabase, str(sessao["id"]))
    if not itens and not _por_gerar(sessao, itens):
        supabase.table("pathr_english_session").delete().eq("id", sessao["id"]).execute()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não consegui preparar os exercícios de hoje. Tente de novo em instantes.",
        )
    return sessao, itens


@router.get("/practice/today")
def practice_today(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O treino de hoje, se já começou. Não cria: abrir a tela não gasta IA.

    Declarada antes de `/practice/{session_id}`, que engoliria "today" como id.
    """
    codigo = _idioma(language)
    sessao = _sessao_de_hoje(supabase, str(current_user["id"]), codigo, _hoje(current_user))
    if not sessao:
        return None
    return _publico(sessao, _itens(supabase, str(sessao["id"])))


@router.post("/practice", status_code=status.HTTP_201_CREATED)
async def start_practice(
    language: str = "en",
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    background: BackgroundTasks = None,
):
    """Abre (ou retoma) o treino de hoje."""
    codigo = _idioma(language)
    user_id = str(current_user["id"])
    dia = _hoje(current_user)

    sessao = _sessao_de_hoje(supabase, user_id, codigo, dia)
    if sessao is None:
        perfil = _perfil(supabase, user_id, codigo)
        quadro = _quadro(supabase, user_id, codigo)
        plano = treino.montar(
            quadro,
            _pontos_vencidos(supabase, user_id, codigo),
            int(perfil.get("daily_goal_min") or 15),
            semente=int(dia.strftime("%Y%m%d")),
        )
        antes = {
            linha["skill"]: {"level": linha["level"], "theta": linha["theta"]}
            for linha in quadro["skills"]
        }
        try:
            sessao = (
                supabase.table("pathr_english_session")
                .insert(
                    {
                        "user_id": user_id,
                        "language": codigo,
                        "mode": "treino",
                        "scenario": f"Treino de {dia.isoformat()}",
                        "practice_day": dia.isoformat(),
                        "cefr_band": quadro["overall"]["level"] or "B1",
                        "status": "active",
                        "feedback": {"plano": [e.para_json() for e in plano], "antes": antes},
                    }
                )
                .execute()
                .data[0]
            )
        except Exception:  # noqa: BLE001
            # Outra aba criou no mesmo instante: o índice único recusou, e o
            # treino certo é o que ela criou.
            sessao = _sessao_de_hoje(supabase, user_id, codigo, dia)
            if sessao is None:
                raise

    sessao, itens = await _com_exercicio_pronto(supabase, current_user, sessao, _PRIMEIRO_LOTE)
    pendentes = _por_gerar(sessao, itens)
    if pendentes and background is not None:
        background.add_task(_gerar, supabase, sessao, pendentes)
    sessao = await _talvez_concluir(supabase, current_user, sessao, itens)
    return _publico(sessao, itens)


@router.get("/practice/{session_id}")
async def get_practice(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """O treino com os exercícios pendentes.

    Se não sobrou nenhum pronto e ainda há o que gerar — o segundo plano
    falhou ou não terminou —, gera aqui mesmo. Esperar é a única saída honesta
    quando não há exercício para mostrar.
    """
    user_id = str(current_user["id"])
    sessao = _sessao(supabase, session_id, user_id)
    sessao, itens = await _com_exercicio_pronto(supabase, current_user, sessao, _LOTE)
    sessao = await _talvez_concluir(supabase, current_user, sessao, itens)
    return _publico(sessao, itens)


def _frente_do_ponto(item: dict[str, Any]) -> str:
    """O que a pessoa errou, escrito para o modelo cobrar de novo depois."""
    payload = item.get("payload") or {}
    partes = [str(payload.get("enunciado") or item.get("prompt") or "")]
    for campo in ("frase", "texto", "audio"):
        if payload.get(campo):
            partes.append(str(payload[campo]))
    if payload.get("emoji"):
        partes.append(f"imagem: {payload['emoji']}")
    if payload.get("esquerda"):
        partes.append("pares: " + ", ".join(payload["esquerda"]))
    return " | ".join(p for p in partes if p)[:1500]


def _reagenda_ou_cria_ponto(
    supabase: Client, user_id: str, item: dict[str, Any], correcao: treino.Correcao
) -> Optional[str]:
    """O ponto de melhora deste exercício anda na fila.

    Exercício de revisão: acerto empurra o ponto para mais longe e SOBE o
    degrau do próximo formato (repetitions do SM-2); erro traz de volta hoje e
    volta ao reconhecimento. Exercício novo errado: vira ponto de melhora.
    Best-effort — perder um reagendamento custa uma repetição; derrubar a
    correção custa a resposta da pessoa.
    """
    try:
        if item.get("review_item_id"):
            cartao = (
                supabase.table("pathr_review_item")
                .select("*")
                .eq("id", item["review_item_id"])
                .limit(1)
                .execute()
                .data
            )
            if not cartao:
                return None
            proximo = review.schedule(
                cartao[0], review.QUALITY_HIT if correcao.acertou else review.QUALITY_MISS
            )
            supabase.table("pathr_review_item").update(proximo).eq(
                "id", item["review_item_id"]
            ).execute()
            return "subiu" if correcao.acertou else "volta_hoje"
        if correcao.acertou:
            return None

        frente = _frente_do_ponto(item)
        chave = review.concept_key(frente)
        existentes = (
            supabase.table("pathr_review_item")
            .select("front")
            .eq("user_id", user_id)
            .eq("kind", "language")
            .eq("language", item.get("language"))
            .limit(300)
            .execute()
            .data
            or []
        )
        if any(review.concept_key(e.get("front")) == chave for e in existentes):
            return None
        certa = correcao.certa if isinstance(correcao.certa, str) else ""
        supabase.table("pathr_review_item").insert(
            {
                "user_id": user_id,
                "kind": "language",
                "language": item.get("language"),
                "skill": item.get("skill"),
                "topic": item.get("topic"),
                "band": item.get("cefr_band"),
                "front": frente,
                "back": " — ".join(p for p in (certa, str(item.get("feedback") or "")) if p)[:2000],
                "due_at": _agora().isoformat(),
                "lapses": 1,
            }
        ).execute()
        return "novo_ponto"
    except Exception:  # noqa: BLE001
        logger.warning("ponto de melhora não atualizado", exc_info=True)
        return None


async def _talvez_concluir(
    supabase: Client, user: dict[str, Any], sessao: dict[str, Any], itens: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fecha o treino quando não sobra nada: nem pendente, nem por gerar."""
    if sessao.get("status") == "done" or not itens:
        return sessao
    if _por_gerar(sessao, itens) or any(i.get("is_correct") is None for i in itens):
        return sessao

    user_id = str(user["id"])
    language = sessao.get("language") or "en"
    feedback = dict(sessao.get("feedback") or {})
    antes = feedback.get("antes") or {}
    depois = _quadro(supabase, user_id, language)

    validos = [i for i in itens if not i.get("skipped")]
    acertos = sum(1 for i in validos if i.get("is_correct"))
    revisoes = [i for i in validos if i.get("origin") == "revisao"]
    niveis = []
    for linha in depois["skills"]:
        if not linha.get("level"):
            continue
        anterior = antes.get(linha["skill"]) or {}
        base = anterior.get("theta")
        niveis.append(
            {
                "skill": linha["skill"],
                "before": anterior.get("level"),
                "after": linha["level"],
                "delta": round(linha["theta"] - float(base), 2) if base is not None else None,
            }
        )
    por_topico: dict[str, dict[str, Any]] = {}
    for item in validos:
        chave = f"{item['skill']}|{item.get('topic') or 'geral'}"
        atual = por_topico.setdefault(
            chave,
            {"skill": item["skill"], "topic": item.get("topic") or "geral", "answered": 0, "correct": 0},
        )
        atual["answered"] += 1
        atual["correct"] += int(bool(item.get("is_correct")))

    feedback["resumo"] = {
        "correct": acertos,
        "answered": len(validos),
        "reviewed": len(revisoes),
        "recovered": sum(1 for i in revisoes if i.get("is_correct")),
        "levels": niveis,
        "topics": sorted(por_topico.values(), key=lambda t: t["correct"] / t["answered"]),
    }
    minutos = max(1, round(len(itens) * 75 / 60))
    supabase.table("pathr_english_session").update(
        {
            "status": "done",
            "feedback": feedback,
            "score": round(100 * acertos / len(validos)) if validos else None,
            "duration_s": minutos * 60,
            "finished_at": _agora().isoformat(),
        }
    ).eq("id", sessao["id"]).execute()
    log_activity(
        supabase,
        user=user,
        kind="language_practice",
        title=f"Treino de idioma — {acertos} de {len(validos)}",
        ref_id=str(sessao["id"]),
        minutes=minutos,
        detail={"language": language, "correct": acertos, "answered": len(validos)},
    )
    return {**sessao, "status": "done", "feedback": feedback}


@router.post("/practice/{session_id}/answer")
async def answer_practice(
    session_id: str,
    payload: PracticeAnswer,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    background: BackgroundTasks = None,
):
    """Corrige na hora e diz o porquê.

    Em idioma a correção é imediata, ao contrário do quiz técnico: o erro não
    corrigido na hora vira hábito, e o próximo exercício já seria feito com a
    forma errada na cabeça.
    """
    user_id = str(current_user["id"])
    sessao = _sessao(supabase, session_id, user_id)
    linhas = (
        supabase.table("pathr_english_item")
        .select("*")
        .eq("id", payload.item_id)
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercício não encontrado.")
    item = linhas[0]

    if item.get("is_correct") is not None:
        # Já respondido (clique duplo, conexão que caiu depois de gravar):
        # devolve o MESMO desfecho em vez de recusar e travar a tela.
        gravado = json.loads(item.get("user_answer") or "{}")
        correcao = treino.Correcao(
            bool(item.get("is_correct")),
            pulado=bool(item.get("skipped")),
            detalhe=gravado.get("detalhe"),
            certa=gravado.get("certa"),
        )
        ponto = gravado.get("ponto")
    else:
        correcao = treino.corrigir(
            item["type"], item.get("correct") or {}, item.get("payload") or {}, payload.answer
        )
        ponto = None if correcao.pulado else _reagenda_ou_cria_ponto(supabase, user_id, item, correcao)
        supabase.table("pathr_english_item").update(
            {
                "user_answer": json.dumps(
                    {
                        "resposta": payload.answer,
                        "detalhe": correcao.detalhe,
                        "certa": correcao.certa,
                        "ponto": ponto,
                    },
                    ensure_ascii=False,
                )[:4000],
                "is_correct": correcao.acertou,
                "skipped": correcao.pulado,
                "answered_at": _agora().isoformat(),
            }
        ).eq("id", item["id"]).execute()

    itens = _itens(supabase, session_id)
    prontos = [i for i in itens if i.get("is_correct") is None]
    por_gerar = _por_gerar(sessao, itens)
    if por_gerar and len(prontos) <= 2 and background is not None:
        background.add_task(_gerar, supabase, sessao, por_gerar[:_LOTE])
    sessao = await _talvez_concluir(supabase, current_user, sessao, itens)

    return {
        "is_correct": correcao.acertou,
        "skipped": correcao.pulado,
        "correct_answer": correcao.certa,
        "detail": correcao.detalhe,
        "explanation": item.get("feedback"),
        # O que aconteceu com o ponto de melhora — dito na tela, para a
        # reciclagem não ser invisível.
        "improvement": ponto,
        "session": _publico(sessao, itens),
    }
