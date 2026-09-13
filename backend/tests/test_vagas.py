"""Vagas: fontes, compatibilidade e a análise do que falta.

Offline. As fontes são trocadas por funções falsas; o que se segura é o que
erra em silêncio: casar tecnologia com palavra comum, dar nota a vaga cujo
anúncio ninguém leu, deixar uma fonte fora do ar derrubar as outras, e
esconder o curso que fecha a lacuna.
"""

import asyncio

import pytest

from app.config import settings
from app.routers import vagas as router
from app.services import vagas as V
from app.services.tag_seed import seed_rows
from tests.fake_supabase import FakeSupabase

CATALOGO = seed_rows()
for posicao, _tag in enumerate(CATALOGO):
    _tag["id"] = f"t{posicao}"


def _minhas(**niveis):
    return {slug: {"id": f"u-{slug}", "slug": slug, "proficiency": nivel, "is_target": False}
            for slug, nivel in niveis.items()}


@pytest.fixture(autouse=True)
def sem_estado(monkeypatch):
    V.limpar_cache()
    router._requisitos_por_texto.clear()
    monkeypatch.setattr(settings, "adzuna_app_id", "")
    monkeypatch.setattr(settings, "adzuna_app_key", "")
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "brave_api_key", "")
    yield
    V.limpar_cache()


# ── Casamento de tecnologias no texto ──────────────────────────────────────


def test_casa_nome_e_apelido_por_palavra_inteira():
    citadas = V.tags_citadas("Experiência com Java, Spring Boot, postgres e k8s.", CATALOGO)
    assert {"java", "spring-boot", "postgresql", "kubernetes"} <= set(citadas)
    assert "javascript" not in citadas


def test_palavra_comum_nao_vira_tecnologia():
    texto = "You will rest assured, express your ideas and take the next step with the rest of the team."
    citadas = V.tags_citadas(texto, CATALOGO)
    assert not {"rest", "express", "next-js"} & set(citadas)


def test_tecnologia_ambigua_vale_quando_escrita_como_tecnologia():
    citadas = V.tags_citadas("APIs REST com Express e C#", CATALOGO)
    assert {"rest", "express", "c-sharp"} <= set(citadas)


# ── Compatibilidade ─────────────────────────────────────────────────────────


def test_obrigatorio_pesa_o_dobro_e_parcial_vale_meio():
    minhas = _minhas(java=3, docker=1)
    compat = V.compatibilidade([("java", "Java", True), ("docker", "Docker", True), ("aws", "AWS", False)], minhas)
    # (2 + 1 + 0) / (2 + 2 + 1)
    assert compat == {"nota": 60, "tem": ["Java"], "parcial": ["Docker"], "falta": ["AWS"]}


def test_quero_aprender_nao_conta_como_ter():
    assert V.situacao("docker", _minhas(docker=0)) == "falta"


def test_termos_de_busca_metas_primeiro_e_so_stack():
    minhas = [
        {"name": "Scrum", "category": "metodologia", "proficiency": 5, "is_target": True},
        {"name": "Python", "category": "linguagem", "proficiency": 4, "is_target": False},
        {"name": "Java", "category": "linguagem", "proficiency": 2, "is_target": True},
        {"name": "React", "category": "frontend", "proficiency": 3, "is_target": False},
        {"name": "Go", "category": "linguagem", "proficiency": 1, "is_target": False},
    ]
    assert V.termos_de_busca(minhas) == ["Java", "Python", "React"]
    assert V.termos_de_busca([], "Desenvolvedor backend") == ["Desenvolvedor backend"]


def test_nivel_do_titulo():
    assert V.nivel_do_titulo("Desenvolvedor Java Sênior") == "senior"
    assert V.nivel_do_titulo("Dev Jr. Backend") == "junior"
    assert V.nivel_do_titulo("Engenheiro de Software Pleno") == "pleno"
    assert V.nivel_do_titulo("Engenheiro de Software") is None


# ── Fontes ──────────────────────────────────────────────────────────────────


