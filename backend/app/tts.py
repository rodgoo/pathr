"""Voz natural para o áudio do módulo de idioma, pelo TTS do Gemini.

## Por que isto existe

O `speechSynthesis` do navegador era a escolha original (ver o cabeçalho de
`frontend/src/components/english/ListeningPlayer.tsx`): não cobra, não precisa
de chave, e o som sai no aparelho de quem estuda. O que ele não garante é a
VOZ. O navegador só oferece o que o sistema tem instalado, e num Windows em
português com Brave isso costuma ser uma única voz de inglês — a "Microsoft
Zira Desktop", da geração SAPI5 concatenativa. Ela lê palavra por palavra:
não muda a entonação na vírgula, não sobe no ponto de interrogação e não
separa uma fala da outra.

Para um item de compreensão isso deixou de servir. Escuta em nível CEFR se
apoia em prosódia — quem estuda precisa ouvir onde a frase respira e qual
palavra carrega a ênfase, que é justamente o que a voz antiga não entrega.

## Por que o Gemini, e não um TTS dedicado

Porque a chave já está aqui. `GEMINI_API_KEY` move o roadmap, os quizzes e o
nivelamento, tem tier gratuito no AI Studio e aceita lista de chaves — a mesma
rotação que `ai_providers.py` descreve. Um provedor dedicado (ElevenLabs,
Azure Speech) significaria outra conta, outra chave e outra fatura para uma
única tela.

Dois traços do TTS do Gemini decidem o caso:

1. **Dois locutores nativos numa chamada.** O item de listening é um diálogo
   ("Ana: ..." / "Marc: ..."), e o modelo aceita uma voz por interlocutor no
   mesmo pedido. Sem isso, um diálogo exigiria uma chamada por fala e a emenda
   entre elas soaria como duas gravações coladas.
2. **Direção de atuação em texto.** Dá para pedir sotaque, ritmo e intenção em
   linguagem natural, que é como `_DIRECAO` pede exatamente o que faltava:
   respeitar a pontuação e soar como conversa, não como leitura.

## O custo continua limitado de propósito

A cobrança é por duração do áudio gerado, na casa de centavos de dólar por
minuto — e cai a zero dentro do tier gratuito. Três coisas seguram isso:

- **Cache por conteúdo.** A chave é o hash do texto mais o modelo e o idioma,
  então reouvir o mesmo diálogo (o que se faz muito, é material de escuta) não
  gera de novo.
- **Teto de tamanho.** `_LIMITE_DE_CARACTERES` recusa texto longo antes de
  gastar, porque um item de escuta é um diálogo curto e qualquer coisa muito
  maior que isso é engano ou abuso.
- **Falha não quebra a tela.** Sem chave, sem cota ou com o modelo fora do ar,
  o endpoint responde 503 e o front volta para a voz do navegador. O áudio
  piora; a atividade continua existindo. É a mesma escolha que `ai_providers`
  faz ao nunca deixar uma cota estourada derrubar uma função inteira.
"""

import asyncio
import base64
import hashlib
import logging
import struct
from collections import OrderedDict
from typing import Optional

import httpx

from app.ai_providers import AiProviderError, _classify, _keys
from app.config import settings

logger = logging.getLogger(__name__)

