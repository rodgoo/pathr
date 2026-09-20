"""O áudio falado dos itens de idioma.

A suíte é offline, então o que se testa aqui é tudo o que decide a chamada
ANTES de ela sair, mais o contrato de quem falha: o container WAV que o
navegador precisa saber ler, a escolha de voz por interlocutor, a chave do
cache e a recusa limpa quando não há chave de Gemini configurada.

O que não se testa: a voz em si. Isso é do provedor.
"""

import base64
import io
import wave

import httpx
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


# ── Os dois dialetos ─────────────────────────────────────────────────────────
# O guia de TTS publica `/v1beta/interactions`; o dialeto clássico usa
# `:generateContent`. Nenhuma fonte declara o clássico morto, e sem chave não
# houve como perguntar ao servidor. Daí os dois — e daí testar que a escolha de
# voz é a MESMA nos dois, senão trocar de dialeto trocaria o interlocutor.


def test_o_classico_e_tentado_primeiro_por_ser_mais_barato():
    """A ordem não é arbitrária: o 2.5 custa cerca de metade do 3.1 por minuto
    de áudio, e custo foi o eixo da decisão original de nem ter TTS."""
    assert tts._DIALETOS[0] is tts._via_generate_content
    assert tts._DIALETOS[1] is tts._via_interactions


