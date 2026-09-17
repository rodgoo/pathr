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


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Envie seu currículo para vagas@empresa.com até sexta.", "vagas@empresa.com"),
        ("Dúvidas: contato@empresa.com. Currículos: rh@empresa.com", "rh@empresa.com"),
        ("Responda para no-reply@empresa.com", None),
        ("Aplique pelo site da empresa.", None),
    ],
)
def test_email_de_contato_sai_do_anuncio(texto, esperado):
    assert servico.email_do_anuncio(texto) == esperado


def test_envio_automatico_respeita_nota_email_e_teto(busca, curriculo, ia, monkeypatch):
    """Só sai sozinho o que dá para enviar de verdade e combina o bastante."""
    enviados = []
    monkeypatch.setattr(servico.emails, "send_application", lambda **kw: enviados.append(kw) or True)
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("curriculo-ana.pdf", "YmFzZTY0"))
    banco = _banco(pathr_resume=[curriculo])
    linhas = [
        {"id": "a1", "title": "Java sênior", "company": "Boa", "score": 88, "to_email": "vagas@boa.com", "snippet": "Java"},
        {"id": "a2", "title": "Java júnior", "company": "Fraca", "score": 40, "to_email": "vagas@fraca.com", "snippet": "Java"},
        {"id": "a3", "title": "Java pleno", "company": "SemEmail", "score": 95, "to_email": None, "snippet": "Java"},
    ]
    for linha in linhas:
        banco.tabelas["pathr_application"].append({**linha, "user_id": EU["id"], "status": "sugerida"})

    enviadas = asyncio.run(servico.enviar_automaticamente(banco, EU, linhas))

    # Nota baixa e vaga sem e-mail ficam na fila para a pessoa decidir.
    assert [linha["id"] for linha in enviadas] == ["a1"]
    assert enviados[0]["to_email"] == "vagas@boa.com"
    situacoes = {l["id"]: l["status"] for l in banco.linhas("pathr_application")}
    assert situacoes == {"a1": "enviada", "a2": "sugerida", "a3": "sugerida"}


def test_envio_automatico_para_no_teto_do_dia(busca, curriculo, ia, monkeypatch):
    monkeypatch.setattr(servico.emails, "send_application", lambda **kw: True)
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("cv.pdf", "YmFzZTY0"))
    banco = _banco(pathr_resume=[curriculo])
    linhas = []
    for i in range(servico.MAXIMO_AUTOMATICO + 3):
        linha = {"id": f"x{i}", "title": "Java", "company": "Empresa", "score": 90, "to_email": f"vagas{i}@e.com", "snippet": "Java"}
        linhas.append(linha)
        banco.tabelas["pathr_application"].append({**linha, "user_id": EU["id"], "status": "sugerida"})

    assert len(asyncio.run(servico.enviar_automaticamente(banco, EU, linhas))) == servico.MAXIMO_AUTOMATICO


def test_email_recusado_nao_marca_como_enviada(busca, curriculo, ia, monkeypatch):
    monkeypatch.setattr(servico.emails, "send_application", lambda **kw: False)
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("cv.pdf", "YmFzZTY0"))
    banco = _banco(pathr_resume=[curriculo])
    linha = {"id": "a1", "title": "Java", "company": "Boa", "score": 90, "to_email": "vagas@boa.com", "snippet": "Java"}
    banco.tabelas["pathr_application"].append({**linha, "user_id": EU["id"], "status": "sugerida"})

    assert asyncio.run(servico.enviar_automaticamente(banco, EU, [linha])) == []
    assert banco.linhas("pathr_application")[0]["status"] == "sugerida"


def test_respostas_do_formulario_usam_perfil_e_curriculo(busca, curriculo, monkeypatch):
    pedidos = []

    async def falsa(_sistema, pedido, _schema, **_):
        pedidos.append(pedido)
        return SimpleNamespace(
            content={"respostas": [{"pergunta": "Pretensão salarial", "resposta": "R$ 9.000"}]}, model="falso"
        )

    monkeypatch.setattr(servico, "generate_json", falsa)
    banco = _banco(
        pathr_resume=[curriculo],
        pathr_profile=[{"user_id": EU["id"], "salary_expectation": "R$ 9.000", "availability": "30 dias"}],
        pathr_english_profile=[{"user_id": EU["id"], "language": "en", "cefr_level": "B2"}],
    )
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]

    atualizada = asyncio.run(servico.escrever_respostas(banco, EU, linha))

    assert "R$ 9.000" in pedidos[0] and "30 dias" in pedidos[0] and "B2" in pedidos[0]
    assert servico.para_api(atualizada, EU["id"])["answers"][0]["resposta"] == "R$ 9.000"


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


