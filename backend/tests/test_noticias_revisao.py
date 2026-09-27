"""Correções da revisão de Notícias: cada teste prende um defeito apontado."""

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers import noticias as rotas
from app.services import noticias
from tests.fake_supabase import FakeSupabase

EU = {"id": "11111111-1111-1111-1111-111111111111", "email": "eu@exemplo.com", "name": "Ana"}


def _banco(**tabelas):
    padrao = {
        "pathr_news_event": [],
        "pathr_news_scan": [],
        "pathr_news_attendance": [],
        "pathr_rate_event": [],
        "pathr_profile": [{"user_id": EU["id"], "city": "Vitória", "state": "ES"}],
    }
    return FakeSupabase(**{**padrao, **tabelas})


# --- a feature flag vale no servidor ---------------------------------------


def _banco_com_flag(estado: str):
    return FakeSupabase(pathr_feature_flag=[{"key": "noticias", "state": estado}])


def test_api_de_noticias_recusa_quem_nao_tem_o_recurso():
    with pytest.raises(HTTPException) as erro:
        rotas.recurso_ligado(EU, _banco_com_flag("ninguem"))
    assert erro.value.status_code == 404
    with pytest.raises(HTTPException):
        rotas.recurso_ligado(EU, _banco_com_flag("admin"))
    assert rotas.recurso_ligado(EU, _banco_com_flag("todos"))["id"] == EU["id"]


def test_todas_as_rotas_de_noticias_passam_pela_guarda():
    guardas = [d.dependency for d in rotas.router.dependencies]
    assert rotas.recurso_ligado in guardas


# --- limite por conta para a varredura -------------------------------------


def test_varredura_tem_teto_por_conta():
    """Trocar a cidade do perfil e reabrir a tela não dispara varredura sem fim."""
    banco = _banco()

    def abrir():
        fundo = BackgroundTasks()
        resposta = rotas.listar(fundo, 50.0, EU, banco)
        return resposta, fundo

    primeira, fundo1 = abrir()
    assert primeira["atualizando"] is True
    assert len(fundo1.tasks) == 1

    segunda, fundo2 = abrir()
    # A lista continua saindo (sem 429), só que sem outra varredura.
    assert segunda["atualizando"] is False
    assert segunda["eventos"] == []
    assert fundo2.tasks == []


# --- confirmar_presenca só engole a unicidade -------------------------------


class _BancoQueFalha:
    def __init__(self, erro: Exception):
        self._erro = erro

    def table(self, _nome):
        return self

    def insert(self, _payload):
        return self

    def execute(self):
        raise self._erro


class _ErroPostgrest(Exception):
    def __init__(self, mensagem, code=None):
        super().__init__(mensagem)
        self.code = code


def test_presenca_repetida_e_silenciosa():
    banco = _BancoQueFalha(_ErroPostgrest("duplicate key value", "23505"))
    noticias.confirmar_presenca(banco, "u1", "e1")  # não levanta


def test_presenca_com_outro_erro_do_banco_sobe():
    banco = _BancoQueFalha(_ErroPostgrest("connection refused"))
    with pytest.raises(_ErroPostgrest):
        noticias.confirmar_presenca(banco, "u1", "e1")


# --- .ics: DTEND é exclusivo ------------------------------------------------


def _campo(ics: str, prefixo: str) -> str:
    return next(l for l in ics.split("\r\n") if l.startswith(prefixo))


def test_ics_de_um_dia_termina_no_dia_seguinte():
    ics = noticias.gerar_ics({"id": "1", "titulo": "Meetup", "data_inicio": "2026-10-28"})
    assert _campo(ics, "DTSTART") == "DTSTART;VALUE=DATE:20261028"
    assert _campo(ics, "DTEND") == "DTEND;VALUE=DATE:20261029"


def test_ics_com_data_fim_soma_um_dia_ao_ultimo_dia():
    ics = noticias.gerar_ics({"id": "1", "data_inicio": "2026-10-30", "data_fim": "2026-10-31"})
    assert _campo(ics, "DTEND") == "DTEND;VALUE=DATE:20261101"


# --- o filtro de região é do banco, não de Python sobre limit(200) ----------


def test_evento_da_regiao_nao_some_atras_de_200_de_outras():
    fora = [
        {"id": f"sp{i}", "title": "Longe", "city": "São Paulo", "state": "SP", "event_start": "2099-01-01"}
        for i in range(250)
    ]
    perto = {"id": "es1", "title": "Perto", "city": "Vitória", "state": "ES", "event_start": "2099-06-01"}
    banco = _banco(pathr_news_event=[*fora, perto])

    lista = noticias.listar_por_regiao(banco, EU["id"], "Vitória", "ES", 50.0)

    assert [e["titulo"] for e in lista] == ["Perto"]


# --- código morto fora -------------------------------------------------------


def test_definicoes_mortas_da_extracao_por_ia_foram_removidas():
    for nome in ("_AI_SYSTEM", "_AI_SCHEMA", "_DATA_ISO", "_data_valida", "_texto_ou_none", "AiProviderError"):
        assert not hasattr(noticias, nome), nome
