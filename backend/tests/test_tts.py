"""O áudio falado dos itens de idioma.

A suíte é offline, então o que se testa aqui é tudo o que decide a chamada
ANTES de ela sair, mais o contrato de quem falha: o container WAV que o
navegador precisa saber ler, a escolha de voz por interlocutor, a chave do
cache e a recusa limpa quando não há chave de Gemini configurada.

O que não se testa: a voz em si. Isso é do provedor.
"""

import io
import wave

import pytest

from app import tts
from app.ai_providers import AiProviderError


# ── O container ──────────────────────────────────────────────────────────────
# O Gemini devolve PCM cru, sem cabeçalho, e nenhum `<audio>` toca isso. Se o
# cabeçalho estiver errado, o áudio sai em outra velocidade ou não toca — e
# nenhum dos dois aparece como erro, só como som ruim. Daí conferir com o
# módulo `wave` da stdlib, que é um leitor independente do nosso escritor.


def test_wav_e_legivel_e_descreve_o_formato_do_gemini():
    um_segundo = b"\x00\x01" * tts._TAXA

    with wave.open(io.BytesIO(tts._wav(um_segundo))) as arquivo:
        assert arquivo.getnchannels() == 1
        assert arquivo.getframerate() == 24000
        assert arquivo.getsampwidth() == 2
        # Um segundo de amostras tem que continuar sendo um segundo: quadro a
        # mais ou a menos aqui é áudio acelerado na tela.
        assert arquivo.getnframes() == tts._TAXA


def test_wav_nao_recodifica_nada():
    """São 44 bytes na frente dos mesmos dados — sem perda."""
    pcm = b"\x12\x34" * 100
    embrulhado = tts._wav(pcm)

    assert len(embrulhado) == len(pcm) + 44
    assert embrulhado.endswith(pcm)


# ── Quem fala ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Ana: I'll push it after lunch.\nMarc: Thanks, I'll review it.", ["Ana", "Marc"]),
        # Três falantes: o modelo aceita dois, e a tela precisa saber disso.
        ("Ana: Hi.\nMarc: Hello.\nSofia: Morning.", ["Ana", "Marc", "Sofia"]),
        # O mesmo nome duas vezes é um interlocutor, não dois.
        ("Ana: Hi.\nAna: Still me.", ["Ana"]),
        ("Just a plain sentence with no speaker.", []),
        # Pontuação dentro do nome reprova: não é jeito de chamar ninguém.
        ("Wait, really: no.", []),
    ],
)
def test_interlocutores(texto, esperado):
    assert tts._interlocutores(texto) == esperado


def test_uma_frase_com_dois_pontos_passa_por_falante_e_isso_esta_certo():
    """O limite conhecido de `_interlocutores`, registrado de propósito.

    "The rule is simple: ship it." vira um falante chamado "The rule is
    simple" — a medida é a mesma de `languages._FALA`, e ela não sabe a
    diferença. Não precisa saber: quem decide a voz é `_config_de_voz`, e um
    falante só cai na narração de voz única, que é o resultado certo para uma
    frase dessas. Apertar a regra aqui custaria falantes legítimos de nome
    composto ("Dr. Silva", "Ana Paula").
    """
    assert tts._interlocutores("The rule is simple: ship it.") == ["The rule is simple"]
    assert "voiceConfig" in tts._config_de_voz("The rule is simple: ship it.")


