"""A faxina das tabelas de eventos.

O que se segura: sai só o que passou da retenção (dois dias de limite, trinta
de erro), o que ainda está na janela de um limite fica — apagar cedo demais
zeraria a contagem de quem está sendo barrado —, uma tabela que falha não
impede a outra, e o disparo de hora em hora é quem chama.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.config import settings
from app.routers import jobs
from app.services import faxina
from tests.fake_supabase import FakeSupabase

AGORA = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _ha(**tempo) -> str:
    return (AGORA - timedelta(**tempo)).isoformat()


def _banco() -> FakeSupabase:
    return FakeSupabase(
        pathr_rate_event=[
            {"id": 1, "action": "ia", "key": "u1", "created_at": _ha(days=3)},
            {"id": 2, "action": "ia", "key": "u1", "created_at": _ha(days=2, minutes=1)},
            # Ainda dentro do limite diário de quem usou ontem: fica.
            {"id": 3, "action": "ia", "key": "u1", "created_at": _ha(hours=23)},
            {"id": 4, "action": "cadastro", "key": "1.2.3.4", "created_at": _ha(days=1, hours=23)},
        ],
        pathr_error_event=[
            {"id": "e1", "fingerprint": "a", "occurred_at": _ha(days=31)},
            {"id": "e2", "fingerprint": "b", "occurred_at": _ha(days=29)},
        ],
    )


def test_apaga_so_o_que_passou_da_retencao():
    banco = _banco()
    faxina.apagar_eventos_velhos(banco, AGORA)
    assert sorted(l["id"] for l in banco.tabelas["pathr_rate_event"]) == [3, 4]
    assert [l["id"] for l in banco.tabelas["pathr_error_event"]] == ["e2"]


def test_tabela_que_falha_nao_impede_a_outra():
    banco = _banco()
    original = banco.table

    def table(nome):
        if nome == "pathr_rate_event":
            raise RuntimeError("fora do ar")
        return original(nome)

    banco.table = table
    resultado = faxina.apagar_eventos_velhos(banco, AGORA)
    assert resultado["pathr_rate_event"] is None
    assert resultado["pathr_error_event"] is not None
    assert [l["id"] for l in banco.tabelas["pathr_error_event"]] == ["e2"]


def test_o_disparo_de_hora_em_hora_faz_a_faxina(monkeypatch):
    monkeypatch.setattr(settings, "jobs_secret", "segredo")
    banco = FakeSupabase(
        pathr_user=[],
        pathr_rate_event=[{"id": 1, "action": "ia", "key": "u1", "created_at": "2000-01-01T00:00:00+00:00"}],
        pathr_error_event=[{"id": "e1", "fingerprint": "a", "occurred_at": "2000-01-01T00:00:00+00:00"}],
    )
    pedido = SimpleNamespace(headers={jobs.CABECALHO: "segredo"})
    resposta = jobs.disparar_avisos(pedido, banco)
    assert set(resposta["faxina"]) == {"pathr_rate_event", "pathr_error_event"}
    assert banco.tabelas["pathr_rate_event"] == [] and banco.tabelas["pathr_error_event"] == []
