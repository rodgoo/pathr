"""A página de status das integrações.

Offline: toda chamada de rede é trocada por um transporte falso. O que se
segura é o que não pode falhar em silêncio: a chave nunca sai no relatório,
resposta HTTP vira o estado certo, e "verificar agora" não vira um jeito de
gastar cota clicando.
"""

import asyncio

import httpx
import pytest

from app import ai_providers
from app.config import settings
from app.services import status_apis as S
from app.services import vagas

CHAVE_SECRETA = "chave-super-secreta-123"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    S.limpar_cache()
    vagas.ultimo_estado.clear()
    for campo in ("gemini_api_key", "groq_api_key", "mistral_api_key", "cerebras_api_key", "openrouter_api_key",
                  "brave_api_key", "adzuna_app_id", "adzuna_app_key", "youtube_api_key", "brevo_from_email"):
        monkeypatch.setattr(settings, campo, "")
    monkeypatch.setattr(settings, "groq_api_key", CHAVE_SECRETA)
    monkeypatch.setattr(settings, "deepl_api_key", "outra-chave:fx")
    monkeypatch.setattr(settings, "brevo_api_key", "brevo-chave")
    monkeypatch.setattr(settings, "tavily_api_key", "tavily-chave")
    monkeypatch.setattr(S, "_banco", lambda: S.Status("supabase", "Supabase", "Base", "", True, S.OK))
    monkeypatch.setattr(S, "_uso_de_ia_hoje", lambda: {"Groq": {"requisicoes": 3, "tokens": 900}})
    monkeypatch.setattr(ai_providers, "provider_status", lambda: [])
    yield
    S.limpar_cache()


def _rede(monkeypatch, respostas):
    """`respostas`: host -> (status, json). Conta as chamadas por host."""
    chamadas = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        chamadas.append(pedido.url.host)
        codigo, corpo = respostas.get(pedido.url.host, (200, {}))
        return httpx.Response(codigo, json=corpo)

    original = httpx.AsyncClient

    def cliente(**argumentos):
        return original(transport=httpx.MockTransport(transporte), **argumentos)

    monkeypatch.setattr(S.httpx, "AsyncClient", cliente)
    return chamadas


def test_http_vira_estado():
    assert S.descreve_http(200)[0] == S.OK
    assert S.descreve_http(401)[0] == S.ERRO
    assert S.descreve_http(429)[0] == S.DEGRADADA
    assert S.descreve_http(503)[0] == S.DEGRADADA
    assert S.descreve_http(404)[0] == S.ERRO


def test_relatorio_nunca_traz_a_chave(monkeypatch):
    _rede(monkeypatch, {})
    relatorio = asyncio.run(S.relatorio())
    texto = repr(relatorio)
    for segredo in (CHAVE_SECRETA, "outra-chave", "brevo-chave", "tavily-chave"):
        assert segredo not in texto


def test_estados_por_integracao(monkeypatch):
    _rede(monkeypatch, {
        "api.groq.com": (401, {}),
        "api-free.deepl.com": (200, {"character_count": 950_000, "character_limit": 1_000_000}),
    })
    itens = {i["id"]: i for i in asyncio.run(S.relatorio())["itens"]}

    assert itens["ia:Groq"]["estado"] == S.ERRO and "recusada" in itens["ia:Groq"]["detalhe"]
    assert itens["ia:Groq"]["uso"] == {"hoje": {"requisicoes": 3, "tokens": 900}}
    assert itens["ia:Gemini"]["estado"] == S.SEM_CHAVE
    # Mais de 90% da cota do DeepL: funciona, mas avisa.
    assert itens["deepl"]["estado"] == S.DEGRADADA and itens["deepl"]["uso"]["usados"] == 950_000
    # Chave do Brevo sem remetente: nenhum e-mail sai.
    assert itens["brevo"]["estado"] == S.ERRO
    assert itens["adzuna"]["estado"] == S.SEM_CHAVE
    # Tavily configurado não é chamado só para checar; Remotive idem.
    assert itens["tavily"]["estado"] == S.SEM_VERIFICACAO
    assert itens["remotive"]["estado"] == S.SEM_VERIFICACAO


def test_fonte_sem_checagem_ao_vivo_usa_o_ultimo_uso_real(monkeypatch):
    from datetime import datetime, timezone

    _rede(monkeypatch, {})
    vagas.ultimo_estado["remotive"] = ("erro", datetime.now(timezone.utc))
    vagas.ultimo_estado["busca"] = ("ok", datetime.now(timezone.utc))
    itens = {i["id"]: i for i in asyncio.run(S.relatorio())["itens"]}
    assert itens["remotive"]["estado"] == S.ERRO
    assert itens["tavily"]["estado"] == S.OK


def test_ia_em_pausa_no_rodizio_aparece_como_degradada(monkeypatch):
    _rede(monkeypatch, {})
    monkeypatch.setattr(ai_providers, "provider_status", lambda: [
        {"provider": "Groq", "available": False, "until": "2026-09-13T12:00:00+00:00", "reason": "limite de uso atingido"},
    ])
    itens = {i["id"]: i for i in asyncio.run(S.relatorio())["itens"]}
    assert itens["ia:Groq"]["estado"] == S.DEGRADADA
    assert "limite de uso" in itens["ia:Groq"]["detalhe"]


def test_verificar_agora_nao_refaz_antes_do_intervalo(monkeypatch):
    chamadas = _rede(monkeypatch, {})

    async def roteiro():
        await S.relatorio()
        primeira = len(chamadas)
        segundo = await S.relatorio(atualizar=True)
        return primeira, segundo

    primeira, segundo = asyncio.run(roteiro())
    assert primeira > 0
    assert len(chamadas) == primeira
    assert segundo["pode_atualizar_em_s"] > 0


def test_resumo_conta_por_estado():
    itens = [{"estado": S.OK}, {"estado": S.OK}, {"estado": S.ERRO}, {"estado": S.SEM_CHAVE}]
    assert S.resumo(itens) == {"ok": 2, "degradada": 0, "erro": 1, "nao_configurada": 1, "sem_verificacao": 0}


def test_busca_de_vagas_registra_o_ultimo_uso(monkeypatch):
    async def gupy(_termo, _regiao=None):
        return []

    async def remotive(_termo, _regiao=None):
        raise RuntimeError("fora")

    monkeypatch.setattr(vagas, "_gupy", gupy)
    monkeypatch.setattr(vagas, "_remotive", remotive)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    vagas.limpar_cache()
    asyncio.run(vagas.buscar(["Java"]))
    assert vagas.ultimo_estado["gupy"][0] == "ok"
    assert vagas.ultimo_estado["remotive"][0] == "erro"