# ── Dois dialetos, e por que os dois ────────────────────────────────────────
#
# O TTS do Gemini é servido por duas superfícies de API, e elas NÃO têm o mesmo
# formato de pedido nem de resposta:
#
# 1. `/v1beta/interactions` — o que o guia de TTS publica hoje (setembro de
#    2026), com o modelo no corpo, `response_format: {"type": "audio"}` e uma
#    lista `speech_config` em que cada item é `{"speaker", "voice"}`.
# 2. `…/models/{modelo}:generateContent` — a superfície clássica, com
#    `responseModalities: ["AUDIO"]` e `speechConfig` aninhado. É a mesma porta
#    que `ai_providers` usa para texto, e o modelo 2.5 não está deprecado.
#
# Os dois estão aqui porque não deu para decidir entre eles com honestidade: o
# guia atual descreve (1), a página do modelo 2.5 não descreve formato nenhum,
# e nenhuma das duas fontes declara (2) morta. Sem chave neste ambiente, não
# houve como perguntar ao servidor quem está certo.
#
# A ordem está em `_DIALETOS`: o CLÁSSICO primeiro, e o documentado como rede
# de segurança. Parece invertido, mas o critério é custo — o 2.5 sai por cerca
# de metade do 3.1 por minuto de áudio, e custo foi o eixo da decisão original
# de nem ter TTS de servidor. Quem recusar o pedido (404 de rota ou modelo
# inexistente, 400 de corpo que não entendeu) passa a vez para o outro.
#
# Um dialeto errado custa uma requisição perdida na primeira fala. O mesmo
# dialeto, se fosse o único e estivesse errado, custaria a feature inteira
# falhando calada — porque 503 aqui é indistinguível de "sem cota" e a tela
# voltaria para a voz velha para sempre, sem ninguém perceber.
#
# Quem decide é a produção: `_pede_ao_gemini` registra em log qual dialeto
# respondeu, e a chave de Gemini só existe lá. Lido isso, o perdedor sai daqui.

_URL_INTERACTIONS = "https://generativelanguage.googleapis.com/v1beta/interactions"
_MODELO_INTERACTIONS = "gemini-3.1-flash-tts-preview"

# Mais barato por minuto de áudio que o 3.1, e o custo é o eixo da decisão
# original de nem ter TTS de servidor — por isso ele é o preferido quando os
# dois funcionam. Ver a ordem em `_DIALETOS`.
_MODELO_GENERATE = "gemini-2.5-flash-preview-tts"
_URL_GENERATE = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

# Compatibilidade: a chave do cache inclui o modelo, e trocar este nome
# invalida o cache de propósito — áudio gerado por outro modelo soa diferente.
_MODELO = _MODELO_GENERATE

_TIMEOUT = 60

# Áudio é lento de gerar e o pedido sai de um clique em "ouvir". Sem teto, um
# texto colado por engano viraria minutos de síntese cobrada.
_LIMITE_DE_CARACTERES = 1200

# O que o PCM do Gemini é, segundo a documentação: 24 kHz, mono, 16 bits.
# Fixo de propósito — a resposta não descreve o formato, então ler daqui é
# mais honesto que adivinhar de um campo que pode não vir.
_TAXA = 24000
_CANAIS = 1
_BITS = 16

# Vozes prontas do catálogo, escolhidas por timbre contrastante: quem ouve
# precisa distinguir os dois interlocutores de imediato, e duas vozes do mesmo
# registro num diálogo curto soam como a mesma pessoa se respondendo.
_VOZES = ("Kore", "Puck", "Zephyr", "Charon")

# A direção de atuação. É a resposta direta ao defeito da voz antiga: a
# instrução não é sobre timbre, é sobre LER DIREITO — pontuação, ritmo e
# sotaque nativo da língua que está sendo estudada.
_DIRECAO = (
    "You are recording study audio for a {idioma} learner.\n"
    "Read the transcript below aloud as natural, connected speech.\n"
    "- Use a native {idioma} accent. Never apply the phonetics of another language.\n"
    "- Obey the punctuation: pause at commas, fall at full stops, rise on questions.\n"
    "- Speak slightly slower than conversational pace, but keep normal rhythm and stress.\n"
    "  Do not read word by word, and do not flatten the intonation.\n"
    "- Say only the words of the transcript. Never read the speaker labels, the\n"
    "  punctuation marks or these instructions out loud.\n\n"
    "Transcript:\n{texto}"
)

_NOME_DO_IDIOMA = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "zh": "Mandarin Chinese",
    "ko": "Korean",
    "pt": "Brazilian Portuguese",
}

