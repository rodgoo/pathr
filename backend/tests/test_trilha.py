"""A trilha como trilha: ordem imposta, e um modulo abrindo o proximo.

`depends_on` estava declarado no modelo desde o comeco, com a docstring
dizendo que era "o grafo de pre-requisitos, que trava/destrava um no" -- e
ninguem escrevia nele. `locked` tinha rotulo na tela e ninguem o definia. O
resultado era uma lista de vinte modulos todos abertos ao mesmo tempo, sem
nada dizendo por onde ir.

Estes testes cobrem as duas metades da trava, porque so uma delas e pior que
nenhuma: travar sem destravar fecharia a trilha para sempre na primeira
conclusao.
"""

import asyncio

from app.routers import roadmap as R
from tests.fake_supabase import FakeSupabase

USUARIO = {"id": "11111111-1111-1111-1111-111111111111", "email": "a@b.co"}


def _modulo(titulo, tags, nivel="intermediario", tipo="skill"):
    return {
        "titulo": titulo,
        "descricao": "d",
        "tipo": tipo,
        "nivel": nivel,
        "horas": 4,
        "semana_inicio": 1,
        "semana_fim": 2,
        "tags": tags,
        "objetivos": ["Fazer algo verificavel"],
    }


def test_a_fase_e_ordenada_pelo_grafo_e_nao_pelo_nivel_declarado():
    """O caso que motivou tudo: um modulo "iniciante de Kubernetes" continua
    exigindo Docker. O nivel descreve a profundidade do tratamento, nao a
    posicao na dependencia."""
    ordenados = R._ordem_de_estudo(
        [
            _modulo("Kubernetes na pratica", ["Kubernetes"], nivel="iniciante"),
            _modulo("Fundamentos de Linux", ["Linux"], nivel="avancado"),
            _modulo("Contêineres com Docker", ["Docker"], nivel="intermediario"),
        ]
    )
    assert [m["titulo"] for m in ordenados] == [
        "Fundamentos de Linux",
        "Contêineres com Docker",
        "Kubernetes na pratica",
    ]


def test_empate_de_camada_mantem_a_ordem_escrita_pelo_modelo():
    """Java e Python sao os dois camada 0: qual vem antes e do objetivo da
    pessoa, e o modelo e quem sabe disso. Reordenar seria inventar."""
    ordenados = R._ordem_de_estudo(
        [_modulo("Java", ["Java"]), _modulo("Python", ["Python"])]
    )
    assert [m["titulo"] for m in ordenados] == ["Java", "Python"]


def test_leitura_antes_de_entrega_quando_a_camada_empata():
    ordenados = R._ordem_de_estudo(
        [
            _modulo("Checkpoint", ["Git"], tipo="checkpoint"),
            _modulo("Ler sobre Git", ["Git"], tipo="reading"),
        ]
    )
    assert [m["titulo"] for m in ordenados] == ["Ler sobre Git", "Checkpoint"]


# ---------------------------------------------------------------------------
# Destravar
# ---------------------------------------------------------------------------


def _banco_com_cadeia():
    """Tres modulos em fila: A pronto para fazer, B e C travados atras dele."""
    return FakeSupabase(
        pathr_roadmap_node=[
            {"id": "A", "roadmap_id": "R1", "status": "doing", "depends_on": []},
            {"id": "B", "roadmap_id": "R1", "status": "locked", "depends_on": ["A"]},
            {"id": "C", "roadmap_id": "R1", "status": "locked", "depends_on": ["B"]},
        ]
    )


def test_concluir_um_modulo_abre_so_o_seguinte():
    duplo = _banco_com_cadeia()

    R._destravar_dependentes(duplo, "A", "R1")

    por_id = {l["id"]: l["status"] for l in duplo.linhas("pathr_roadmap_node")}
    assert por_id["B"] == "todo", "o modulo seguinte tinha que abrir"
    assert por_id["C"] == "locked", "o terceiro so abre quando B terminar"


def test_o_modulo_aberto_entra_como_todo_e_nao_como_doing():
    """Quem escolhe o que esta fazendo agora e a pessoa. Marcar em andamento
    por ela criaria um "atual" que ela nao decidiu, logo depois de terminar
    outra coisa -- que e quando ela mais provavelmente vai parar."""
    duplo = _banco_com_cadeia()

    R._destravar_dependentes(duplo, "A", "R1")

    b = next(l for l in duplo.linhas("pathr_roadmap_node") if l["id"] == "B")
    assert b["status"] == "todo"


def test_modulo_com_dois_pre_requisitos_espera_os_dois():
    """Hoje a cadeia e linear e isso da no mesmo, mas o campo e uma lista --
    e a checagem precisa valer para o dia em que ela deixar de ser."""
    duplo = FakeSupabase(
        pathr_roadmap_node=[
            {"id": "A", "roadmap_id": "R1", "status": "done", "depends_on": []},
            {"id": "B", "roadmap_id": "R1", "status": "doing", "depends_on": []},
            {"id": "C", "roadmap_id": "R1", "status": "locked", "depends_on": ["A", "B"]},
        ]
    )

    # A ja estava pronto; concluir B fecha os dois pre-requisitos de C.
    R._destravar_dependentes(duplo, "B", "R1")

    c = next(l for l in duplo.linhas("pathr_roadmap_node") if l["id"] == "C")
    assert c["status"] == "todo"


def test_destravar_nao_derruba_a_conclusao_quando_falha():
    """Best-effort de verdade: a pessoa acabou de registrar que terminou o
    modulo, e perder isso e pior que ficar com um modulo travado a mais."""

    class BancoQuebrado:
        def table(self, _nome):
            raise RuntimeError("banco fora")

    R._destravar_dependentes(BancoQuebrado(), "A", "R1")  # nao levanta
