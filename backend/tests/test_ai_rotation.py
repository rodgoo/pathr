"""Rotação de provedores de IA.

Os testes cobrem o que a rotação promete: cair para o próximo candidato numa
falha, rebaixar (sem remover) quem estourou cota, e nunca declarar derrota
enquanto houver candidato não tentado.
"""

import asyncio
import time
from datetime import timedelta

import httpx
import pytest

from app import ai_providers as ai
from app.ai_providers import AiProviderError, _Candidate, _CandidateFailed, _cooldowns


def _fails(kind: str, detail: str = "falhou"):
    async def call(_sp, _up, _schema):
        raise _CandidateFailed(kind, detail)

    return call


def _works(payload: dict, tokens: int = 7):
    async def call(_sp, _up, _schema):
        return payload, tokens

    return call


@pytest.mark.asyncio
async def test_cai_para_o_proximo_candidato(monkeypatch):
    monkeypatch.setattr(
        ai,
        "_text_candidates",
        lambda: [
            _Candidate("A", _fails(ai.QUOTA, "limite de uso atingido")),
            _Candidate("B", _works({"ok": True})),
        ],
    )
    result = await ai.generate_json("sistema", "usuario")
    assert result.content == {"ok": True}
    assert result.provider == "B"


@pytest.mark.asyncio
async def test_candidato_que_falhou_entra_em_cooldown(monkeypatch):
    monkeypatch.setattr(
        ai,
        "_text_candidates",
        lambda: [
            _Candidate("A", _fails(ai.QUOTA)),
            _Candidate("B", _works({"ok": True})),
        ],
    )
    await ai.generate_json("s", "u")
    assert "A" in _cooldowns
    assert "B" not in _cooldowns


@pytest.mark.asyncio
async def test_cooldown_rebaixa_mas_nao_remove(monkeypatch):
    """O ponto 3 da docstring do módulo: um cooldown obsoleto nunca pode ser
    a razão de a IA ficar indisponível."""
    _cooldowns["A"] = ai._Cooldown(until=ai._now() + timedelta(minutes=10), reason="cota")
    monkeypatch.setattr(
        ai,
        "_text_candidates",
        lambda: [_Candidate("A", _works({"de": "A"}))],
    )
    result = await ai.generate_json("s", "u")
    assert result.content == {"de": "A"}


@pytest.mark.asyncio
async def test_ordem_de_tentativa_poe_saudavel_na_frente():
    cooled = _Candidate("frio", _works({}))
    healthy = _Candidate("saudavel", _works({}))
    _cooldowns["frio"] = ai._Cooldown(until=ai._now() + timedelta(minutes=5), reason="cota")
    order = ai._attempt_order([cooled, healthy])
    assert [candidate.name for candidate in order] == ["saudavel", "frio"]


@pytest.mark.asyncio
async def test_erro_quando_todos_falham(monkeypatch):
    monkeypatch.setattr(
        ai,
        "_text_candidates",
        lambda: [
            _Candidate("A", _fails(ai.QUOTA, "limite de uso atingido")),
            _Candidate("B", _fails(ai.AUTH, "chave recusada")),
        ],
    )
    with pytest.raises(AiProviderError) as excinfo:
        await ai.generate_json("s", "u")
    assert "A" in excinfo.value.detail and "B" in excinfo.value.detail


@pytest.mark.asyncio
async def test_sem_provedor_configurado(monkeypatch):
    monkeypatch.setattr(ai, "_text_candidates", list)
    with pytest.raises(AiProviderError) as excinfo:
        await ai.generate_json("s", "u")
    assert "GEMINI_API_KEY" in excinfo.value.detail


def test_multiplas_chaves_viram_candidatos_independentes():
    assert ai._keys("k1,k2 , k3") == ["k1", "k2", "k3"]
    assert ai._keys("uma-chave") == ["uma-chave"]
    assert ai._keys("") == []
    assert ai._named("Gemini", 0, 1) == "Gemini"
    assert ai._named("Gemini", 1, 3) == "Gemini #2"