def test_site_de_vaga_aceita_vaga_individual_e_recusa_listagem():
    assert V.site_de_vaga("https://www.linkedin.com/jobs/view/4012345678/") == "linkedin.com"
    assert V.site_de_vaga("https://www.vagas.com.br/vagas/v2645123/desenvolvedor-java") == "vagas.com.br"
    assert V.site_de_vaga("https://www.linkedin.com/jobs/search/?keywords=java") is None
    assert V.site_de_vaga("https://www.glassdoor.com.br/Vaga/brasil-java-vagas-SRCH_IL.htm") is None
    assert V.site_de_vaga("https://sitequalquer.com/jobs/view/1") is None


def _vaga(id_, titulo, descricao="", fonte="Gupy", **extra):
    return V.Vaga(id=id_, titulo=titulo, empresa="ACME", url=f"https://x/{id_}", fonte=fonte,
                  descricao=descricao, **extra)


def test_fonte_fora_do_ar_nao_derruba_as_outras(monkeypatch):
    async def gupy(_termo, _regiao=None):
        return [_vaga("gupy:1", "Dev Java", "Java e SQL")]

    async def remotive(_termo, _regiao=None):
        raise RuntimeError("fora")

    monkeypatch.setattr(V, "_gupy", gupy)
    monkeypatch.setattr(V, "_remotive", remotive)
    vagas, estado = asyncio.run(V.buscar(["Java"]))
    assert [v.id for v in vagas] == ["gupy:1"]
    assert estado == {"gupy": "ok", "remotive": "erro", "adzuna": "sem_chave", "busca": "sem_chave"}


def test_mesma_vaga_por_dois_termos_aparece_uma_vez_e_cache_evita_nova_chamada(monkeypatch):
    chamadas = []

    async def gupy(termo, _regiao=None):
        chamadas.append(termo)
        return [_vaga("gupy:1", "Dev Java Spring", "Java")]

    async def vazio(_termo, _regiao=None):
        return []

    monkeypatch.setattr(V, "_gupy", gupy)
    monkeypatch.setattr(V, "_remotive", vazio)
    vagas, _ = asyncio.run(V.buscar(["Java", "Spring Boot"]))
    assert len(vagas) == 1
    asyncio.run(V.buscar(["Java"]))
    assert sorted(chamadas) == ["Java", "Spring Boot"]
    assert V.vaga_guardada("gupy:1") is not None


# ── Listagem ────────────────────────────────────────────────────────────────


def test_listagem_ordena_por_compatibilidade_e_nao_da_nota_a_link_de_busca():
    vagas = [
        _vaga("a", "Dev Python", "Python, Django, AWS, Docker"),
        _vaga("b", "Dev Java", "Java, Spring Boot e SQL"),
        _vaga("c", "Dev Java", "Java Java Java", fonte="LinkedIn", extra={"so_link": True}),
    ]
    minhas = _minhas(java=3, **{"spring-boot": 2, "sql": 2})
    lista = V.para_tela(vagas, CATALOGO, minhas)
    # "a" não cita nada da stack nem do objetivo: sai.
    assert [linha["id"] for linha in lista] == ["b", "c"]
    assert lista[0]["compatibilidade"]["nota"] == 100
    assert lista[-1]["compatibilidade"]["nota"] is None


def test_trecho_da_adzuna_nao_ganha_nota():
    """O trecho que só cita "Java" daria 100% a uma vaga que pede muito mais."""
    vagas = [_vaga("adzuna:1", "Dev Java", "Desenvolvedor Java para projeto...", fonte="Adzuna",
                   extra={"so_trecho": True})]
    linha = V.para_tela(vagas, CATALOGO, _minhas(java=3))[0]
    assert linha["compatibilidade"]["nota"] is None and linha["so_trecho"] is True


def test_so_remotas():
    vagas = [_vaga("a", "Dev", "Java", remota=True), _vaga("b", "Dev", "Java", remota=False)]
    assert [l["id"] for l in V.para_tela(vagas, CATALOGO, _minhas(java=3), so_remotas=True)] == ["a"]


