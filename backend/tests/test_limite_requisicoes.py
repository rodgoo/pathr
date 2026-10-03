"""O teto geral de requisições por IP — a única barreira contra inundação na API, que não fica atrás da
Cloudflare (ver o cabeçalho de app/limite_requisicoes.py).

Aciona o middleware ASGI direto, com `scope`/`receive`/`send` de mentira: não precisa de app FastAPI nem de
TestClient para testar contagem, janela e isenção.
"""

import asyncio

import pytest

from app import limite_requisicoes as mod
from app.limite_requisicoes import LimiteDeRequisicoes


async def _app_interno(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _scope(path: str = "/qualquer") -> dict:
    return {"type": "http", "path": path, "headers": []}


async def _nao_chega():
    raise AssertionError("não deveria ser chamado")


async def _chamar(middleware: LimiteDeRequisicoes, path: str = "/qualquer") -> int:
    """Devolve o status HTTP que o middleware respondeu."""
    status = {}

    async def send(mensagem):
        if mensagem["type"] == "http.response.start":
            status["code"] = mensagem["status"]
            status["headers"] = dict(mensagem["headers"])

    await middleware(_scope(path), _nao_chega, send)
    return status.get("code")


@pytest.fixture(autouse=True)
def ip_controlavel(monkeypatch):
    """Troca `client_ip` por um valor fixo, controlado por teste — sem depender da lógica de
    detecção de IP de `app/deps.py` (que tem teste próprio)."""
    estado = {"ip": "203.0.113.1"}
    monkeypatch.setattr(mod, "client_ip", lambda request: estado["ip"])
    return estado


@pytest.fixture(autouse=True)
def janela_pequena(monkeypatch):
    """Janela e teto baixos — sem isto, bater o teto real (240/60s) tornaria o teste lento."""
    monkeypatch.setattr(mod, "LIMITE_POR_JANELA", 3)


def test_deixa_passar_ate_o_teto_e_recusa_a_seguir(ip_controlavel):
    mid = LimiteDeRequisicoes(_app_interno)
    resultados = [asyncio.run(_chamar(mid)) for _ in range(5)]

    assert resultados == [200, 200, 200, 429, 429]


def test_a_resposta_429_tem_retry_after_e_corpo_em_portugues():
    mid = LimiteDeRequisicoes(_app_interno)
    for _ in range(3):
        asyncio.run(_chamar(mid))

    corpo = {}

    async def send(mensagem):
        if mensagem["type"] == "http.response.start":
            corpo["status"] = mensagem["status"]
            corpo["headers"] = dict(mensagem["headers"])
        elif mensagem["type"] == "http.response.body":
            corpo["body"] = mensagem["body"]

    asyncio.run(mid(_scope(), _nao_chega, send))

    assert corpo["status"] == 429
    assert corpo["headers"][b"retry-after"] == str(mod.JANELA_S).encode()
    assert b"Muitas requisi" in corpo["body"]


def test_cada_ip_tem_a_propria_contagem(ip_controlavel):
    mid = LimiteDeRequisicoes(_app_interno)
    for _ in range(3):
        assert asyncio.run(_chamar(mid)) == 200
    # O mesmo endereço já estourou o teto.
    assert asyncio.run(_chamar(mid)) == 429

    # Outro endereço começa do zero.
    ip_controlavel["ip"] = "203.0.113.2"
    assert asyncio.run(_chamar(mid)) == 200


def test_janela_vira_e_a_contagem_reinicia(monkeypatch):
    mid = LimiteDeRequisicoes(_app_interno)
    for _ in range(3):
        assert asyncio.run(_chamar(mid)) == 200
    assert asyncio.run(_chamar(mid)) == 429

    # Avança o relógio para a janela seguinte.
    agora = mod.time.time()
    monkeypatch.setattr(mod.time, "time", lambda: agora + mod.JANELA_S)
    assert asyncio.run(_chamar(mid)) == 200


def test_health_nunca_e_barrado_mesmo_acima_do_teto(ip_controlavel):
    mid = LimiteDeRequisicoes(_app_interno)
    resultados = [asyncio.run(_chamar(mid, "/health")) for _ in range(10)]

    assert resultados == [200] * 10


def test_ips_demais_nao_crescem_sem_fim(monkeypatch, ip_controlavel):
    """Um IP novo a cada pedido (gira endereço, ou botnet) não pode fazer o
    dicionário de contagem crescer para sempre."""
    monkeypatch.setattr(mod, "MAXIMO_DE_IPS", 5)
    mid = LimiteDeRequisicoes(_app_interno)

    for i in range(50):
        ip_controlavel["ip"] = f"203.0.113.{i}"
        asyncio.run(_chamar(mid))

    assert len(mid._janelas) <= 5