def test_classificacao_por_status():
    def response(status: int, headers=None):
        return httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "http://x"))

    assert ai._classify(response(429)).kind == ai.QUOTA
    assert ai._classify(response(402)).kind == ai.QUOTA
    assert ai._classify(response(401)).kind == ai.AUTH
    assert ai._classify(response(404)).kind == ai.AUTH
    assert ai._classify(response(500)).kind == ai.TRANSIENT


def test_retry_after_respeitado_com_teto():
    request = httpx.Request("POST", "http://x")
    curto = httpx.Response(429, headers={"retry-after": "90"}, request=request)
    assert ai._parse_retry_after(curto) == timedelta(seconds=90)

    absurdo = httpx.Response(429, headers={"retry-after": "999999"}, request=request)
    assert ai._parse_retry_after(absurdo) == ai._MAX_COOLDOWN


def test_resposta_que_nao_e_objeto_vira_motivo_para_rotacionar():
    with pytest.raises(ValueError):
        ai._parsed_object("[1, 2, 3]")
    with pytest.raises(ValueError):
        ai._parsed_object("null")
    assert ai._parsed_object('{"a": 1}') == {"a": 1}


def test_erro_desconhecido_nao_e_engolido():
    """Bug nosso não pode virar "tenta o próximo" — isso esconderia o defeito."""
    assert ai._as_failure(RuntimeError("bug")) is None
    assert ai._as_failure(httpx.ConnectTimeout("lento")).kind == ai.TRANSIENT
    assert ai._as_failure(ValueError("json ruim")).kind == ai.TRANSIENT


# ---------------------------------------------------------------------------
# Contrato de formato para quem não aceita schema
# ---------------------------------------------------------------------------


def test_contrato_nomeia_as_chaves_do_schema():
    """O bug de producao: `response_format: json_object` garante JSON VALIDO,
    nao JSON no formato combinado. O modelo devolveu a lista de tecnologias sob
    a chave `competencias` e o curriculo entrou vazio, sem nada falhar."""
    schema = {
        "type": "OBJECT",
        "properties": {
            "anos_experiencia": {"type": "NUMBER"},
            "tecnologias": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "nome": {"type": "STRING"},
                        "proficiencia": {"type": "INTEGER"},
                    },
                },
            },
        },
    }
    contrato = ai._schema_contract(schema)

    assert '"tecnologias"' in contrato
    assert '"anos_experiencia"' in contrato
    # As chaves aninhadas tambem: o modelo errou uma de primeiro nivel, mas
    # nada impede que erre `nome` dentro do array.
    assert '"nome"' in contrato
    assert '"proficiencia"' in contrato
    assert "sinônimos" in contrato


def test_contrato_vazio_quando_nao_ha_schema():
    """Chamador sem schema (nenhum hoje, mas a assinatura permite) nao deve
    ganhar um paragrafo de instrucao vazio colado no fim do prompt."""
    assert ai._schema_contract(None) == ""
    assert ai._schema_contract({}) == ""


def test_contrato_traduz_os_tipos():
    schema = {
        "type": "OBJECT",
        "properties": {
            "titulo": {"type": "STRING"},
            "semanas": {"type": "INTEGER"},
            "horas": {"type": "NUMBER"},
        },
    }
    contrato = ai._schema_contract(schema)
    assert "string" in contrato and "inteiro" in contrato and "número" in contrato


# ---------------------------------------------------------------------------
# O teto de tempo da rotacao inteira.
#
# O caso real: "Gerar plano" ficava carregando e terminava em "Nao consegui
# falar com o servidor" -- fetch rejeitado, sem resposta HTTP nenhuma. Com 45s
# POR candidato e candidatos tentados em sequencia, tres candidatos lentos
# passam de dois minutos e o proxy da borda corta a conexao antes de a rota
# responder. A pessoa espera e nao recebe nem o motivo.
# ---------------------------------------------------------------------------


def _demora(segundos: float):
    async def call(_sp, _up, _schema):
        await asyncio.sleep(segundos)
        return {"ok": True}, 1

    return call


