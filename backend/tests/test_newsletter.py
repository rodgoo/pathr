"""Newsletter do admin: agenda, busca em profundidade, envio e leitura.

O que este arquivo trava:
- a agenda: cada frequência cai nos dias certos, na hora escolhida ou depois,
  e uma edição por dia;
- "Java + Empregos" busca o ecossistema (Spring Boot, JVM…), não só "Java";
- o que já saiu não volta, e a mesma matéria não aparece duas vezes;
- só o super admin vê, configura, busca, envia e lê as edições;
- o cron respeita o interruptor geral, o segredo e quem deixou de ser admin;
- o e-mail escapa o que vem de página de terceiro e recusa link que não é http.

Offline: busca e Brevo são duplos; nada sai da máquina.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import ai_providers
from app.config import settings
from app.database import get_supabase
from app.deps import get_current_user
from app.main import app
from app.services import email as emails
from app.services import newsletter as nl
from tests.fake_supabase import FakeSupabase

# Guardada antes do duplo do `_ambiente`, para o teste que quer a função real.
_IMAGEM_DA_PAGINA_REAL = nl._imagem_da_pagina

ADMIN = {
    "id": "11111111-0000-0000-0000-000000000001",
    "email": "chefe@exemplo.com",
    "name": "Chefe Silva",
    "timezone_name": "America/Sao_Paulo",
}
ANA = {"id": "22222222-0000-0000-0000-000000000002", "email": "ana@exemplo.com", "name": "Ana"}
SEGREDO = "segredo-do-cron"
SP = ZoneInfo("America/Sao_Paulo")


def _item(titulo="Spring Boot 4 chega", url="https://exemplo.com/a", tema="Java", angulo="noticias", termo=None):
    return {
        "titulo": titulo,
        "url": url,
        "fonte": "exemplo.com",
        "resumo": "Resumo da própria fonte.",
        "publicado_em": "2026-10-09",
        "topico": tema,
        "categoria": angulo,
        "termo": termo or tema,
    }


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "super_admin_emails", ["chefe@exemplo.com"])
    monkeypatch.setattr(settings, "jobs_secret", SEGREDO)
    monkeypatch.setattr(settings, "tavily_api_key", "tvly-teste")
    monkeypatch.setattr(settings, "brave_api_key", "")

    # Sem rede: a foto que viria da página da matéria. Quem testa a foto
    # troca este duplo pelo que precisa.
    async def sem_foto(cliente, url):
        return None

    monkeypatch.setattr(nl, "_imagem_da_pagina", sem_foto)
    nl._cache_ecossistema.clear()
    yield
    nl._cache_ecossistema.clear()


@pytest.fixture
def banco():
    return FakeSupabase(
        pathr_user=[dict(ADMIN), dict(ANA)],
        pathr_newsletter_config=[],
        pathr_newsletter_issue=[],
        pathr_feature_flag=[],
        pathr_security_event=[],
    )


@pytest.fixture
def como(banco):
    atual = {}
    app.dependency_overrides[get_supabase] = lambda: banco
    app.dependency_overrides[get_current_user] = lambda: atual["user"]
    cliente = TestClient(app)

    def trocar(user):
        atual["user"] = user
        return cliente

    yield trocar
    app.dependency_overrides.clear()


@pytest.fixture
def brevo(monkeypatch):
    """Registra o que seria enviado, no lugar do Brevo."""
    enviados = []

    def falso(destino, nome, assunto, grupos):
        enviados.append({"destino": destino, "assunto": assunto, "grupos": grupos})
        return True

    monkeypatch.setattr(emails, "send_newsletter", falso)
    return enviados


def _config(**extra):
    base = {
        "enabled": True,
        "topics": ["Java"],
        "angles": ["trabalhos"],
        "frequency": "diaria",
        "weekdays": [0],
        "month_day": 1,
        "send_hour": 0,
        "items_per_topic": 2,
    }
    return {**base, **extra}


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

SEGUNDA = date(2026, 10, 12)  # weekday() == 0


@pytest.mark.parametrize(
    "frequencia,dias,esperado",
    [
        ("diaria", [], {0, 1, 2, 3, 4, 5, 6}),
        ("dias_uteis", [], {0, 1, 2, 3, 4}),
        ("fim_de_semana", [], {5, 6}),
        ("semanal", [2], {2}),
        ("personalizada", [0, 3, 6], {0, 3, 6}),
    ],
)
def test_cada_frequencia_cai_nos_dias_certos(frequencia, dias, esperado):
    cfg = {"frequency": frequencia, "weekdays": dias}
    caem = {i for i in range(7) if nl.e_dia_de_envio(cfg, SEGUNDA + timedelta(days=i))}
    assert caem == esperado


def test_mensal_usa_o_dia_do_mes():
    cfg = {"frequency": "mensal", "month_day": 15}
    assert nl.e_dia_de_envio(cfg, date(2026, 11, 15))
    assert not nl.e_dia_de_envio(cfg, date(2026, 11, 14))


def _agora(hora, dia=SEGUNDA):
    local = datetime(dia.year, dia.month, dia.day, hora, 5, tzinfo=SP)
    return local, local.astimezone(timezone.utc)


def test_sai_na_hora_escolhida_ou_depois_nunca_antes():
    cfg = _config(send_hour=8)
    assert not nl.esta_devida(cfg, *_agora(7))
    assert nl.esta_devida(cfg, *_agora(8))
    # Cron atrasado ou máquina que acordou tarde: ainda entrega.
    assert nl.esta_devida(cfg, *_agora(15))


def test_uma_edicao_por_dia():
    cfg = _config(send_hour=8, last_sent_on=SEGUNDA.isoformat())
    assert not nl.esta_devida(cfg, *_agora(9))
    assert nl.esta_devida(cfg, *_agora(9, SEGUNDA + timedelta(days=1)))


def test_busca_vazia_segura_a_proxima_tentativa_por_horas():
    local, utc = _agora(9)
    cfg = _config(send_hour=8, last_attempt_at=(utc - timedelta(hours=1)).isoformat())
    assert not nl.esta_devida(cfg, local, utc)
    cfg = _config(send_hour=8, last_attempt_at=(utc - timedelta(hours=4)).isoformat())
    assert nl.esta_devida(cfg, local, utc)


def test_desligada_ou_sem_tema_nunca_e_devida():
    assert not nl.esta_devida(_config(enabled=False), *_agora(9))
    assert not nl.esta_devida(_config(topics=[]), *_agora(9))


def test_proximo_envio_pula_para_o_dia_certo():
    cfg = _config(frequency="fim_de_semana", send_hour=8)
    local, _ = _agora(9)  # segunda
    assert nl.proximo_envio(cfg, local) == date(2026, 10, 17)  # sábado
    # Hoje é dia de envio e a hora ainda não chegou: é hoje.
    sabado, _ = _agora(7, date(2026, 10, 17))
    assert nl.proximo_envio(cfg, sabado) == date(2026, 10, 17)


# ---------------------------------------------------------------------------
# Combinações e ecossistema
# ---------------------------------------------------------------------------


def test_combinacao_aparece_como_tecnologia_mais_angulo():
    combos = nl.combinacoes(["Java", "Rust"], ["trabalhos", "novidades"])
    assert [c["rotulo"] for c in combos] == [
        "Java + Novidades",
        "Java + Empregos",
        "Rust + Novidades",
        "Rust + Empregos",
    ]
    java_empregos = combos[1]
    assert "Spring Boot" in java_empregos["ecossistema"]
    assert "vagas" in java_empregos["consulta"]


def test_temas_e_angulos_acumulam_sem_repetir():
    assert nl.normalizar_temas(["Java", "java ", "", "Rust"]) == ["Java", "Rust"]
    assert nl.normalizar_angulos(["polemicas", "inventado", "novidades"]) == ["novidades", "polemicas"]
    assert nl.normalizar_angulos([]) == ["noticias"]


def test_go_vai_a_busca_como_golang():
    assert nl.consulta_para("Go", "noticias") == "Golang"


# ---------------------------------------------------------------------------
# Busca em profundidade
# ---------------------------------------------------------------------------


@pytest.fixture
def busca_falsa(monkeypatch):
    """Tavily falso: cada consulta devolve duas matérias com URL própria."""
    consultas = []

    async def tavily(cliente, consulta, dias):
        consultas.append(consulta)
        slug = consulta.replace(" ", "-").lower().replace(".", "")
        return [
            (f"{consulta} 1", f"https://site.com/{slug}/1", f"trecho de {consulta}", "2026-10-09"),
            (f"{consulta} 2", f"https://site.com/{slug}/2", f"trecho de {consulta}", "2026-10-08"),
        ]

    async def brave(cliente, consulta, dias):
        return []

    monkeypatch.setattr(nl, "_tavily", tavily)
    monkeypatch.setattr(nl, "_brave", brave)
    return consultas


def test_java_empregos_busca_o_ecossistema_e_nao_so_java(busca_falsa):
    itens = asyncio.run(nl.procurar(["Java"], ["trabalhos"], 7, set(), por_consulta=4))
    assert any(c.startswith("Spring Boot") for c in busca_falsa)
    assert any(c.startswith("JVM") for c in busca_falsa)
    termos = {i["termo"] for i in itens}
    assert "Java" in termos and "Spring Boot" in termos
    # O item continua sob a tecnologia escolhida.
    assert {i["topico"] for i in itens} == {"Java"}
    assert {i["categoria"] for i in itens} == {"trabalhos"}


def test_rodizio_entre_termos_primeiros_itens_nao_sao_todos_da_busca_base(busca_falsa):
    itens = asyncio.run(nl.procurar(["Java"], ["noticias"], 7, set(), por_consulta=2))
    assert [i["termo"] for i in itens] == ["Java", "Spring Boot"]


def test_orcamento_de_buscas_nao_estoura_e_a_base_nunca_perde(busca_falsa, monkeypatch):
    monkeypatch.setattr(nl, "MAX_BUSCAS", 8)
    temas = ["Java", "Python", "Rust", "Go"]
    asyncio.run(nl.procurar(temas, ["noticias", "novidades"], 7, set()))
    assert len(busca_falsa) <= 8
    # 8 combinações = 8 buscas: o orçamento cabe só a base de cada uma.
    assert not any(c.startswith("Spring Boot") for c in busca_falsa)


def test_o_que_ja_saiu_nao_volta_nem_se_repete_na_mesma_edicao(busca_falsa):
    ja = {nl.chave_da_url("https://site.com/java/1")}
    itens = asyncio.run(nl.procurar(["Java"], ["noticias", "novidades"], 7, ja, por_consulta=5))
    urls = [nl.chave_da_url(i["url"]) for i in itens]
    assert nl.chave_da_url("https://site.com/java/1") not in urls
    assert len(urls) == len(set(urls))


def test_url_com_utm_e_barra_e_o_mesmo_link():
    assert nl.chave_da_url("https://www.Exemplo.com/a/?utm_source=x#topo") == nl.chave_da_url(
        "https://exemplo.com/a"
    )


def test_tecnologia_fora_do_mapa_usa_a_ia_so_para_termos_e_guarda_em_cache(monkeypatch, busca_falsa):
    chamadas = []

    async def ia(sistema, usuario, schema=None, **kw):
        chamadas.append(usuario)
        return SimpleNamespace(content={"termos": ["Zig stdlib", "zig build", "Zig stdlib"]})

    monkeypatch.setattr(ai_providers, "generate_json", ia)
    asyncio.run(nl.procurar(["Zig"], ["noticias"], 7, set()))
    asyncio.run(nl.procurar(["Zig"], ["noticias"], 7, set()))
    assert len(chamadas) == 1  # a segunda edição não gasta a IA de novo
    assert any(c.startswith("Zig stdlib") for c in busca_falsa)


def test_ia_fora_do_ar_nao_derruba_a_busca(monkeypatch, busca_falsa):
    async def ia(*a, **k):
        raise RuntimeError("cota")

    monkeypatch.setattr(ai_providers, "generate_json", ia)
    itens = asyncio.run(nl.procurar(["Zig"], ["noticias"], 7, set()))
    assert itens and {i["termo"] for i in itens} == {"Zig"}


def test_fonte_fora_do_ar_nao_derruba_a_outra(monkeypatch):
    import httpx

    async def quebrada(cliente, consulta, dias):
        raise httpx.ConnectError("sem rede")

    async def viva(cliente, consulta, dias):
        return [("Achou", "https://site.com/x", "t", None)]

    monkeypatch.setattr(nl, "_tavily", quebrada)
    monkeypatch.setattr(nl, "_brave", viva)
    itens = asyncio.run(nl.procurar(["Rust"], ["noticias"], 7, set()))
    assert [i["titulo"] for i in itens] == ["Achou"]


# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------


def _capturar_html(monkeypatch):
    capturado = {}
    monkeypatch.setattr(emails, "_send", lambda to, nome, assunto, html, **k: capturado.update(html=html) or True)
    return capturado


def test_email_mostra_a_combinacao_o_termo_e_escapa_o_que_vem_de_fora(monkeypatch):
    cap = _capturar_html(monkeypatch)
    item = _item(titulo="<script>alert(1)</script> Vaga", angulo="trabalhos", termo="Spring Boot")
    assert emails.send_newsletter("a@b.com", "Chefe Silva", "1 notícia: Java", [("Java", [item])])
    html = cap["html"]
    assert "Java + Empregos" in html
    assert "via Spring Boot" in html
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_email_recusa_link_que_nao_e_http(monkeypatch):
    cap = _capturar_html(monkeypatch)
    ruim = _item(url="javascript:alert(1)")
    bom = _item(titulo="Matéria boa", url="https://exemplo.com/boa")
    emails.send_newsletter("a@b.com", "x", "assunto", [("Java", [ruim, bom])])
    assert "javascript:" not in cap["html"]
    assert "Matéria boa" in cap["html"]


def test_email_sem_materia_nao_e_enviado(monkeypatch):
    cap = _capturar_html(monkeypatch)
    assert emails.send_newsletter("a@b.com", "x", "assunto", []) is False
    assert cap == {}


def test_email_traz_a_foto_da_materia_e_so_em_https(monkeypatch):
    cap = _capturar_html(monkeypatch)
    com = _item(titulo="Com foto", url="https://e.com/c")
    com["imagem"] = "https://img.exemplo.com/capa.jpg"
    insegura = _item(titulo="Foto insegura", url="https://e.com/i")
    insegura["imagem"] = "http://img.exemplo.com/x.jpg"
    emails.send_newsletter("a@b.com", "x", "assunto", [("Java", [com, insegura])])
    html = cap["html"]
    assert 'src="https://img.exemplo.com/capa.jpg"' in html
    assert "http://img.exemplo.com" not in html


def test_foto_so_https_na_selecao_e_na_busca():
    assert nl._imagem_valida("https://x.com/a.png") == "https://x.com/a.png"
    assert nl._imagem_valida("http://x.com/a.png") is None
    assert nl._imagem_valida("data:image/png;base64,AAAA") is None
    assert nl._imagem_valida("javascript:alert(1)") is None
    limpo = nl.limpar_selecao([{**_item(), "imagem": "http://x.com/a.png"}])
    assert limpo[0]["imagem"] is None


def test_brave_traz_a_miniatura_junto(monkeypatch):
    async def brave(cliente, consulta, dias):
        return [("Achou", "https://site.com/x", "t", None, "https://imgs.brave.com/t.jpg")]

    async def tavily(cliente, consulta, dias):
        return []

    monkeypatch.setattr(nl, "_tavily", tavily)
    monkeypatch.setattr(nl, "_brave", brave)
    itens = asyncio.run(nl.procurar(["Rust"], ["noticias"], 7, set()))
    assert itens[0]["imagem"] == "https://imgs.brave.com/t.jpg"


def test_sem_miniatura_a_foto_vem_da_propria_pagina(monkeypatch, busca_falsa):
    pedidas = []

    async def da_pagina(cliente, url):
        pedidas.append(url)
        return "https://cdn.exemplo.com/og.jpg"

    monkeypatch.setattr(nl, "_imagem_da_pagina", da_pagina)
    itens = asyncio.run(nl.procurar(["Rust"], ["noticias"], 7, set(), por_consulta=2))
    assert itens and all(i["imagem"] == "https://cdn.exemplo.com/og.jpg" for i in itens)
    # Só as matérias escolhidas têm a página baixada, e não todos os candidatos.
    assert len(pedidas) == len(itens)


def test_pagina_sem_foto_nao_derruba_a_materia(monkeypatch):
    # A função REAL de página, com o download falhando dentro dela, como o
    # `saida.baixar` falharia numa página fora do ar.
    async def baixar(cliente, url):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(nl, "_imagem_da_pagina", _IMAGEM_DA_PAGINA_REAL)
    monkeypatch.setattr(nl.saida_http, "baixar", baixar)

    async def tavily(cliente, consulta, dias):
        return [("Matéria", "https://site.com/m", "t", None)]

    async def brave(cliente, consulta, dias):
        return []

    monkeypatch.setattr(nl, "_tavily", tavily)
    monkeypatch.setattr(nl, "_brave", brave)
    itens = asyncio.run(nl.procurar(["Rust"], ["noticias"], 7, set()))
    assert [i["titulo"] for i in itens] == ["Matéria"]
    assert itens[0]["imagem"] is None


def test_assunto_diz_o_que_veio():
    itens = [_item(tema="Rust"), _item(tema="Kubernetes", url="https://e.com/2"), _item(tema="Rust", url="https://e.com/3")]
    assert nl.assunto_da_edicao(itens) == "3 notícias: Rust e Kubernetes"
    assert nl.assunto_da_edicao([_item()]) == "1 notícia: Java"


# ---------------------------------------------------------------------------
# Rotas do admin
# ---------------------------------------------------------------------------


def test_so_super_admin_alcanca_as_rotas(como):
    for chamada in (
        lambda c: c.get("/admin/newsletter"),
        lambda c: c.put("/admin/newsletter/config", json=_config()),
        lambda c: c.post("/admin/newsletter/buscar", json={}),
        lambda c: c.post("/admin/newsletter/enviar", json={}),
        lambda c: c.get("/newsletter"),
        lambda c: c.get(f"/newsletter/{'0' * 8}-0000-0000-0000-{'0' * 12}"),
    ):
        assert chamada(como(ANA)).status_code == 404


def test_salvar_e_ler_a_configuracao(como):
    r = como(ADMIN).put(
        "/admin/newsletter/config",
        json=_config(topics=["Java", "Rust"], angles=["trabalhos", "novidades"], frequency="personalizada",
                     weekdays=[4, 0], send_hour=7),
    )
    assert r.status_code == 200, r.text
    corpo = como(ADMIN).get("/admin/newsletter").json()
    assert corpo["config"]["weekdays"] == [0, 4]
    assert corpo["config"]["send_hour"] == 7
    assert corpo["config"]["next_send_on"] is not None
    assert corpo["fuso"] == "America/Sao_Paulo"
    assert [c["rotulo"] for c in corpo["combinacoes"]][:2] == ["Java + Novidades", "Java + Empregos"]


@pytest.mark.parametrize(
    "mudanca",
    [
        {"topics": []},  # ligada sem tecnologia
        {"frequency": "semanal", "weekdays": [1, 2]},  # semanal é um dia só
        {"frequency": "personalizada", "weekdays": []},
        {"send_hour": 24},
        {"month_day": 31},
        {"topics": [f"T{i}" for i in range(8)], "angles": ["noticias", "novidades", "trabalhos", "polemicas"]},
    ],
)
def test_configuracao_invalida_e_recusada(como, mudanca):
    assert como(ADMIN).put("/admin/newsletter/config", json=_config(**mudanca)).status_code == 422


def test_buscar_sem_fonte_configurada_explica(como, monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    r = como(ADMIN).post("/admin/newsletter/buscar", json={"topics": ["Java"]})
    assert r.status_code == 409 and "TAVILY_API_KEY" in r.json()["detail"]


def test_buscar_devolve_combinacoes_e_materias_sem_enviar(como, busca_falsa, brevo):
    r = como(ADMIN).post("/admin/newsletter/buscar", json={"topics": ["Java"], "angles": ["trabalhos"]})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["combinacoes"][0]["rotulo"] == "Java + Empregos"
    assert corpo["itens"]
    assert brevo == []


def test_enviar_as_materias_escolhidas_registra_a_edicao(como, banco, brevo):
    r = como(ADMIN).post(
        "/admin/newsletter/enviar", json={"itens": [_item(), _item(url="https://e.com/2", titulo="Outra")]}
    )
    assert r.status_code == 200 and r.json()["enviado"] is True
    assert brevo[0]["destino"] == "chefe@exemplo.com"
    assert len(banco.linhas("pathr_newsletter_issue")) == 1
    # Envio manual não consome a edição agendada do dia.
    assert not banco.linhas("pathr_newsletter_config")


def test_enviar_recusa_materia_so_com_link_invalido(como, brevo):
    r = como(ADMIN).post("/admin/newsletter/enviar", json={"itens": [_item(url="javascript:alert(1)")]})
    assert r.status_code == 422
    assert brevo == []


def test_interruptor_geral_desligado_trava_o_envio_manual(como, banco, brevo):
    banco.tabelas["pathr_feature_flag"].append({"key": "newsletter_ativa", "state": "ninguem"})
    r = como(ADMIN).post("/admin/newsletter/enviar", json={"itens": [_item()]})
    assert r.status_code == 409
    assert brevo == []


def test_leitura_lista_e_abre_a_edicao_agrupada(como, banco, brevo):
    como(ADMIN).post(
        "/admin/newsletter/enviar",
        json={"itens": [_item(), _item(tema="Rust", url="https://e.com/r", titulo="Rust 2")]},
    )
    lista = como(ADMIN).get("/newsletter").json()["edicoes"]
    assert len(lista) == 1 and lista[0]["quantidade"] == 2
    detalhe = como(ADMIN).get(f"/newsletter/{lista[0]['id']}").json()
    assert [g["topico"] for g in detalhe["grupos"]] == ["Java", "Rust"]
    assert como(ADMIN).get("/newsletter/nao-e-uuid").status_code == 404


# ---------------------------------------------------------------------------
# O cron
# ---------------------------------------------------------------------------

CRON = {"X-Pathr-Jobs-Secret": SEGREDO}


@pytest.fixture
def procura_falsa(monkeypatch):
    chamadas = []

    async def procurar(temas, angulos, dias, ja, por_consulta=2):
        chamadas.append((list(temas), list(angulos), dias))
        return [_item(titulo=f"Notícia {len(chamadas)}", url=f"https://e.com/{len(chamadas)}", angulo="trabalhos")]

    monkeypatch.setattr(nl, "procurar", procurar)
    return chamadas


def _banco_com_config(banco, **extra):
    banco.tabelas["pathr_newsletter_config"].append({"user_id": ADMIN["id"], **_config(**extra)})


def test_cron_exige_o_segredo(como):
    cliente = como(ANA)
    assert cliente.post("/jobs/newsletter").status_code == 401
    assert cliente.post("/jobs/newsletter", headers={"X-Pathr-Jobs-Secret": "errado"}).status_code == 401


def test_cron_envia_uma_vez_por_dia(como, banco, brevo, procura_falsa):
    _banco_com_config(banco)
    cliente = como(ANA)
    primeira = cliente.post("/jobs/newsletter", headers=CRON).json()
    assert primeira == {"ativa": True, "avaliadas": 1, "enviadas": 1}
    assert brevo[0]["destino"] == "chefe@exemplo.com"
    hoje = datetime.now(timezone.utc).astimezone(SP).date().isoformat()
    assert banco.linhas("pathr_newsletter_config")[0]["last_sent_on"] == hoje
    assert cliente.post("/jobs/newsletter", headers=CRON).json()["enviadas"] == 0
    assert len(brevo) == 1


def test_cron_usa_a_configuracao_salva_incluindo_os_angulos(como, banco, brevo, procura_falsa):
    _banco_com_config(banco, topics=["Java", "Rust"], angles=["trabalhos", "polemicas"])
    como(ANA).post("/jobs/newsletter", headers=CRON)
    temas, angulos, _ = procura_falsa[0]
    assert temas == ["Java", "Rust"] and angulos == ["trabalhos", "polemicas"]


def test_cron_com_interruptor_geral_desligado_nao_faz_nada(como, banco, brevo, procura_falsa):
    _banco_com_config(banco)
    banco.tabelas["pathr_feature_flag"].append({"key": "newsletter_ativa", "state": "ninguem"})
    corpo = como(ANA).post("/jobs/newsletter", headers=CRON).json()
    assert corpo == {"ativa": False, "avaliadas": 0, "enviadas": 0}
    assert brevo == [] and procura_falsa == []


def test_cron_dia_sem_noticia_nao_envia_e_segura_a_proxima_busca(como, banco, brevo, monkeypatch):
    buscas = []

    async def vazia(*a, **k):
        buscas.append(1)
        return []

    monkeypatch.setattr(nl, "procurar", vazia)
    _banco_com_config(banco)
    cliente = como(ANA)
    assert cliente.post("/jobs/newsletter", headers=CRON).json()["enviadas"] == 0
    assert banco.linhas("pathr_newsletter_config")[0]["last_attempt_at"]
    cliente.post("/jobs/newsletter", headers=CRON)
    assert len(buscas) == 1  # a segunda hora não refez a busca
    assert brevo == []


def test_cron_nao_envia_para_quem_deixou_de_ser_admin(como, banco, brevo, procura_falsa, monkeypatch):
    _banco_com_config(banco)
    monkeypatch.setattr(settings, "super_admin_emails", [])
    assert como(ANA).post("/jobs/newsletter", headers=CRON).json()["enviadas"] == 0
    assert brevo == [] and procura_falsa == []


def test_falha_do_brevo_nao_trava_o_dia(como, banco, procura_falsa, monkeypatch):
    monkeypatch.setattr(emails, "send_newsletter", lambda *a, **k: False)
    _banco_com_config(banco)
    assert como(ANA).post("/jobs/newsletter", headers=CRON).json()["enviadas"] == 0
    assert banco.linhas("pathr_newsletter_config")[0].get("last_sent_on") is None
    assert banco.linhas("pathr_newsletter_issue") == []