def test_nivel_diferente_do_perfil_desce():
    vagas = [_vaga("senior", "Dev Java Sênior", "Java"), _vaga("pleno", "Dev Java Pleno", "Java")]
    lista = V.para_tela(vagas, CATALOGO, _minhas(java=3), senioridade="pleno")
    assert [l["id"] for l in lista] == ["pleno", "senior"]


# ── Análise ─────────────────────────────────────────────────────────────────


def _achar(nome):
    citadas = V.tags_citadas(nome, CATALOGO)
    return next(iter(citadas.values()), None)


def test_analise_aponta_lacunas_com_curso_gratuito_primeiro():
    requisitos = [
        {"nome": "Java", "obrigatorio": True},
        {"nome": "AWS", "obrigatorio": True},
        {"nome": "Docker", "obrigatorio": False},
        {"nome": "Comunicação com stakeholders", "obrigatorio": True},
    ]
    analise = V.analisar(requisitos, "", CATALOGO, _achar, _minhas(java=3, docker=1), {"docker"})

    assert [l["nome"] for l in analise["lacunas"]] == ["AWS", "Docker"]
    aws, docker = analise["lacunas"]
    assert aws["situacao"] == "falta" and aws["cursos"] and aws["cursos"][0]["gratuito"]
    assert docker["situacao"] == "parcial" and docker["no_roadmap"] is True
    assert docker["user_tag_id"] == "u-docker"
    # Requisito fora do catálogo aparece, mas não vira lacuna sem caminho.
    fora = next(r for r in analise["requisitos"] if r["nome"].startswith("Comunicação"))
    assert fora["situacao"] == "desconhecido"
    # Java (2) + Docker parcial (0,5) sobre Java (2) + AWS (2) + Docker (1)
    assert analise["nota"] == 50


def test_analise_sem_ia_usa_as_tecnologias_do_texto():
    analise = V.analisar([], "Buscamos Kotlin e Kafka.", CATALOGO, _achar, {}, set())
    assert {r["nome"] for r in analise["requisitos"]} == {"Kotlin", "Kafka"}
    assert all(r["obrigatorio"] for r in analise["requisitos"])


# ── Router ──────────────────────────────────────────────────────────────────


def _banco():
    java = next(t["id"] for t in CATALOGO if t["slug"] == "java")
    return FakeSupabase(
        pathr_tag=[dict(t) for t in CATALOGO],
        pathr_user_tag=[{"id": "ut1", "user_id": "eu", "tag_id": java, "proficiency": 3, "is_target": False}],
        pathr_profile=[{"user_id": "eu", "target_role": "Desenvolvedor Java", "seniority": "Pleno", "state": "SP"}],
        pathr_roadmap=[],
    )


def test_endpoint_lista_pelos_termos_do_perfil(monkeypatch):
    async def gupy(_termo, _regiao=None):
        return [_vaga("gupy:9", "Dev Java Pleno", "Java e Docker", remota=True)]

    async def vazio(_termo, _regiao=None):
        return []

    monkeypatch.setattr(V, "_gupy", gupy)
    monkeypatch.setattr(V, "_remotive", vazio)
    resposta = asyncio.run(router.listar_vagas(q="", remotas=False, alcance="todas", current_user={"id": "eu"}, supabase=_banco()))
    assert resposta["termos"] == ["Java"]
    assert resposta["vagas"][0]["compatibilidade"] == {"nota": 50, "tem": ["Java"], "parcial": [], "falta": ["Docker"]}


def test_endpoint_analisa_vaga_da_listagem_e_guarda_a_extracao(monkeypatch):
    V._por_id["gupy:9"] = _vaga("gupy:9", "Dev Java", "Requisitos: Java, AWS. " * 30)
    chamadas = []

    class Resultado:
        content = {"titulo": "Dev Java", "requisitos": [{"nome": "Java", "obrigatorio": True},
                                                         {"nome": "AWS", "obrigatorio": True}]}

    async def ia(*_a, **_k):
        chamadas.append(1)
        return Resultado()

    monkeypatch.setattr(router, "generate_json", ia)
    for _ in range(2):
        resposta = asyncio.run(router.analisar_vaga(router.AnaliseVaga(vaga_id="gupy:9"),
                                                    current_user={"id": "eu"}, supabase=_banco()))
    assert resposta["empresa"] == "ACME"
    assert [l["nome"] for l in resposta["lacunas"]] == ["AWS"]
    assert resposta["nota"] == 50
    assert len(chamadas) == 1