# Cache de conteúdo, em processo. Não é a memória definitiva — reinício apaga,
# e cada worker tem o seu — mas cobre o caso que mais gera chamada: a mesma
# pessoa tocando o mesmo diálogo várias vezes seguidas para entender. O passo
# seguinte, quando o volume pedir, é guardar em Supabase Storage e enfim
# preencher a coluna `audio_url`, que existe no schema e nunca foi usada.
_CACHE_MAXIMO = 256
_cache: "OrderedDict[str, bytes]" = OrderedDict()
_trava = asyncio.Lock()


def disponivel() -> bool:
    """Há chave de Gemini configurada? Sem isso o endpoint nem tenta."""
    return bool(_keys(settings.gemini_api_key))


def _wav(pcm: bytes) -> bytes:
    """Embrulha o PCM cru num container WAV.

    O Gemini devolve amostras sem cabeçalho, e nenhum `<audio>` toca isso: o
    navegador precisa que alguém diga a taxa, o número de canais e a largura
    da amostra. São 44 bytes na frente dos mesmos dados — não há recodificação,
    e portanto nenhuma perda.
    """
    bytes_por_amostra = _BITS // 8
    taxa_de_bytes = _TAXA * _CANAIS * bytes_por_amostra
    alinhamento = _CANAIS * bytes_por_amostra
    return b"".join(
        (
            b"RIFF",
            struct.pack("<I", 36 + len(pcm)),
            b"WAVEfmt ",
            struct.pack("<IHHIIHH", 16, 1, _CANAIS, _TAXA, taxa_de_bytes, alinhamento, _BITS),
            b"data",
            struct.pack("<I", len(pcm)),
            pcm,
        )
    )


def _interlocutores(texto: str) -> list[str]:
    """Quem fala, na ordem em que aparece.

    O diálogo chega como "Ana: ..." por linha, do mesmo jeito que o prompt do
    nivelamento pede. Sem marcação de falante, a lista volta vazia e o texto é
    narrado por uma voz só.
    """
    nomes: list[str] = []
    for linha in texto.splitlines():
        cabeca, separador, resto = linha.partition(":")
        if not separador or not resto.strip():
            continue
        quem = cabeca.strip()
        # Mesma medida que `languages._FALA` usa para reconhecer uma fala: nome
        # curto, sem quebra de linha, seguido de dois-pontos e conteúdo. A
        # pontuação no nome é uma reprova a mais, para não tomar por falante o
        # começo de uma frase que só tem dois-pontos no meio.
        #
        # Isto NÃO distingue "Note: the meeting is at 3" de uma fala — ali
        # "Note" passa como nome. Não precisa distinguir: quem decide é
        # `_config_de_voz`, que só usa duas vozes quando há exatamente dois
        # falantes, e uma linha solta dessas cai na narração de voz única.
        if not quem or len(quem) > 40 or any(c in quem for c in ".!?,;"):
            continue
        if quem not in nomes:
            nomes.append(quem)
    return nomes


def _uma_voz(indice: int) -> dict:
    return {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": _VOZES[indice % len(_VOZES)]}}}


def _config_de_voz(texto: str, voz: Optional[int] = None) -> dict:
    """A voz, ou as duas vozes, do pedido.

    `voz` fixa uma voz e desliga a detecção. É o caminho que a tela de escuta
    usa: ela manda uma fala por vez, para poder destacar a linha que está
    tocando, e então quem sabe de quem é a fala é ela — o texto de uma linha
    solta ("I'll push it after lunch.") não carrega mais o nome de quem diz.
    Sem isso, todo interlocutor voltaria na mesma voz e o diálogo soaria como
    uma pessoa conversando consigo mesma.

    Sem `voz`, os falantes saem do próprio texto. O modelo aceita no máximo
    dois locutores; um diálogo de três ou mais é narrado por uma voz só,
    porque uma leitura boa e uniforme é melhor que perder o áudio inteiro num
    400 por exceder o limite.
    """
    if voz is not None:
        return _uma_voz(voz)
    nomes = _interlocutores(texto)
    if len(nomes) != 2:
        return _uma_voz(0)
    return {
        "multiSpeakerVoiceConfig": {
            "speakerVoiceConfigs": [
                {"speaker": nome, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}}
                for nome, voz in zip(nomes, _VOZES)
            ]
        }
    }