def test_dialogo_de_dois_usa_uma_voz_por_pessoa():
    config = tts._config_de_voz("Ana: Hi.\nMarc: Hello.")

    falantes = config["multiSpeakerVoiceConfig"]["speakerVoiceConfigs"]
    assert [f["speaker"] for f in falantes] == ["Ana", "Marc"]
    vozes = {f["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] for f in falantes}
    # Duas vozes iguais num diálogo soariam como uma pessoa se respondendo.
    assert len(vozes) == 2


@pytest.mark.parametrize(
    "texto",
    [
        "Ana: Hi.\nMarc: Hello.\nSofia: Morning.",  # além do limite de dois
        "Plain narration.",  # sem falante
        "Note: at 3.",  # uma linha marcada só
    ],
)
def test_o_que_nao_e_dialogo_de_dois_sai_em_voz_unica(texto):
    """Melhor uma leitura boa e uniforme que perder o áudio num 400."""
    assert "voiceConfig" in tts._config_de_voz(texto)


def test_voz_explicita_desliga_a_deteccao():
    """A tela de escuta manda uma fala por vez, para destacar a linha em curso.

    Aí o texto não carrega mais o nome de quem diz, e é o índice que mantém
    cada interlocutor na sua voz.
    """
    primeira = tts._config_de_voz("I'll push it after lunch.", 0)
    segunda = tts._config_de_voz("Thanks, I'll review it.", 1)

    nome = lambda c: c["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"]  # noqa: E731
    assert nome(primeira) != nome(segunda)


def test_indice_de_voz_alto_da_a_volta_em_vez_de_estourar():
    fora = len(tts._VOZES) + 1
    assert tts._config_de_voz("x", fora)["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] in tts._VOZES


# ── O cache ──────────────────────────────────────────────────────────────────


def test_a_chave_do_cache_separa_o_que_soa_diferente():
    """Mesmo texto em outra voz, ou noutro idioma, é outro áudio: servir um
    pelo outro trocaria o interlocutor no meio do diálogo."""
    chaves = {
        tts._chave_do_cache("hello", "en", 0),
        tts._chave_do_cache("hello", "en", 1),
        tts._chave_do_cache("hello", "en", None),
        tts._chave_do_cache("hello", "pt", 0),
        tts._chave_do_cache("goodbye", "en", 0),
    }
    assert len(chaves) == 5


def test_a_chave_do_cache_e_estavel():
    assert tts._chave_do_cache("hello", "en", 0) == tts._chave_do_cache("hello", "en", 0)


# ── Quando não dá para gerar ──────────────────────────────────────────────────
# Toda recusa aqui vira 503 no router, que é o sinal de "volte para a voz do
# navegador". O que não pode acontecer é a chamada sair para a rede à toa.


@pytest.mark.asyncio
async def test_sem_chave_configurada_recusa_sem_chamar_a_rede(monkeypatch):
    monkeypatch.setattr(tts.settings, "gemini_api_key", "", raising=False)

    with pytest.raises(AiProviderError):
        await tts.narrar("Hello.", "en")

    assert not tts.disponivel()


@pytest.mark.asyncio
async def test_texto_vazio_e_texto_longo_demais_nao_gastam_chamada(monkeypatch):
    monkeypatch.setattr(tts.settings, "gemini_api_key", "chave-de-teste", raising=False)

    with pytest.raises(AiProviderError):
        await tts.narrar("   ", "en")
    with pytest.raises(AiProviderError):
        await tts.narrar("a" * (tts._LIMITE_DE_CARACTERES + 1), "en")


@pytest.mark.asyncio
async def test_o_cache_evita_o_segundo_pedido(monkeypatch):
    """Reouvir é o gesto mais comum de um exercício de escuta. Se ele gerasse
    de novo, o custo seria proporcional à insistência de quem estuda."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "chave-de-teste", raising=False)
    tts._cache.clear()
    pedidos = []

    async def falso_pedido(texto, idioma, voz, api_key):
        pedidos.append(texto)
        return tts._wav(b"\x00\x01" * 10)

    monkeypatch.setattr(tts, "_pede_ao_gemini", falso_pedido)

    primeiro = await tts.narrar("Hello there.", "en", 0)
    segundo = await tts.narrar("Hello there.", "en", 0)

    assert primeiro == segundo
    assert len(pedidos) == 1
    # Outra voz é outro áudio, e portanto um pedido novo.
    await tts.narrar("Hello there.", "en", 1)
    assert len(pedidos) == 2


@pytest.mark.asyncio
async def test_rotaciona_para_a_segunda_chave_quando_a_primeira_falha(monkeypatch):
    """Mesma postura de `generate_json`: com várias chaves, uma cota estourada
    não pode ser o que cala o áudio do app."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1,k2", raising=False)
    tts._cache.clear()
    tentadas = []

    async def falso_pedido(texto, idioma, voz, api_key):
        tentadas.append(api_key)
        if api_key == "k1":
            raise RuntimeError("cota estourada nesta chave")
        return tts._wav(b"\x00\x01" * 10)

    monkeypatch.setattr(tts, "_pede_ao_gemini", falso_pedido)

    audio = await tts.narrar("Hello.", "en", 0)

    assert tentadas == ["k1", "k2"]
    assert audio.startswith(b"RIFF")