def test_endpoint_recusa_texto_curto_demais():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as erro:
        asyncio.run(router.analisar_vaga(router.AnaliseVaga(texto="Dev Java"), current_user={"id": "eu"}, supabase=_banco()))
    assert erro.value.status_code == 422


# ── Inglês e alcance ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto,internacional,esperado",
    [
        ("Requisitos: Java e inglês avançado para reuniões.", False, "C1"),
        ("Diferencial: inglês intermediário.", False, "B1"),
        ("English level: B2 or higher.", False, "B2"),
        ("Fluent English is required.", False, "C1"),
        # "avançado" longe da palavra inglês não é pedido de inglês.
        ("Conhecimento avançado de SQL e Java. " + "Benefícios completos para você e sua família. " * 3 + "Inglês básico.", False, "A2"),
        ("Conhecimento avançado de SQL.", False, None),
        # Anúncio escrito em inglês, sem nível dito: o piso de trabalho.
        ("We are looking for a backend engineer with experience in Java and you will work with our team.", False, "B2"),
        ("Vaga remota em Java.", True, "B2"),
    ],
)
def test_nivel_de_ingles_exigido(texto, internacional, esperado):
    assert V.ingles_exigido(texto, internacional) == esperado


def test_situacao_do_ingles_na_regua_cefr():
    assert V.situacao_do_ingles("B2", "C1") == "tem"
    assert V.situacao_do_ingles("B2", "B2") == "tem"
    assert V.situacao_do_ingles("B2", "B1") == "parcial"
    assert V.situacao_do_ingles("C1", "A2") == "falta"
    assert V.situacao_do_ingles("B2", None) == "sem_nivel"
    assert V.situacao_do_ingles(None, "B2") is None


def test_alcance_separa_nacionais_de_internacionais_e_ingles_abaixo_desce():
    vagas = [
        _vaga("remotive:1", "Backend Engineer", "Java. Fluent English required.", fonte="Remotive", remota=True),
        _vaga("gupy:1", "Dev Java", "Java e SQL."),
        _vaga("gupy:2", "Dev Java", "Java e SQL. Inglês fluente obrigatório."),
    ]
    minhas = _minhas(java=3, sql=2)

    nacionais = V.para_tela(vagas, CATALOGO, minhas, alcance="nacionais", nivel_ingles="B1")
    assert [l["id"] for l in nacionais] == ["gupy:1", "gupy:2"]
    assert nacionais[1]["ingles"] == {"exigido": "C1", "seu": "B1", "situacao": "falta"}

    internacionais = V.para_tela(vagas, CATALOGO, minhas, alcance="internacionais", nivel_ingles="B1")
    assert [l["id"] for l in internacionais] == ["remotive:1"]
    assert internacionais[0]["internacional"] is True


def test_analise_poe_o_ingles_como_lacuna_com_curso_e_caminho_para_idiomas():
    texto = "Desenvolvedor Java. Requisitos: Java, inglês avançado."
    requisitos = [{"nome": "Java", "obrigatorio": True}, {"nome": "Inglês avançado", "obrigatorio": True}]
    analise = V.analisar(requisitos, texto, CATALOGO, _achar, _minhas(java=3), set(), nivel_ingles="B1")

    ingles = [r for r in analise["requisitos"] if r["nome"].startswith("Inglês")]
    assert len(ingles) == 1 and ingles[0]["nome"] == "Inglês C1" and ingles[0]["situacao"] == "falta"
    lacuna = next(l for l in analise["lacunas"] if l["nome"] == "Inglês C1")
    assert lacuna["idioma"] is True and lacuna["cursos"][0]["id"] == "ef-set"
    # Java (2 de 2) + Inglês em falta (0 de 2)
    assert analise["nota"] == 50