def _vozes_achatadas(texto: str, voz: Optional[int] = None) -> list[dict]:
    """A mesma decisão de `_config_de_voz`, no formato do dialeto novo.

    Aqui a configuração é uma lista: um item sem `speaker` é narração de voz
    única, e dois itens com `speaker` são o diálogo. As duas funções partem de
    `_interlocutores`, então a escolha de quem fala com qual voz é a mesma nos
    dois dialetos — só a forma do JSON muda.
    """
    if voz is not None:
        return [{"voice": _VOZES[voz % len(_VOZES)]}]
    nomes = _interlocutores(texto)
    if len(nomes) != 2:
        return [{"voice": _VOZES[0]}]
    return [{"speaker": nome, "voice": voz_} for nome, voz_ in zip(nomes, _VOZES)]


def _chave_do_cache(texto: str, idioma: str, voz: Optional[int]) -> str:
    """A voz entra na chave: o mesmo texto em duas vozes são dois áudios, e
    servir um pelo outro trocaria o interlocutor no meio do diálogo."""
    return hashlib.sha256(f"{_MODELO}\n{idioma}\n{voz}\n{texto}".encode("utf-8")).hexdigest()


async def _le_do_cache(chave: str) -> Optional[bytes]:
    async with _trava:
        audio = _cache.get(chave)
        if audio is not None:
            _cache.move_to_end(chave)
        return audio


async def _grava_no_cache(chave: str, audio: bytes) -> None:
    async with _trava:
        _cache[chave] = audio
        _cache.move_to_end(chave)
        while len(_cache) > _CACHE_MAXIMO:
            _cache.popitem(last=False)


class _DialetoRecusado(Exception):
    """A rota ou o corpo não serviram para esta superfície de API.

    Distinta de `_CandidateFailed`: aquela diz "esta CHAVE não deu" (cota,
    auth) e manda tentar a próxima chave; esta diz "este DIALETO não existe
    aqui" e manda tentar o outro formato com a MESMA chave. Confundir as duas
    gastaria todas as chaves repetindo um pedido que nenhuma poderia atender.
    """


def _texto_dirigido(texto: str, idioma: str) -> str:
    return _DIRECAO.format(idioma=_NOME_DO_IDIOMA.get(idioma, "English"), texto=texto)


def _audio_ou_erro(bruto: Optional[str]) -> bytes:
    if not bruto:
        # 200 sem áudio é como o filtro de conteúdo do Gemini responde: vem o
        # metadado de uso e nenhum dado de som. Não é falha de chave nem de
        # dialeto — é este texto que ele não vai falar.
        raise AiProviderError("o modelo não devolveu áudio para este texto")
    return _wav(base64.b64decode(bruto))