@pytest.mark.asyncio
async def test_o_log_diz_qual_dialeto_respondeu(monkeypatch, caplog):
    """O log é como a dúvida entre as superfícies se resolve: a chave só existe
    no backend, então quem responde a pergunta é a produção."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1", raising=False)
    tts._cache.clear()

    async def recusa(texto, idioma, voz, api_key):
        raise tts._DialetoRecusado("HTTP 404")

    async def aceita(texto, idioma, voz, api_key):
        return tts._wav(b"\x00\x01" * 10)

    monkeypatch.setattr(tts, "_DIALETOS", (recusa, aceita))

    with caplog.at_level("INFO", logger="app.tts"):
        await tts.narrar("Hello.", "en", 0)

    registrado = "\n".join(r.getMessage() for r in caplog.records)
    assert "recusa recusou" in registrado
    assert "aceita gerou" in registrado


def test_as_duas_formas_de_json_descrevem_a_mesma_escolha_de_voz():
    dialogo = "Ana: Hi.\nMarc: Hello."

    aninhado = tts._config_de_voz(dialogo)["multiSpeakerVoiceConfig"]["speakerVoiceConfigs"]
    achatado = tts._vozes_achatadas(dialogo)

    assert [f["speaker"] for f in aninhado] == [f["speaker"] for f in achatado]
    assert [f["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] for f in aninhado] == [
        f["voice"] for f in achatado
    ]


@pytest.mark.parametrize("texto", ["Plain narration.", "Ana: Hi.\nMarc: Hello.\nSofia: Morning."])
def test_voz_unica_no_dialeto_novo_e_uma_lista_de_um_sem_falante(texto):
    achatado = tts._vozes_achatadas(texto)

    assert len(achatado) == 1
    assert "speaker" not in achatado[0]


def test_voz_explicita_tambem_desliga_a_deteccao_no_dialeto_novo():
    assert tts._vozes_achatadas("I'll push it.", 0) == [{"voice": tts._VOZES[0]}]
    assert tts._vozes_achatadas("Thanks.", 1) == [{"voice": tts._VOZES[1]}]


class _ClienteFalso:
    """Um `httpx.AsyncClient` de mentira, para conferir o que sai e o que entra.

    O código cria o cliente por dentro, então não há transporte para injetar:
    trocar a classe é o único jeito de ver o corpo do pedido sem rede.
    """

    enviado: dict = {}

    def __init__(self, resposta):
        self._resposta = resposta

    def __call__(self, *_a, **_kw):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def post(self, url, params=None, headers=None, json=None):
        type(self).enviado = {"url": url, "params": params, "headers": headers, "json": json}
        return self._resposta


def _resposta(payload: dict, status: int = 200):
    return httpx.Response(status, json=payload)


@pytest.mark.asyncio
async def test_dialeto_novo_monta_o_corpo_e_le_o_audio_de_output_audio(monkeypatch):
    pcm = base64.b64encode(b"\x00\x01" * 10).decode("ascii")
    cliente = _ClienteFalso(_resposta({"output_audio": {"data": pcm}}))
    monkeypatch.setattr(tts.httpx, "AsyncClient", cliente)

    audio = await tts._via_interactions("Ana: Hi.\nMarc: Hello.", "en", None, "k1")

    assert audio.startswith(b"RIFF")
    corpo = _ClienteFalso.enviado["json"]
    assert _ClienteFalso.enviado["url"] == tts._URL_INTERACTIONS
    assert corpo["response_format"] == {"type": "audio"}
    assert corpo["model"] == tts._MODELO_INTERACTIONS
    assert [f["speaker"] for f in corpo["generation_config"]["speech_config"]] == ["Ana", "Marc"]
    # A direção de atuação tem que chegar junto: é ela que pede pontuação
    # obedecida e sotaque nativo, que era o defeito original.
    assert "Obey the punctuation" in corpo["input"]


@pytest.mark.asyncio
async def test_dialeto_classico_monta_o_corpo_e_le_o_audio_de_inline_data(monkeypatch):
    pcm = base64.b64encode(b"\x00\x01" * 10).decode("ascii")
    cliente = _ClienteFalso(
        _resposta(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                # Uma parte de texto na frente não pode esconder
                                # o áudio: a busca é pela que tem `inlineData`.
                                {"text": "ok"},
                                {"inlineData": {"mimeType": "audio/L16", "data": pcm}},
                            ]
                        }
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(tts.httpx, "AsyncClient", cliente)

    audio = await tts._via_generate_content("Ana: Hi.\nMarc: Hello.", "en", None, "k1")

    assert audio.startswith(b"RIFF")
    corpo = _ClienteFalso.enviado["json"]
    assert tts._MODELO_GENERATE in _ClienteFalso.enviado["url"]
    assert corpo["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert "multiSpeakerVoiceConfig" in corpo["generationConfig"]["speechConfig"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 404, 405])
async def test_rota_ou_corpo_recusados_viram_recusa_de_dialeto(monkeypatch, status):
    cliente = _ClienteFalso(_resposta({"error": {"message": "nope"}}, status))
    monkeypatch.setattr(tts.httpx, "AsyncClient", cliente)

    with pytest.raises(tts._DialetoRecusado):
        await tts._via_interactions("Hello.", "en", 0, "k1")


@pytest.mark.asyncio
async def test_200_sem_audio_nao_rotaciona_nada(monkeypatch):
    """É o filtro de conteúdo: nem chave nem dialeto resolvem, e insistir só
    gastaria cota. O erro sobe direto e a tela cai para a voz do navegador."""
    cliente = _ClienteFalso(_resposta({"usageMetadata": {"totalTokenCount": 7}}))
    monkeypatch.setattr(tts.httpx, "AsyncClient", cliente)

    with pytest.raises(AiProviderError, match="não devolveu áudio"):
        await tts._via_interactions("Hello.", "en", 0, "k1")


@pytest.mark.asyncio
async def test_dialeto_recusado_cai_para_o_outro_com_a_mesma_chave(monkeypatch):
    """Rota inexistente é problema de FORMATO, não de chave.

    Se isso rotacionasse chave, todas seriam gastas repetindo um pedido que
    nenhuma poderia atender — e o motivo real ficaria escondido.
    """
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1,k2", raising=False)
    tts._cache.clear()
    chamados = []

    async def recusa(texto, idioma, voz, api_key):
        chamados.append(("recusa", api_key))
        raise tts._DialetoRecusado("HTTP 404")

    async def aceita(texto, idioma, voz, api_key):
        chamados.append(("aceita", api_key))
        return tts._wav(b"\x00\x01" * 10)

    monkeypatch.setattr(tts, "_DIALETOS", (recusa, aceita))

    audio = await tts.narrar("Hello.", "en", 0)

    assert audio.startswith(b"RIFF")
    # A mesma chave nos dois: nenhuma rotação disparada por recusa de formato.
    assert chamados == [("recusa", "k1"), ("aceita", "k1")]


@pytest.mark.asyncio
async def test_os_dois_dialetos_recusados_falha_dizendo_por_que(monkeypatch):
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1", raising=False)
    # Sem Groq: este teste é sobre o Gemini recusar, e sem desligá-la o
    # resultado passava a depender de quem roda ter (ou não) chave da Groq no
    # .env.local — teste que muda de resposta conforme a máquina não segura
    # nada.
    monkeypatch.setattr(tts.settings, "groq_api_key", "", raising=False)
    tts._cache.clear()

    async def recusa(texto, idioma, voz, api_key):
        raise tts._DialetoRecusado("HTTP 404")

    monkeypatch.setattr(tts, "_DIALETOS", (recusa, recusa))

    with pytest.raises(AiProviderError, match="nenhuma superfície de TTS"):
        await tts.narrar("Hello.", "en", 0)


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


@pytest.mark.asyncio
async def test_a_chave_vai_no_cabecalho_e_nunca_na_url(monkeypatch):
    """Chave em `?key=...` vaza em todo lugar que registra endereço.

    Aconteceu numa depuração: com o log do httpx em INFO, a chave inteira saiu
    impressa no terminal. No cabeçalho ela fica fora do que se costuma
    registrar — e este teste existe para que ninguém a devolva para a URL por
    conveniência.
    """
    pcm = base64.b64encode(bytes([0, 1]) * 10).decode("ascii")
    cliente = _ClienteFalso(_resposta({"candidates": [{"content": {"parts": [{"inlineData": {"data": pcm}}]}}]}))
    monkeypatch.setattr(tts.httpx, "AsyncClient", cliente)

    await tts._via_generate_content("Hello.", "en", None, "chave-secreta")

    enviado = _ClienteFalso.enviado
    assert enviado["headers"] == {"x-goog-api-key": "chave-secreta"}
    assert "chave-secreta" not in enviado["url"]
    assert not enviado["params"]


# ---------------------------------------------------------------------------
# Dois provedores: cota de um não pode calar o áudio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groq_assume_quando_o_gemini_fica_sem_cota(monkeypatch):
    """O relato que originou isto: "a cota acabou e o áudio parou de sair"."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1", raising=False)
    monkeypatch.setattr(tts.settings, "groq_api_key", "g1", raising=False)
    monkeypatch.setattr(tts, "_TENTATIVAS", 1)  # sem espera no teste
    tts._cache.clear()

    async def sem_cota(*_a):
        raise tts._classify(httpx.Response(429))

    async def groq_fala(texto, idioma, voz, api_key):
        assert api_key == "g1"
        return b"RIFF....WAVEfake"

    monkeypatch.setattr(tts, "_pede_ao_gemini", sem_cota)
    monkeypatch.setattr(tts, "_via_groq", groq_fala)

    assert await tts.narrar("Hello.", "en", 0) == b"RIFF....WAVEfake"


@pytest.mark.asyncio
async def test_idioma_que_a_groq_nao_fala_nao_a_oferece(monkeypatch):
    """A Groq fala inglês (e árabe). Oferecê-la para francês produziria áudio
    em inglês com texto francês — pior que não ter áudio."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1", raising=False)
    monkeypatch.setattr(tts.settings, "groq_api_key", "g1", raising=False)

    nomes = [nome for nome, _, _ in await tts._provedores("fr")]
    assert nomes == ["gemini"]
    assert [nome for nome, _, _ in await tts._provedores("en")] == ["gemini", "groq"]


@pytest.mark.asyncio
async def test_provedor_perto_do_teto_vai_para_o_fim(monkeypatch):
    """A troca acontece ANTES de a cota acabar: quem passou de 85% do teto do
    dia cede a vez, em vez de gastar a última fatia e voltar 429."""
    monkeypatch.setattr(tts.settings, "gemini_api_key", "k1", raising=False)
    monkeypatch.setattr(tts.settings, "groq_api_key", "g1", raising=False)
    monkeypatch.setattr(tts, "perto_do_teto", lambda nome: nome == "gemini")

    assert [nome for nome, _, _ in await tts._provedores("en")] == ["groq", "gemini"]
