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
from app.routers.roadmap import GenerateRequest, _persist, linha_do_roadmap
from app.services.tag_catalog import TagCatalog
from tests.fake_supabase import FakeSupabase

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


# --- _persist grava fase e módulo em LOTE, não um INSERT por linha ----------
#
# Antes, depends_on do módulo N precisava do id (gerado pelo banco) do módulo
# N-1, e isso forçava um INSERT por fase/módulo dentro do laço — 20 a 40
# round-trips sequenciais ao PostgREST num plano de 12 semanas. Gerar o uuid
# no Python (ver _persist) deixa calcular depends_on sem esperar o banco e
# mandar tudo num insert só.

PLANO_DUAS_FASES = {
    "titulo": "Plano Fullstack",
    "resumo": "Do zero ao deploy.",
    "fases": [
        {
            "titulo": "Fundamentos",
            "objetivo": "A base.",
            "semana_inicio": 1,
            "semana_fim": 4,
            "modulos": [
                {
                    "titulo": "Lógica",
                    "descricao": "Variáveis e laços.",
                    "tipo": "skill",
                    "tags": [],
                    "nivel": "iniciante",
                    "horas": 10,
                    "semana_inicio": 1,
                    "semana_fim": 2,
                    "objetivos": [],
                },
                {
                    "titulo": "Estruturas de dados",
                    "descricao": "Listas e dicionários.",
                    "tipo": "skill",
                    "tags": [],
                    "nivel": "iniciante",
                    "horas": 10,
                    "semana_inicio": 3,
                    "semana_fim": 4,
                    "objetivos": [],
                },
            ],
        },
        {
            "titulo": "Web",
            "objetivo": "Front e back.",
            "semana_inicio": 5,
            "semana_fim": 8,
            "modulos": [
                {
                    "titulo": "APIs",
                    "descricao": "REST com FastAPI.",
                    "tipo": "project",
                    "tags": [],
                    "nivel": "intermediario",
                    "horas": 20,
                    "semana_inicio": 5,
                    "semana_fim": 8,
                    "objetivos": [],
                },
            ],
        },
    ],
}


def _banco_vazio() -> FakeSupabase:
    return FakeSupabase(pathr_roadmap=[], pathr_roadmap_node=[], pathr_tag=[])


def test_persist_grava_fase_e_modulo_num_unico_insert_em_lote():
    banco = _banco_vazio()
    catalog = TagCatalog(banco).load()

    _persist(banco, "user-1", _pedido(), PLANO_DUAS_FASES, catalog, "modelo-x")

    inserts_no_node = [e for e in banco.escritas if e[0] == "pathr_roadmap_node" and e[1] == "insert"]
    assert len(inserts_no_node) == 1, "fase e módulo precisam sair num insert só, não um por linha"
    # 2 fases + 3 módulos = 5 linhas, todas no mesmo lote.
    assert len(inserts_no_node[0][2]) == 5


def test_persist_mantem_hierarquia_e_cadeia_de_pre_requisitos():
    """O comportamento não pode mudar com o lote: módulo pertence à SUA fase
    (parent_id), e a ordem de estudo continua travando o que vem depois."""
    banco = _banco_vazio()
    catalog = TagCatalog(banco).load()

    _persist(banco, "user-1", _pedido(), PLANO_DUAS_FASES, catalog, "modelo-x")

    nos = banco.linhas("pathr_roadmap_node")
    fases = {n["id"]: n for n in nos if n["kind"] == "phase"}
    modulos = [n for n in nos if n["kind"] != "phase"]
    assert len(fases) == 2
    assert len(modulos) == 3

    por_titulo = {m["title"]: m for m in modulos}
    fundamentos = fases[por_titulo["Lógica"]["parent_id"]]
    assert fundamentos["title"] == "Fundamentos"
    assert por_titulo["Estruturas de dados"]["parent_id"] == fundamentos["id"]
    web = fases[por_titulo["APIs"]["parent_id"]]
    assert web["title"] == "Web"

    # Só o primeiro módulo (na ordem de estudo) começa aberto; os demais
    # travam no anterior, cruzando até a fronteira entre fases.
    primeiro = por_titulo["Lógica"]
    assert primeiro["status"] == "doing"
    assert primeiro["depends_on"] == []
    segundo = por_titulo["Estruturas de dados"]
    assert segundo["status"] == "locked"
    assert segundo["depends_on"] == [primeiro["id"]]
    terceiro = por_titulo["APIs"]
    assert terceiro["status"] == "locked"
    assert terceiro["depends_on"] == [segundo["id"]]


def test_persist_atualiza_is_primary_e_devolve_o_roadmap_criado():
    banco = _banco_vazio()
    catalog = TagCatalog(banco).load()
    banco.tabelas["pathr_roadmap"].append({"id": "antigo", "user_id": "user-1", "is_primary": True})

    roadmap = _persist(banco, "user-1", _pedido(), PLANO_DUAS_FASES, catalog, "modelo-x")

    assert roadmap["title"] == "Plano Fullstack"
    antigo = next(r for r in banco.linhas("pathr_roadmap") if r["id"] == "antigo")
    assert antigo["is_primary"] is False