async def _via_interactions(texto: str, idioma: str, voz: Optional[int], api_key: str) -> bytes:
    """O dialeto que o guia de TTS publica hoje.

    O `speech_config` é uma LISTA achatada, e é o campo `speaker` em cada item
    que liga uma voz a um interlocutor — sem o aninhamento de `voiceConfig` /
    `prebuiltVoiceConfig` do dialeto clássico.
    """
    corpo: dict = {
        "model": _MODELO_INTERACTIONS,
        "input": _texto_dirigido(texto, idioma),
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": _vozes_achatadas(texto, voz)},
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resposta = await client.post(_URL_INTERACTIONS, params={"key": api_key}, json=corpo)
    if resposta.status_code in (400, 404, 405):
        raise _DialetoRecusado(f"interactions recusou o pedido (HTTP {resposta.status_code})")
    if resposta.status_code != 200:
        raise _classify(resposta)
    dados = resposta.json()
    saida = dados.get("output_audio") or {}
    return _audio_ou_erro(saida.get("data") if isinstance(saida, dict) else None)


async def _via_generate_content(texto: str, idioma: str, voz: Optional[int], api_key: str) -> bytes:
    """O dialeto clássico, a mesma porta que `ai_providers` usa para texto."""
    corpo = {
        "contents": [{"parts": [{"text": _texto_dirigido(texto, idioma)}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": _config_de_voz(texto, voz),
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resposta = await client.post(
            _URL_GENERATE.format(modelo=_MODELO_GENERATE), params={"key": api_key}, json=corpo
        )
    if resposta.status_code in (400, 404, 405):
        raise _DialetoRecusado(f"generateContent recusou o pedido (HTTP {resposta.status_code})")
    if resposta.status_code != 200:
        raise _classify(resposta)
    dados = resposta.json()
    try:
        partes = dados["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return _audio_ou_erro(None)
    bruto = next(
        (p["inlineData"]["data"] for p in partes if isinstance(p, dict) and "inlineData" in p),
        None,
    )
    return _audio_ou_erro(bruto)


# O mais barato por minuto primeiro: custo é o eixo da decisão original, e a
# diferença entre os dois modelos é de cerca de duas vezes. O documentado vem
# depois, como rede de segurança para o caso de o clássico ter sido desligado.
_DIALETOS = (_via_generate_content, _via_interactions)


async def _pede_ao_gemini(texto: str, idioma: str, voz: Optional[int], api_key: str) -> bytes:
    """Tenta os dialetos com a MESMA chave, e para no primeiro que responder.

    Registra em log qual respondeu, e isso não é telemetria de enfeite: é como
    a dúvida entre as duas superfícies se resolve. A documentação não decide,
    e a chave de Gemini só existe no backend — então quem responde a pergunta
    é a produção, na primeira vez que alguém aperta "Ouvir". Com o log, basta
    ler `flyctl logs` para saber qual dialeto apagar do código.

    Em INFO e uma vez por geração (não por reprodução, que o cache absorve),
    então não é ruído: um item de escuta ouvido gera uma linha.
    """
    recusas: list[str] = []
    for dialeto in _DIALETOS:
        try:
            audio = await dialeto(texto, idioma, voz, api_key)
        except _DialetoRecusado as erro:
            recusas.append(str(erro))
            logger.info("TTS: dialeto %s recusou (%s)", dialeto.__name__, erro)
            continue
        logger.info(
            "TTS: dialeto %s gerou %d bytes de WAV%s",
            dialeto.__name__,
            len(audio),
            f" apos {len(recusas)} recusa(s)" if recusas else "",
        )
        return audio
    logger.warning("TTS: nenhuma superficie aceitou o pedido (%s)", "; ".join(recusas))
    raise AiProviderError(
        "nenhuma superfície de TTS do Gemini aceitou o pedido: " + "; ".join(recusas)
    )


async def narrar(texto: str, idioma: str = "en", voz: Optional[int] = None) -> bytes:
    """O texto falado, em WAV.

    Tenta as chaves de Gemini em ordem e só desiste quando todas falham — é a
    mesma postura de `ai_providers.generate_json()`, pelo mesmo motivo: com
    várias chaves configuradas, uma cota estourada não pode ser o que cala o
    áudio do app.
    """
    texto = texto.strip()
    if not texto:
        raise AiProviderError("nada para falar")
    if len(texto) > _LIMITE_DE_CARACTERES:
        raise AiProviderError("texto longo demais para virar áudio")

    chave = _chave_do_cache(texto, idioma, voz)
    guardado = await _le_do_cache(chave)
    if guardado is not None:
        return guardado

    api_keys = _keys(settings.gemini_api_key)
    if not api_keys:
        raise AiProviderError("nenhuma chave de Gemini configurada")

    ultima: Optional[Exception] = None
    for api_key in api_keys:
        try:
            audio = await _pede_ao_gemini(texto, idioma, voz, api_key)
        except AiProviderError:
            raise
        except Exception as erro:  # falha de rede ou recusa desta chave
            ultima = erro
            continue
        await _grava_no_cache(chave, audio)
        return audio
    raise AiProviderError("nenhuma chave de Gemini conseguiu gerar o áudio") from ultima
