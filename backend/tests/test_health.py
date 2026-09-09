"""A checagem de saúde.

O que importa aqui é o contrato com o orquestrador: 503 enquanto o schema não
estiver pronto, 200 depois. Um health check que devolve 200 cedo demais faz o
Render promover uma versão que responderia 500 em toda rota.
"""

from unittest.mock import MagicMock

import pytest

from app import health


class _Store:
    """Um Supabase de mentira. `fail_on` é a tabela que dispara o erro."""

    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on
        self.consulted: list[str] = []

    def table(self, name: str):
        self.consulted.append(name)
        if name == self.fail_on:
            raise RuntimeError("relation does not exist")
        chain = MagicMock()
        chain.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return chain


@pytest.fixture
def store(monkeypatch):
    """Injeta o cliente falso no ponto onde health.py o importa (tarde, dentro
    da função) — importar `app.database` no topo exigiria ambiente
    configurado e tiraria a suíte do modo offline."""

    def install(fail_on: str | None = None) -> _Store:
        fake = _Store(fail_on)
        module = MagicMock()
        module.get_supabase.return_value = fake
        monkeypatch.setitem(__import__("sys").modules, "app.database", module)
        return fake

    return install


def test_ok_quando_as_tabelas_respondem(store):
    fake = store()
    response = MagicMock()
    body = health.health(response)

    assert body["status"] == "ok"
    assert body["checks"]["schema"]["ok"] is True
    # Não consulta as 28 tabelas: uma amostra basta para saber que a migration
    # rodou e o PostgREST recarregou.
    assert fake.consulted == list(health._CORE_TABLES)


def test_503_quando_uma_tabela_central_falta(store):
    store(fail_on="pathr_roadmap")
    response = MagicMock()
    body = health.health(response)

    assert body["status"] == "degraded"
    assert body["checks"]["schema"]["ok"] is False
    assert response.status_code == 503


def test_nao_vaza_o_texto_do_erro(store):
    """/health é público e a mensagem do PostgREST pode carregar a URL do
    projeto Supabase."""
    store(fail_on="pathr_user")
    body = health.health(MagicMock())

    detail = body["checks"]["schema"]["detail"]
    assert "RuntimeError" in detail
    assert "relation does not exist" not in detail