@pytest.mark.asyncio
async def test_rotacao_para_quando_o_orcamento_acaba(monkeypatch):
    """Sem teto, os tres candidatos lentos somariam bem mais que o orcamento."""
    tentados = []

    def _registra(nome):
        async def call(_sp, _up, _schema):
            tentados.append(nome)
            await asyncio.sleep(0.15)
            raise _CandidateFailed(ai.TRANSIENT, "nao respondeu a tempo")

        return call

    candidatos = [_Candidate(nome, _registra(nome)) for nome in ("A", "B", "C")]
    # A gasta 0.15 e sobra 0.25 -> B roda. B gasta 0.15 e sobra 0.10, abaixo
    # do minimo -> C nao e tentado.
    monkeypatch.setattr(ai, "_MIN_ATTEMPT", 0.12)

    result, failures = await ai._run_rotation(
        candidatos, lambda c: c.call("s", "u", None), budget=0.4
    )

    assert result is None
    # A e B cabem; C nao chega a ser tentado, e a mensagem diz isso em vez de
    # afirmar que ele falhou.
    assert tentados == ["A", "B"]
    assert any("sem tempo de serem tentados" in falha for falha in failures)


@pytest.mark.asyncio
async def test_candidato_lento_nao_consome_alem_do_orcamento(monkeypatch):
    """Um candidato que trava sozinho e cortado no fim do orcamento."""
    monkeypatch.setattr(ai, "_MIN_ATTEMPT", 0.05)
    inicio = time.monotonic()

    result, failures = await ai._run_rotation(
        [_Candidate("Lento", _demora(30))], lambda c: c.call("s", "u", None), budget=0.3
    )

    assert result is None
    assert time.monotonic() - inicio < 5
    assert failures == ["Lento: não respondeu a tempo"]


@pytest.mark.asyncio
async def test_candidato_rapido_ainda_vence_dentro_do_orcamento(monkeypatch):
    """O teto nao pode atrapalhar o caminho feliz."""
    monkeypatch.setattr(
        ai,
        "_text_candidates",
        lambda: [_Candidate("A", _fails(ai.QUOTA, "limite")), _Candidate("B", _works({"ok": 1}))],
    )
    result = await ai.generate_json("sistema", "usuario")
    assert result.provider == "B"


@pytest.mark.asyncio
async def test_teto_por_tentativa_deixa_o_proximo_ser_tentado(monkeypatch):
    """Caso real do treino de idioma: o Gemini ficou 50s calado e os outros
    quatro provedores nem foram tentados. Com teto por tentativa, o lento é
    cortado e o seguinte responde dentro do mesmo orçamento."""
    monkeypatch.setattr(ai, "_MIN_ATTEMPT", 0.05)
    # Nomes diferentes em cada rodada: a primeira põe o lento em cooldown, e
    # com o mesmo nome a segunda já começaria pelo rápido, sem provar o teto.
    sem = [_Candidate("Lento A", _demora(30)), _Candidate("Rapido A", _works({"ok": 1}))]
    com = [_Candidate("Lento B", _demora(30)), _Candidate("Rapido B", _works({"ok": 1}))]

    sem_teto, falhas_sem = await ai._run_rotation(sem, lambda c: c.call("s", "u", None), budget=0.6)
    com_teto, falhas_com = await ai._run_rotation(
        com, lambda c: c.call("s", "u", None), budget=0.6, per_attempt=0.2
    )

    assert sem_teto is None and any("sem tempo" in f for f in falhas_sem)
    assert com_teto is not None
    assert falhas_com == ["Lento B: não respondeu a tempo"]


def test_timeout_do_orcamento_e_falha_transitoria():
    """`asyncio.wait_for` levanta TimeoutError; sem reconhece-lo, a rotacao
    trataria o corte como bug nosso e levantaria em vez de tentar o proximo."""
    falha = ai._as_failure(TimeoutError())
    assert falha is not None
    assert falha.kind == ai.TRANSIENT
