"""A fila diária de candidaturas.

O que se segura: a fila sai do mesmo ranqueamento da tela de Vagas, não repete
vaga (nem a descartada), respeita o teto do dia; a carta é escrita com o
currículo e guardada na linha; o envio por e-mail leva o currículo em anexo e
responde para a pessoa; a vaga que pede resposta no site é só marcada como
enviada (com o link na mão); e o agendador monta a fila de manhã, uma vez por
dia, só para quem tem currículo.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import candidaturas as rotas
from app.routers import jobs
from app.routers import vagas as rotas_de_vagas
from app.services import candidaturas as servico
from tests.fake_supabase import FakeSupabase

EU = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "eu@exemplo.com",
    "name": "Ana Souza",
    "timezone_name": "America/Sao_Paulo",
}
AGORA = datetime(2026, 9, 15, 11, 30, tzinfo=timezone.utc)  # 8h30 em São Paulo
PEDIDO = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.7"), url=SimpleNamespace(path="/x"))


def _vaga(numero: int, **extra):
    return {
        "id": f"v{numero}",
        "titulo": f"Pessoa Desenvolvedora Java {numero}",
        "empresa": f"Empresa {numero}",
        "url": f"https://vagas.exemplo.com/{numero}",
        "fonte": "gupy",
        "local": "São Paulo, SP",
        "remota": False,
        "combina": 90 - numero,
        "resumo": "Vaga para trabalhar com Java e Spring Boot.",
        "sobre": {"pede": "Java, Spring Boot e SQL", "faz": "APIs do produto"},
        **extra,
    }


@pytest.fixture
def busca(monkeypatch):
    """A busca de vagas da tela, de mentira."""
    estado = SimpleNamespace(vagas=[_vaga(i) for i in range(1, 9)], chamadas=0)

    async def falsa(_supabase, _user, **_):
        estado.chamadas += 1
        return {"vagas": estado.vagas, "sem_perfil": False}

    monkeypatch.setattr(rotas_de_vagas, "vagas_da_pessoa", falsa)
    return estado


def _banco(**tabelas):
    return FakeSupabase(pathr_application=[], pathr_rate_event=[], pathr_security_event=[], **tabelas)


def test_a_fila_do_dia_sai_do_ranqueamento_e_nao_repete(busca):
    banco = _banco()
    novas = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))

    assert [linha["url"] for linha in novas] == [f"https://vagas.exemplo.com/{i}" for i in range(1, 6)]
    assert novas[0]["day"] == "2026-09-15" and novas[0]["score"] == 89
    assert "Spring Boot" in novas[0]["snippet"]

    # De novo no mesmo dia: o teto do dia já foi atingido.
    assert asyncio.run(servico.montar_fila(banco, EU, agora=AGORA)) == []

    # Amanhã, as cinco de hoje não voltam — inclusive a que foi descartada.
    banco.tabelas["pathr_application"][0]["status"] = "descartada"
    amanha = datetime(2026, 9, 16, 11, 30, tzinfo=timezone.utc)
    seguintes = asyncio.run(servico.montar_fila(banco, EU, agora=amanha))
    assert [linha["url"] for linha in seguintes] == [f"https://vagas.exemplo.com/{i}" for i in (6, 7, 8)]


def test_fonte_fora_do_ar_nao_derruba_a_fila(monkeypatch):
    async def explode(*_a, **_k):
        raise RuntimeError("fonte fora")

    monkeypatch.setattr(rotas_de_vagas, "vagas_da_pessoa", explode)
    assert asyncio.run(servico.montar_fila(_banco(), EU, agora=AGORA)) == []


@pytest.fixture
def curriculo():
    return {
        "id": "r1",
        "user_id": EU["id"],
        "status": "parsed",
        "is_primary": True,
        "filename": "curriculo-ana.pdf",
        "storage_path": "ana/abc.pdf",
        "parsed": {
            "headline": "Desenvolvedora back-end",
            "skills": [{"name": "Java"}, {"name": "Spring Boot"}],
            "experiences": [{"role": "Dev Java", "company": "Acme", "period": "2023-2026"}],
        },
    }


@pytest.fixture
def ia(monkeypatch):
    estado = SimpleNamespace(pedidos=[])

    async def falsa(_sistema, pedido, _schema, **_):
        estado.pedidos.append(pedido)
        return SimpleNamespace(
            content={"assunto": "Candidatura — Dev Java", "carta": "Trabalho com Java há três anos..."},
            model="falso",
        )

    monkeypatch.setattr(servico, "generate_json", falsa)
    return estado


def test_carta_usa_o_curriculo_e_fica_guardada(busca, curriculo, ia):
    banco = _banco(pathr_resume=[curriculo])
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]

    atualizada = asyncio.run(servico.escrever_carta(banco, EU, linha))
    assert "Spring Boot" in ia.pedidos[0] and "Empresa 1" in ia.pedidos[0]
    assert servico.para_api(atualizada, EU["id"])["letter"].startswith("Trabalho com Java")
    assert atualizada["subject"] == "Candidatura — Dev Java"


def test_sem_curriculo_analisado_a_carta_e_recusada(busca, ia):
    banco = _banco(pathr_resume=[])
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]
    with pytest.raises(HTTPException) as erro:
        asyncio.run(servico.escrever_carta(banco, EU, linha))
    assert erro.value.status_code == 412


def test_vaga_que_pede_resposta_no_site_so_e_marcada(busca, curriculo, ia, monkeypatch):
    """Sem e-mail de contato, ninguém responde as perguntas no lugar da pessoa:
    a tela dá o link e registra que foi enviada."""
    enviados = []
    monkeypatch.setattr(rotas.email_service, "send_application", lambda **kw: enviados.append(kw) or True)
    banco = _banco(pathr_resume=[curriculo])
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]

    saida = asyncio.run(rotas.enviar(str(linha["id"]), rotas.PedidoDeEnvio(), PEDIDO, EU, banco))

    assert saida["status"] == "enviada" and saida["sent_at"]
    assert saida["url"] == linha["url"]  # o link para responder as perguntas
    assert enviados == []


def test_envio_por_email_leva_o_curriculo_em_anexo(busca, curriculo, ia, monkeypatch):
    enviados = []
    monkeypatch.setattr(rotas.email_service, "send_application", lambda **kw: enviados.append(kw) or True)
    monkeypatch.setattr(rotas, "_curriculo_em_anexo", lambda *_: ("curriculo-ana.pdf", "YmFzZTY0"))
    banco = _banco(pathr_resume=[curriculo])
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]

    saida = asyncio.run(
        rotas.enviar(str(linha["id"]), rotas.PedidoDeEnvio(email="vagas@empresa.com"), PEDIDO, EU, banco)
    )

    assert saida["status"] == "enviada" and saida["to_email"] == "vagas@empresa.com"
    assert enviados[0]["anexo_nome"] == "curriculo-ana.pdf"
    # A empresa responde para a pessoa, não para o PathR.
    assert enviados[0]["candidato_email"] == EU["email"]
    assert enviados[0]["carta"].startswith("Trabalho com Java")
    assert "candidatura_enviada" in banco.eventos()


def test_candidatura_de_outra_pessoa_nao_abre(busca):
    banco = _banco()
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]
    with pytest.raises(HTTPException) as erro:
        servico.uma(banco, "22222222-2222-2222-2222-222222222222", str(linha["id"]))
    assert erro.value.status_code == 404


def _banco_do_agendador(curriculos):
    return _banco(
        pathr_user=[EU],
        pathr_resume=curriculos,
        pathr_profile=[{"user_id": EU["id"], "notifications": {}}],
        pathr_email_log=[],
        pathr_activity=[],
        pathr_streak=[],
        pathr_weekly_checklist=[],
    )


def _pedido_do_cron():
    return SimpleNamespace(headers={jobs.CABECALHO: "segredo"}, client=None, url=SimpleNamespace(path="/jobs/emails"))


@pytest.fixture
def agendador(monkeypatch):
    monkeypatch.setattr(jobs.settings, "jobs_secret", "segredo")
    monkeypatch.setattr(
        jobs, "datetime", SimpleNamespace(now=lambda _tz=None: AGORA, fromisoformat=datetime.fromisoformat)
    )
    avisados: list = []
    monkeypatch.setattr(jobs.emails, "send_daily_jobs", lambda *a: avisados.append(a) or True)
    return avisados


def test_o_agendador_monta_a_fila_de_manha_uma_vez_por_dia(busca, curriculo, agendador):
    banco = _banco_do_agendador([curriculo])

    resposta = asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), banco))

    assert jobs.VAGAS_DO_DIA in resposta["tipos"]
    assert len(banco.linhas("pathr_application")) == servico.POR_DIA
    assert agendador[0][2][0]["titulo"].startswith("Pessoa Desenvolvedora")

    # Segunda rodada no mesmo dia: o registro de e-mail já barra.
    agendador.clear()
    resposta = asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), banco))
    assert jobs.VAGAS_DO_DIA not in resposta["tipos"] and agendador == []


def test_sem_curriculo_o_agendador_nao_monta_fila(busca, agendador):
    banco = _banco_do_agendador([])
    resposta = asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), banco))
    assert jobs.VAGAS_DO_DIA not in resposta["tipos"] and banco.linhas("pathr_application") == []
