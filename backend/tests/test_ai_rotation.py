"""Rotação de provedores de IA.

Os testes cobrem o que a rotação promete: cair para o próximo candidato numa
falha, rebaixar (sem remover) quem estourou cota, e nunca declarar derrota
enquanto houver candidato não tentado.
"""

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