def test_sem_nivelamento_o_ingles_fica_fora_da_nota():
    analise = V.analisar([{"nome": "Java", "obrigatorio": True}], "Java e inglês fluente.", CATALOGO, _achar,
                         _minhas(java=3), set(), nivel_ingles=None)
    assert analise["ingles"]["situacao"] == "sem_nivel"
    assert analise["nota"] == 100


def test_vaga_so_entra_se_for_mesmo_sobre_o_termo():
    assert V.cita_o_termo("Java", "Senior Java Engineer", [], "")
    assert V.cita_o_termo("Java", "Backend Engineer", ["java", "spring"], "")
    assert V.cita_o_termo("Java", "Backend Engineer", [], "We use Java 21. Java experience required.")
    # JavaScript no rodapé não faz de um redator uma vaga de Java.
    assert not V.cita_o_termo("Java", "Freelance Copywriter", ["writing"], "Our site uses JavaScript. Java once.")


def test_adzuna_marca_remota_pelo_anuncio(monkeypatch):
    """A Adzuna não informa trabalho remoto: sem ler o anúncio, toda vaga dela
    sumia do filtro de remotas."""
    import httpx

    monkeypatch.setattr(settings, "adzuna_app_id", "id")
    monkeypatch.setattr(settings, "adzuna_app_key", "chave")
    resultados = {"results": [
        {"id": 1, "title": "Desenvolvedor Java - Trabalho Remoto", "description": "Java", "redirect_url": "https://a/1",
         "location": {"display_name": "Belo Horizonte, Minas Gerais"}},
        {"id": 2, "title": "Desenvolvedor Java", "description": "Presencial no centro.", "redirect_url": "https://a/2",
         "location": {"display_name": "São Paulo"}},
    ]}
    original = httpx.AsyncClient

    def cliente(**argumentos):
        return original(transport=httpx.MockTransport(lambda _p: httpx.Response(200, json=resultados)), **argumentos)

    monkeypatch.setattr(V.httpx, "AsyncClient", cliente)
    vagas = {v.id: v for v in asyncio.run(V._adzuna("Java"))}
    assert vagas["adzuna:1"].remota is True and vagas["adzuna:1"].local == "Remoto · Belo Horizonte, Minas Gerais"
    assert vagas["adzuna:2"].remota is None
    assert len(vagas) == 2



# ── Objetivo e stack: a vaga tem a cara da pessoa? ──────────────────────────


def test_vaga_que_so_pede_ingles_nao_aparece_para_dev():
    """Caso real: vagas sem nada a ver apareciam porque o currículo tinha inglês."""
    minhas = _minhas(java=3, **{"spring-boot": 3, "ingles": 4})
    for tag in minhas.values():
        tag["category"] = "idioma" if tag["slug"] == "ingles" else "linguagem"
    vagas = [
        _vaga("atendimento", "Analista de Customer Success", "Inglês fluente e boa comunicação."),
        _vaga("java", "Desenvolvedor Java", "Java, Spring Boot e inglês avançado."),
    ]
    lista = V.para_tela(vagas, CATALOGO, minhas)
    assert [l["id"] for l in lista] == ["java"]
    assert lista[0]["compatibilidade"]["tem"] == ["Java", "Spring Boot"]


def test_mais_stack_em_comum_vem_antes():
    minhas = _minhas(java=3, **{"spring-boot": 3, "oracle": 2, "mongodb": 2, "kafka": 2, "docker": 2})
    vagas = [
        _vaga("pouca", "Desenvolvedor", "Java e mais dez coisas: Go, Rust, Elixir, Scala, PHP."),
        _vaga("muita", "Desenvolvedor", "Java, Spring Boot, Oracle, MongoDB, Kafka e Docker; também Go."),
    ]
    lista = V.para_tela(vagas, CATALOGO, minhas)
    assert [l["id"] for l in lista] == ["muita", "pouca"]
    assert len(lista[0]["afinidade"]["stack_em_comum"]) == 6


