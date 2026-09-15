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
import struct
from collections import OrderedDict
from typing import Optional

import httpx

from app.ai_providers import AiProviderError, _classify, _keys
from app.config import settings

# Preview é o que existe: em setembro de 2026 o TTS do Gemini ainda não saiu
# dessa fase em nenhuma variante. Um modelo preview que sai do catálogo
# responde 404, e aí a tela cai para a voz do navegador até a troca daqui.
_MODELO = "gemini-2.5-flash-preview-tts"
_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

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


async def _pede_ao_gemini(texto: str, idioma: str, voz: Optional[int], api_key: str) -> bytes:
    corpo = {
        "contents": [
            {
                "parts": [
                    {
                        "text": _DIRECAO.format(
                            idioma=_NOME_DO_IDIOMA.get(idioma, "English"), texto=texto
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": _config_de_voz(texto, voz),
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resposta = await client.post(
            _URL.format(modelo=_MODELO), params={"key": api_key}, json=corpo
        )
    if resposta.status_code != 200:
        raise _classify(resposta)
    dados = resposta.json()
    try:
        bruto = dados["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as erro:
        # Resposta 200 sem áudio é o formato do filtro de conteúdo do Gemini:
        # o candidato volta com `finishReason` e sem `inlineData`.
        raise AiProviderError("o modelo não devolveu áudio para este texto") from erro
    return _wav(base64.b64decode(bruto))


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
