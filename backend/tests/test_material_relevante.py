"""Material que trata do assunto: guia de criptomoedas não é material de Docker.

O relato, com print: no módulo "Docker" apareciam "Um Guia Para Iniciantes Sobre Como Investir Em Criptomoedas" e
"O Guia de Renda Passiva em Staking para Novatos" (coinmarketcap.com) e um exercício do beecrowd sem relação alguma.
A causa: todo resultado de busca recebia no mínimo 40 pontos e a única checagem depois era "o link abre" — nada
perguntava se a página falava do assunto. O catálogo é GLOBAL, então o lixo servia todo mundo que estuda Docker.
"""

import pytest

from app.services import resource_search as rs

CRIPTO_1 = dict(
    title="Um Guia Para Iniciantes Sobre Como Investir Em Criptomoedas",
    description="Aprenda a comprar Bitcoin e outras criptomoedas com segurança na sua primeira exchange.",
    url="https://coinmarketcap.com/pt-br/academy/article/guia-para-iniciantes-sobre-como-investir-em-criptomoedas",
)
CRIPTO_2 = dict(
    title="O Guia de Renda Passiva em Staking para Novatos",
    description="Como ganhar renda passiva fazendo staking de tokens em redes proof-of-stake.",
    url="https://coinmarketcap.com/pt-br/academy/article/renda-passiva-em-staking",
)
BEECROWD = dict(
    title="1001 - Respostas dos exercicios - beecrowd",
    description="Resolva o problema Extremely Basic e envie a sua solução.",
    url="https://judge.beecrowd.com/pt/problems/view/1001",
)


@pytest.mark.parametrize("lixo", [CRIPTO_1, CRIPTO_2, BEECROWD])
def test_o_lixo_do_print_nao_trata_de_docker(lixo):
    assert rs.fala_do_assunto("Docker", lixo["title"], lixo["description"], lixo["url"]) is False


@pytest.mark.parametrize(
    "assunto, titulo, url",
    [
        ("Docker", "APRENDA DOCKER DO ZERO | TUTORIAL COMPLETO COM DEPLOY", "https://www.youtube.com/watch?v=abc"),
        ("Docker", "Get started with Docker", "https://docs.docker.com/get-started/"),
        ("Docker", "Guia de containers", "https://exemplo.com/docker-para-iniciantes"),  # o assunto só no endereço
        ("Git e GitHub Actions", "Automatize testes com GitHub Actions", "https://docs.github.com/pt/actions"),
        ("Spring Boot", "Construindo uma API REST com Spring Boot", "https://spring.io/guides"),
        ("Kubernetes", "Kubernetes: primeiros passos", "https://kubernetes.io/pt-br/docs/tutorials/"),
        ("PostgreSQL", "Índices no PostgreSQL", "https://www.postgresql.org/docs/"),
    ],
)
def test_material_do_assunto_passa(assunto, titulo, url):
    assert rs.fala_do_assunto(assunto, titulo, None, url) is True


def test_acento_e_caixa_nao_atrapalham():
    assert rs.fala_do_assunto("Programação Orientada a Objetos", "Programacao orientada a objetos em Java", None, "https://e.com")
    assert rs.fala_do_assunto("DOCKER", "docker para iniciantes")


def test_o_termo_precisa_comecar_uma_palavra():
    """"net" não acha "internet", mas "git" acha "GitHub": prefixo de palavra, não pedaço qualquer."""
    assert not rs.fala_do_assunto(".NET", "Como funciona a internet", "https://e.com/internet")
    assert rs.fala_do_assunto("Git", "GitHub para equipes", "https://github.com")


def test_palavra_generica_do_nome_do_modulo_nao_conta_como_assunto():
    """"Fundamentos de DevOps" não pode aceitar tudo que tem "fundamentos" no título."""
    assert not rs.fala_do_assunto("Fundamentos de DevOps", "Fundamentos de investimentos para iniciantes", None, "https://e.com")
    assert rs.fala_do_assunto("Fundamentos de DevOps", "O que é DevOps", None, "https://e.com")


@pytest.mark.parametrize("assunto", ["C", "C++", "R", "", "   "])
def test_assunto_sem_ancora_nao_e_julgado(assunto):
    """Recusar tudo por não ter o que comparar apagaria a biblioteca inteira dessas linguagens."""
    assert rs.fala_do_assunto(assunto, "qualquer coisa", None, "https://e.com") is True


def test_assunto_com_varias_palavras_pede_a_metade():
    assert rs.fala_do_assunto("Clean Code", "Clean Code na prática", None, "https://e.com")
    assert rs.fala_do_assunto("Clean Code", "Boas práticas de code review", None, "https://e.com"), "uma de duas"
    assert not rs.fala_do_assunto("Clean Code", "Receita de bolo de cenoura", None, "https://e.com")


# --- na curadoria de verdade --------------------------------------------------


def _busca(**campos):
    return rs.Candidate(kind="article", provider="coinmarketcap.com", language="pt", source="tavily", **campos)


@pytest.fixture
def fontes(monkeypatch):
    """Cada fonte devolve o que o teste mandar; link sempre abre; a IA só é chamada se o teste permitir."""
    estado = {"artigos": [], "videos": [], "ia": [], "ia_chamada": 0}

    async def artigos(_assunto):
        return list(estado["artigos"])

    async def videos(_assunto):
        return list(estado["videos"])

    async def vazio(_assunto):
        return []

    async def ia(_assunto, _categoria):
        estado["ia_chamada"] += 1
        return list(estado["ia"])

    async def abre(candidatos):
        return list(candidatos)

    monkeypatch.setattr(rs, "_articles", artigos)
    monkeypatch.setattr(rs, "_youtube", videos)
    monkeypatch.setattr(rs, "_documentacao", vazio)
    monkeypatch.setattr(rs, "_exercicios", vazio)
    monkeypatch.setattr(rs, "_ai_fallback", ia)
    monkeypatch.setattr(rs, "_keep_reachable", abre)
    return estado


async def test_a_curadoria_de_docker_nao_grava_criptomoedas(fontes):
    fontes["artigos"] = [
        _busca(**CRIPTO_1, quality_score=75),
        _busca(**CRIPTO_2, quality_score=70),
        _busca(title="Get started with Docker", url="https://docs.docker.com/get-started/", description="Docker basics", quality_score=95),
    ]
    achados = await rs.search_for_tag({"id": "t-docker", "name": "Docker", "slug": "docker"})
    assert [c.title for c in achados] == ["Get started with Docker"]


async def test_video_do_youtube_nao_e_julgado_pelo_filtro(fontes):
    """O YouTube já ordena por relevância, e o título de um vídeo raramente repete o assunto por extenso."""
    fontes["videos"] = [rs.Candidate(kind="video", title="Containers na prática, do zero", url="https://youtube.com/watch?v=1", source="youtube")]
    achados = await rs.search_for_tag({"id": "t", "name": "Docker", "slug": "docker"})
    assert len(achados) == 1


async def test_busca_que_so_trouxe_lixo_cai_na_reserva_por_ia(fontes):
    """Sem isto, o lixo era gravado e a IA — que sabe indicar a documentação canônica — nunca rodava."""
    fontes["artigos"] = [_busca(**CRIPTO_1), _busca(**CRIPTO_2)]
    fontes["ia"] = [rs.Candidate(kind="doc", title="Docker Docs", url="https://docs.docker.com", source="ia", quality_score=38)]

    achados = await rs.search_for_tag({"id": "t-docker", "name": "Docker", "slug": "docker"})

    assert fontes["ia_chamada"] == 1
    assert [c.title for c in achados] == ["Docker Docs"]