def test_objetivo_traz_a_vaga_do_papel_e_da_tecnologia_pedida():
    objetivo = V.ler_objetivo("Quero ser desenvolvedor backend Java com Quarkus", CATALOGO)
    assert {"java", "quarkus"} <= objetivo.slugs and "backend" in objetivo.papeis

    vagas = [
        # Nada da stack atual, mas é exatamente o que o objetivo pede.
        _vaga("objetivo", "Engenheiro Backend", "Quarkus e Kotlin."),
        _vaga("fora", "Designer", "Figma e Illustrator."),
    ]
    lista = V.para_tela(vagas, CATALOGO, _minhas(python=3), objetivo=objetivo)
    assert [l["id"] for l in lista] == ["objetivo"]
    assert lista[0]["afinidade"]["objetivo"] is True


def test_busca_comeca_pelo_que_o_objetivo_cita():
    minhas = [
        {"slug": "python", "name": "Python", "category": "linguagem", "proficiency": 5, "is_target": True},
        {"slug": "java", "name": "Java", "category": "linguagem", "proficiency": 2, "is_target": False},
    ]
    assert V.termos_de_busca(minhas, objetivo_slugs={"java"})[0] == "Java"


# ── Região: presencial só no raio, remota sempre ────────────────────────────


def test_presencial_so_no_raio_e_remota_de_qualquer_lugar():
    """Caso real: quem mora em Vitória via vaga presencial em São Paulo."""
    regiao = V.regiao_do_perfil("Vitoria", "ES", 50)  # sem acento, como no cadastro
    assert regiao and regiao.cidade and regiao.cidade.nome == "Vitória"
    vagas = [
        _vaga("sp", "Dev Java", "Java.", remota=False, extra={"cidade": "São Paulo", "estado": "São Paulo"}),
        _vaga("serra", "Dev Java", "Java.", remota=False, extra={"cidade": "Serra", "estado": "Espírito Santo"}),
        _vaga("remota", "Dev Java", "Java.", remota=True),
        _vaga("sem-local", "Dev Java", "Java.", remota=None),
    ]
    lista = V.para_tela(vagas, CATALOGO, _minhas(java=3), regiao=regiao)
    assert {l["id"] for l in lista} == {"serra", "remota"}
    serra = next(l for l in lista if l["id"] == "serra")
    assert 15 <= serra["distancia_km"] <= 30 and serra["na_sua_regiao"] is True


def test_raio_zero_e_so_remotas_e_adzuna_localiza_pelas_coordenadas():
    vagas = [
        _vaga("perto", "Dev Java", "Java.", fonte="Adzuna", extra={"so_trecho": True, "lat": -20.14, "lon": -40.18}),
        _vaga("remota", "Dev Java", "Java.", remota=True),
    ]
    perto = V.para_tela(vagas, CATALOGO, _minhas(java=3), regiao=V.regiao_do_perfil("Vitória", "ES", 50))
    assert {l["id"] for l in perto} == {"perto", "remota"}
    so_remotas = V.para_tela(vagas, CATALOGO, _minhas(java=3), regiao=V.regiao_do_perfil("Vitória", "ES", 0))
    assert [l["id"] for l in so_remotas] == ["remota"]


def test_resultado_de_buscador_entra_quando_cita_cidade_do_raio():
    regiao = V.regiao_do_perfil("Vitória", "ES", 50)
    vagas = [
        _vaga("vv", "Desenvolvedor Java - Vila Velha", "", fonte="LinkedIn", extra={"so_link": True}),
        _vaga("poa", "Desenvolvedor Java - Porto Alegre", "", fonte="LinkedIn", extra={"so_link": True}),
    ]
    assert [l["id"] for l in V.para_tela(vagas, CATALOGO, _minhas(java=3), regiao=regiao)] == ["vv"]