def test_agendador_envia_sozinho_so_quando_a_pessoa_ligou(busca, curriculo, ia, agendador, monkeypatch):
    """O envio automático é escolha: desligado, a fila só espera na tela."""
    enviados = []
    monkeypatch.setattr(servico.emails, "send_application", lambda **kw: enviados.append(kw) or True)
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("cv.pdf", "YmFzZTY0"))
    # A primeira vaga passa a trazer e-mail de contato no anúncio.
    busca.vagas[0]["sobre"] = {"pede": "Java. Envie seu currículo para vagas@empresa1.com"}

    desligado = _banco_do_agendador([curriculo])
    asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), desligado))
    assert enviados == []
    assert {l["status"] for l in desligado.linhas("pathr_application")} == {"sugerida"}

    ligado = _banco_do_agendador([curriculo])
    ligado.tabelas["pathr_profile"][0]["notifications"] = {jobs.AUTOMATICO: True}
    asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), ligado))

    assert [e["to_email"] for e in enviados] == ["vagas@empresa1.com"]
    situacoes = sorted(l["status"] for l in ligado.linhas("pathr_application"))
    assert situacoes == ["enviada", "sugerida", "sugerida", "sugerida", "sugerida"]
    # O e-mail do dia diz o que já saiu em nome da pessoa.
    assert [v["enviada"] for v in agendador[-1][2]].count(True) == 1


def test_sem_curriculo_o_agendador_nao_monta_fila(busca, agendador):
    banco = _banco_do_agendador([])
    resposta = asyncio.run(jobs.disparar_avisos(_pedido_do_cron(), banco))
    assert jobs.VAGAS_DO_DIA not in resposta["tipos"] and banco.linhas("pathr_application") == []


# --- o passo a passo, o banco de respostas e os números do período ---------


def test_perguntas_redundantes_caem_na_mesma_chave():
    """"Nome completo", "Nome" e "Full name" são a mesma pergunta — é isso que
    faz a resposta dada uma vez valer em qualquer site."""
    from app.services import perguntas

    assert perguntas.chave("Nome completo") == perguntas.chave("Full name") == "nome"
    assert perguntas.chave("Currículo (PDF)") == perguntas.chave("Resume") == "curriculo"
    assert perguntas.chave("Endereço") == perguntas.chave("Logradouro") == "endereco"
    assert perguntas.chave("Pretensão salarial") == perguntas.chave("Salary expectation") == "pretensao"
    # Sensível e aberta nunca viram resposta automática.
    assert perguntas.e_sensivel("Qual seu gênero?") and not perguntas.reutilizavel("Qual seu gênero?")
    assert perguntas.e_aberta("Por que você quer trabalhar aqui?")


def test_banco_guarda_a_resposta_e_ela_volta_na_proxima_vaga():
    banco = _banco(pathr_answer_bank=[])
    guardadas = servico.guardar_respostas(banco, EU["id"], [
        {"pergunta": "Nome completo", "resposta": "Ana Souza"},
        {"pergunta": "Telefone", "resposta": "(27) 99999-0000"},
        # Sensível não entra nem se a pessoa responder.
        {"pergunta": "Qual seu gênero?", "resposta": "prefiro não dizer"},
    ])
    assert guardadas == 2

    guardado = servico.banco_de_respostas(banco, EU["id"])
    # Outro site pergunta "Full name": a resposta já está lá.
    assert guardado[servico.perguntas.chave("Full name")] == "Ana Souza"
    assert "sensivel:genero" not in guardado


def test_preparar_monta_o_passo_a_passo_e_diz_o_que_falta(busca, curriculo, ia, monkeypatch):
    monkeypatch.setattr(servico, "curriculo_em_anexo", lambda *_: ("cv.pdf", "YmFzZTY0"))
    banco = _banco(
        pathr_resume=[curriculo],
        pathr_answer_bank=[],
        pathr_profile=[{"user_id": EU["id"], "city": "Vitória", "salary_expectation": "R$ 9.000"}],
        pathr_english_profile=[],
    )
    linha = asyncio.run(servico.montar_fila(banco, EU, agora=AGORA))[0]

    pronta = servico.para_api(asyncio.run(servico.preparar(banco, EU, linha)), EU["id"])

    passos = {p["passo"]: p["situacao"] for p in pronta["steps"]}
    assert passos["anuncio"] == "feito" and passos["curriculo"] == "feito" and passos["carta"] == "feito"
    # O que o perfil já sabe entra respondido; o resto vira campo na tela.
    respondidas = {r["chave"] for r in pronta["answers"]}
    assert {"nome", "email", "cidade", "pretensao"} <= respondidas
    pendentes = {p["chave"] for p in pronta["pending"]}
    assert "telefone" in pendentes  # ninguém informou ainda
    # Sem e-mail de contato, o envio aponta para o site da vaga.
    assert passos["envio"] == "pendente"


def test_numeros_de_hoje_ontem_e_da_semana():
    from datetime import date as tipo_data

    hoje = tipo_data(2026, 9, 16)
    linhas = [
        {"status": "enviada", "sent_at": "2026-09-16T10:00:00+00:00"},
        {"status": "enviada", "sent_at": "2026-09-16T18:00:00+00:00"},
        {"status": "enviada", "sent_at": "2026-09-15T09:00:00+00:00"},
        {"status": "enviada", "sent_at": "2026-09-12T09:00:00+00:00"},
        {"status": "enviada", "sent_at": "2026-09-01T09:00:00+00:00"},  # fora da semana
        {"status": "sugerida", "sent_at": None},
    ]
    assert servico.quantas_enviadas(linhas, hoje) == {"hoje": 2, "ontem": 1, "ultimos7": 4}
