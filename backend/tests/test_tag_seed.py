"""A semente do catálogo de tecnologias.

O que se segura: nenhum apelido aponta para duas tags (era o que fundia
Playwright com Cypress e TDD com "Testes automatizados"), toda categoria é
aceita pelo catálogo, e as tecnologias que as vagas reais cobram existem.
"""

from collections import defaultdict

from app.services.tag_catalog import CATEGORIES, _alias_keys, slugify
from app.services.tag_seed import SEED, seed_rows


def test_nenhum_apelido_aponta_para_duas_tags():
    donos: dict[str, set[str]] = defaultdict(set)
    for tag in seed_rows():
        for chave in _alias_keys(tag):
            donos[chave].add(tag["slug"])
    colisoes = {chave: sorted(slugs) for chave, slugs in donos.items() if len(slugs) > 1}
    assert colisoes == {}


def test_slugs_unicos_e_categorias_aceitas():
    slugs = [slugify(nome) for nome, *_ in SEED]
    assert len(slugs) == len(set(slugs))
    assert {categoria for _, categoria, _, _ in SEED} <= CATEGORIES


def test_tecnologias_que_as_vagas_cobram_existem():
    """Tiradas de anúncios reais de vaga Java do mercado brasileiro."""
    nomes = {nome for nome, *_ in SEED}
    exigidas = {
        "Quarkus", "Mockito", "Testcontainers", "JUnit", "OpenAPI", "Keycloak", "JWT", "OAuth 2.0",
        "Datadog", "Dynatrace", "Prometheus", "OpenTelemetry", "ELK", "SonarQube", "Jira",
        "Azure DevOps", "OpenShift", "Jenkins", "AWS Lambda", "Kanban", "SOLID", "Design Patterns",
        "Arquitetura hexagonal", "Arquitetura orientada a eventos", "ActiveMQ", "JMS", "GitFlow",
        "GraalVM", "Azure API Management", "Bancário e financeiro", "Varejo", "Testes unitários", "TDD",
    }
    assert exigidas <= nomes, exigidas - nomes


def test_apelidos_nao_fundem_tecnologias_distintas():
    por_chave = {}
    for tag in seed_rows():
        for chave in _alias_keys(tag):
            por_chave.setdefault(chave, tag["name"])
    assert por_chave["tdd"] == "TDD"
    assert por_chave["playwright"] == "Playwright"
    assert por_chave["kanban"] == "Kanban"
    assert por_chave["lambda"] == "AWS Lambda"
    assert por_chave["datadog"] == "Datadog"
    assert por_chave["vsts"] == "Azure DevOps"