def test_sugere_cidades_pelo_comeco_do_nome():
    from app.services import geo

    assert geo.sugerir("vit")[0].nome == "Vitória"
    # "pa" aqui é o começo de Paulo, não o Pará.
    assert geo.sugerir("sao pa")[0].nome == "São Paulo"
    assert [c.uf for c in geo.sugerir("Serra - ES")] == ["ES"]


# ── A nota que ordena, o anúncio em partes e o que falta ────────────────────


def test_a_de_cima_e_a_que_mais_combina():
    minhas = _minhas(java=3, **{"spring-boot": 3, "postgresql": 2, "docker": 2})
    vagas = [
        _vaga("fraca", "Analista", "Java, Go, Rust, Elixir, Scala, PHP, Ruby."),
        _vaga("forte", "Desenvolvedor Java Pleno", "Java, Spring Boot, PostgreSQL e Docker."),
        _vaga("media", "Desenvolvedor", "Java, Spring Boot e Kubernetes."),
    ]
    lista = V.para_tela(vagas, CATALOGO, minhas, senioridade="pleno")
    assert [l["id"] for l in lista] == ["forte", "media", "fraca"]
    notas = [l["combina"] for l in lista]
    assert notas == sorted(notas, reverse=True)


def test_plano_de_saude_nao_vira_setor_nem_lacuna():
    """Caso real: "falta Saúde" numa vaga de dev por causa do plano de saúde."""
    vagas = [_vaga("v", "Desenvolvedor Java", "Java e React. Benefícios: plano de saúde e banco de horas.")]
    lista = V.para_tela(vagas, CATALOGO, _minhas(java=3))
    nomes = [l["nome"] for l in lista[0]["lacunas"]]
    assert "Saúde" not in nomes and "Saúde" not in lista[0]["compatibilidade"]["falta"]
    assert "React" in nomes


def test_anuncio_em_partes_e_diferencial_vira_desejavel():
    texto = (
        "Somos uma fintech que cresce rápido.Responsabilidades e atribuiçõesDesenvolver APIs em Java."
        "Revisar código do time.Requisitos e qualificaçõesExperiência com Java;Spring Boot;"
        "Diferenciais:Kafka e React.Informações adicionaisVale-refeição."
    )
    sobre = V.sobre_a_vaga(texto)
    assert sobre["apresentacao"].startswith("Somos uma fintech")
    assert sobre["faz"] == ["Desenvolver APIs em Java", "Revisar código do time"]
    assert "Experiência com Java" in sobre["pede"]
    assert sobre["diferenciais"] == ["Kafka e React"]

    lista = V.para_tela(
        [_vaga("v", "Desenvolvedor Java", texto)], CATALOGO, _minhas(java=3), slugs_do_roadmap={"kafka"}
    )
    lacunas = {l["nome"]: l for l in lista[0]["lacunas"]}
    assert lacunas["Spring Boot"]["obrigatorio"] is True
    assert lacunas["Kafka"]["obrigatorio"] is False and lacunas["Kafka"]["no_roadmap"] is True
    # Obrigatório vem antes na lista do que falta.
    assert lista[0]["lacunas"][0]["nome"] == "Spring Boot"
    assert set(V.cursos_das_lacunas(lista)) >= {"spring-boot", "kafka"}


def test_atualizar_ignora_a_validade_mas_nao_martela_a_fonte(monkeypatch):
    chamadas = []

    async def gupy(termo, _regiao=None):
        chamadas.append(termo)
        return []

    async def vazio(_termo, _regiao=None):
        return []

    monkeypatch.setattr(V, "_gupy", gupy)
    monkeypatch.setattr(V, "_remotive", vazio)
    asyncio.run(V.buscar(["Java"]))
    asyncio.run(V.buscar(["Java"], atualizar=True))  # acabou de buscar: não vai de novo
    assert chamadas == ["Java"]
    chave = next(k for k in V._cache if k[0] == "gupy")
    V._cache[chave] = (V._cache[chave][0] - V._INTERVALO_MINIMO_S - 1, [])
    asyncio.run(V.buscar(["Java"], atualizar=True))
    assert chamadas == ["Java", "Java"]
