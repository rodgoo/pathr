"""O plano gerado precisa CABER na tabela.

O caso real, visto no log de producao: a IA montava o plano inteiro e o INSERT
morria com

    null value in column "goal" of relation "pathr_roadmap"
    violates not-null constraint

Um 500 depois de todo o trabalho feito e pago. E nenhum teste pegava: a suite
cobria a rotacao de provedores e a normalizacao do plano, mas nada conferia
que as colunas obrigatorias da tabela estavam entre as chaves do insert.

O que se testa aqui nao e "o insert funciona" -- isso exigiria um banco, e a
suite e offline de proposito (ver conftest.py). E que toda coluna NOT NULL sem
default aparece na linha montada. Uma coluna nova obrigatoria reprova aqui,
antes de chegar a producao.
"""

from app.models import PathrRoadmap
from app.routers.roadmap import GenerateRequest, linha_do_roadmap

PLANO = {
    "titulo": "Plano Fullstack Java",
    "resumo": "Do React ao Spring em 26 semanas.",
    "fases": [],
}


def _pedido(objetivo: str = "fullstack Java, Typescript, React") -> GenerateRequest:
    return GenerateRequest(
        objective=objetivo, horizon_weeks=26, weekly_hours=8, context="Sem depender de IA."
    )


def _colunas_obrigatorias(modelo) -> set[str]:
    """As colunas que o banco recusa vazias: NOT NULL, sem default proprio e
    sem default do servidor. A chave primaria fica de fora -- o Postgres a
    preenche (ver _mirror_defaults_to_database em app/models.py)."""
    return {
        coluna.name
        for coluna in modelo.__table__.columns
        if not coluna.nullable
        and not coluna.primary_key
        and coluna.default is None
        and coluna.server_default is None
    }


def test_toda_coluna_obrigatoria_do_roadmap_e_preenchida():
    linha = linha_do_roadmap("user-1", _pedido(), PLANO, "modelo-x")
    faltando = _colunas_obrigatorias(PathrRoadmap) - set(linha)
    assert not faltando, f"colunas NOT NULL fora do insert: {sorted(faltando)}"


def test_goal_recebe_o_objetivo_inteiro():
    """Era a coluna que faltava, e e a que carrega o que a pessoa escreveu."""
    linha = linha_do_roadmap("user-1", _pedido(), PLANO, "modelo-x")
    assert linha["goal"] == "fullstack Java, Typescript, React"


def test_objetivo_longo_nao_e_perdido_pelo_corte_do_rotulo():
    """`target_role` corta em 120 para caber num rotulo de tela. Cortar nao
    pode ser o unico lugar onde o objetivo existe."""
    longo = "fullstack Java com foco em vagas internacionais e entrevista tecnica em ingles, " * 3
    linha = linha_do_roadmap("user-1", _pedido(longo), PLANO, "modelo-x")
    assert linha["goal"] == longo
    assert len(linha["target_role"]) == 120


def test_nenhuma_coluna_obrigatoria_recebe_nulo():
    """Estar na chave nao basta: o Postgres recusa o None do mesmo jeito."""
    linha = linha_do_roadmap("user-1", _pedido(), PLANO, "modelo-x")
    nulas = [
        nome for nome in _colunas_obrigatorias(PathrRoadmap) if linha.get(nome, None) is None
    ]
    assert not nulas, f"colunas NOT NULL com valor nulo: {sorted(nulas)}"
