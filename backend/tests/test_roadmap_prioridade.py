"""A ordem em que o plano ataca os assuntos.

Esta é a regra que decide se um plano de 12 semanas termina ou é abandonado
na terceira, e ela não aparece em nenhum lugar da resposta do modelo — só no
texto que a gente manda. Por isso é testada no PROMPT: o que se pode afirmar
sem chamar IA é que a instrução saiu correta e completa, e é justamente o que
quebra em silêncio quando alguém mexe no `build_prompt`.

O que a regra diz, e o porquê de cada metade:

- Entre dois assuntos que não bloqueiam um ao outro, começa o que já tem chão.
  Sair de parcial para autônomo custa uma fração do que custa sair do zero, e
  entrega resultado nas primeiras semanas.
- MAS o que está no zero e o objetivo EXIGE vai cedo, não por último: é o
  assunto mais longo do plano, e o fim de um prazo fechado é onde as coisas
  não acontecem.
- E o que está no zero e é só desejo vai para o fim, e sai primeiro quando as
  horas não fecham.
"""

from app.services import roadmap_builder


def um_prompt(**extra):
    base = dict(
        objective="Backend senior",
        weeks=12,
        weekly_hours=8,
        current_role="Desenvolvedor pleno",
        years=4,
        known=[],
        targets=[],
        catalog_names=["Docker", "Kubernetes", "Postgres", "Redis"],
    )
    base.update(extra)
    return roadmap_builder.build_prompt(**base)


def test_corte_e_em_n3_nao_em_n1():
    prompt = um_prompt(
        known=[
            {"name": "Docker", "proficiency": 4},
            {"name": "Postgres", "proficiency": 2},
            {"name": "Redis", "proficiency": 1},
            {"name": "Kubernetes", "proficiency": 0},
        ],
    )

    # N3+ fica de fora do plano.
    linha_dominio = next(l for l in prompt.splitlines() if l.startswith("JA DOMINA"))
    assert "Docker" in linha_dominio
    assert "Postgres" not in linha_dominio

    # N1 e N2 ENTRAM, para aprofundar. Foi a confusão que a tela mostrava: dá
    # para ler "só o N0 é coberto" e não é isso que o gerador faz.
    linha_parcial = next(l for l in prompt.splitlines() if l.startswith("SABE PARCIALMENTE"))
    assert "Postgres (nivel 2/5)" in linha_parcial
    assert "Redis (nivel 1/5)" in linha_parcial


def test_parcial_vem_antes_do_zero_no_texto():
    prompt = um_prompt(
        known=[
            {"name": "Postgres", "proficiency": 2},
            {"name": "Kubernetes", "proficiency": 0},
        ],
    )

    # O modelo lê de cima para baixo e o que vem antes pesa mais. A ordem do
    # texto precisa repetir a regra, não contrariá-la.
    assert prompt.index("SABE PARCIALMENTE") < prompt.index("DO ZERO")


def test_zero_exigido_pelo_objetivo_vai_cedo():
    prompt = um_prompt(
        known=[
            {"name": "Kubernetes", "proficiency": 0},
            {"name": "Redis", "proficiency": 0},
        ],
        targets=["Kubernetes"],
    )

    essencial = next(l for l in prompt.splitlines() if l.startswith("DO ZERO E EXIGIDO"))
    desejado = next(l for l in prompt.splitlines() if l.startswith("DO ZERO, APENAS DESEJADO"))

    # O zero que o objetivo exige é o mais caro E o mais importante. Empurrá-lo
    # para o fim de um prazo fechado é garantir que não seja concluído.
    assert "Kubernetes" in essencial
    assert "Kubernetes" not in desejado
    assert "Redis" in desejado
    assert "CEDO" in essencial
    assert "corte isto primeiro" in desejado


def test_dependencia_continua_mandando_mais_que_a_prioridade():
    prompt = um_prompt(known=[{"name": "Docker", "proficiency": 0}])

    # Sem esta ressalva no texto, "comece pelo parcial" inverteria a escada:
    # um pré-requisito em zero cairia depois do que depende dele, e o plano
    # deixaria de ser trilha.
    regras = roadmap_builder.SYSTEM_PROMPT
    assert "Dependencia vence sempre" in regras or "Dependência vence sempre" in regras
    assert "ORDEM OBRIGATORIA" in regras
    assert "ORDEM OBRIGATORIA" in prompt or "Docker" in prompt


def test_ordem_de_corte_quando_as_horas_nao_fecham():
    # O prompt é texto embrulhado em 80 colunas: uma frase atravessa quebras de
    # linha e indentação. Comparar com o espaçamento colapsado afirma a ORDEM
    # das frases, que é o que importa, sem prender o teste ao ponto onde o
    # parágrafo quebra hoje.
    regras = " ".join(roadmap_builder.SYSTEM_PROMPT.split())

    assert "corte NESTA ordem" in regras
    # Cortar aprofundamento antes de cortar desejo seria jogar fora o que sai
    # mais barato e rende mais rápido.
    assert regras.index("em ZERO e o objetivo não exige") < regras.index(
        "o aprofundamento que o objetivo não exige"
    )
    # E o que o objetivo exige não sai de jeito nenhum.
    assert "Nunca corte o que o objetivo exige" in regras
