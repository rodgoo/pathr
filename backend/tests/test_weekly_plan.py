"""O checklist da semana: nível, orçamento, ordem e evidência.

Offline e sem banco — as regras são funções puras. Cada teste nomeia o método
que a regra aplica, porque é isso que quebra em silêncio: uma lista que ainda
aparece, só que na ordem errada ou no tamanho errado.
"""

from datetime import date, timedelta

import pytest

from app.services import weekly_plan as wp


def _node(nid, tags, semana=(1, 1), status="todo", ordem=0, titulo=None):
    return {
        "id": nid,
        "title": titulo or f"Módulo {nid}",
        "kind": "skill",
        "tag_ids": tags,
        "week_start": semana[0],
        "week_end": semana[1],
        "status": status,
        "order_index": ordem,
    }


# --- semana -------------------------------------------------------------------


def test_inicio_da_semana_e_segunda():
    for delta in range(7):
        dia = date(2026, 9, 7) + timedelta(days=delta)
        inicio = wp.inicio_da_semana(dia)
        assert inicio.weekday() == 0 and 0 <= (dia - inicio).days < 7


def test_semana_do_plano_conta_semanas_de_calendario():
    criado = wp.inicio_da_semana(date(2026, 9, 10))
    assert wp.semana_do_plano(criado, criado, 12) == 1
    assert wp.semana_do_plano(criado, criado + timedelta(days=15), 12) == 3
    assert wp.semana_do_plano(criado, criado + timedelta(days=200), 4) == 4


@pytest.mark.parametrize(
    "nivel,banda",
    [(0, "iniciante"), (1, "iniciante"), (2, "intermediario"), (3, "avancado"), (5, "avancado")],
)
def test_faixas(nivel, banda):
    assert wp.faixa(nivel) == banda


# --- quais módulos ------------------------------------------------------------


def test_atrasado_vem_antes_do_modulo_da_semana():
    nodes = [_node("da-semana", ["t"], (3, 3), ordem=2), _node("atrasado", ["t"], (1, 2), ordem=1)]
    assert [n["id"] for n in wp.modulos_da_semana(nodes, 3)] == ["atrasado", "da-semana"]


def test_concluido_e_fase_nao_entram():
    nodes = [
        _node("feito", ["t"], status="done"),
        {"id": "fase", "kind": "phase", "week_start": 1, "week_end": 1},
        _node("aberto", ["t"]),
    ]
    assert [n["id"] for n in wp.modulos_da_semana(nodes, 1)] == ["aberto"]


def test_semana_sem_modulo_pega_os_proximos_em_aberto():
    """Checklist vazio com o plano pela metade diria "nada a fazer" quando há."""
    nodes = [_node("futuro", ["t"], (9, 9))]
    assert [n["id"] for n in wp.modulos_da_semana(nodes, 2)] == ["futuro"]


# --- composição por nível -----------------------------------------------------


def test_iniciante_estuda_antes_de_ser_testado():
    itens = wp.montar([_node("a", ["t"])], {"t": 0}, 0, 600)
    tipos = [i["tipo"] for i in itens]
    assert tipos.index("material") < tipos.index("quiz")


def test_avancado_nao_reve_o_basico():
    """Rever o que já se domina é o jeito mais confortável de não progredir."""
    tipos = {i["tipo"] for i in wp.montar([_node("a", ["t"])], {"t": 4}, 0, 600)}
    assert "material" not in tipos and "quiz" not in tipos
    assert {"feynman", "desafio"} <= tipos


def test_revisao_vem_primeiro():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 5, 600)
    assert itens[0]["tipo"] == "revisao" and "5 conceitos" in itens[0]["titulo"]


def test_sem_pendencia_nao_ha_item_de_revisao():
    assert all(i["tipo"] != "revisao" for i in wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600))


def test_assuntos_se_alternam():
    """Intercalação: quiz de A, quiz de B — não tudo de A antes de B."""
    itens = wp.montar([_node("a", ["t"]), _node("b", ["u"])], {"t": 2, "u": 2}, 0, 600)
    assert [i["node_id"] for i in itens][:2] == ["a", "b"]


def test_cabe_no_orcamento_mas_nunca_fica_vazio():
    muitos = [_node(str(n), ["t"]) for n in range(3)]
    folgado = wp.montar(muitos, {"t": 0}, 0, 10_000)
    apertado = wp.montar(muitos, {"t": 0}, 0, 30)
    assert len(apertado) < len(folgado)
    assert len(apertado) >= 2


# --- evidência e marcação -----------------------------------------------------


def test_quiz_feito_na_semana_se_marca_sozinho():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600)
    mudou = wp.aplicar_evidencias(itens, {"a"}, set(), 0, "2026-09-10T10:00:00+00:00")
    quiz = next(i for i in itens if i["tipo"] == "quiz")
    assert mudou and quiz["feito"] and quiz["verificado"]


def test_pratica_nao_se_marca_sem_evidencia():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600)
    wp.aplicar_evidencias(itens, {"a"}, {"a"}, 0, "agora")
    assert not next(i for i in itens if i["tipo"] == "pratica")["feito"]


def test_revisao_se_marca_quando_a_fila_zera():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 3, 600)
    wp.aplicar_evidencias(itens, set(), set(), 0, "agora")
    assert itens[0]["tipo"] == "revisao" and itens[0]["verificado"]


def test_item_verificado_nao_se_desmarca():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600)
    wp.aplicar_evidencias(itens, {"a"}, set(), 0, "agora")
    with pytest.raises(wp.ItemVerificado):
        wp.marcar(itens, "quiz:a", False, "agora")


def test_item_desconhecido():
    with pytest.raises(KeyError):
        wp.marcar([], "nada", True, "agora")


def test_refazer_mantem_o_que_foi_feito():
    antigos = wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600)
    wp.marcar(antigos, "pratica:a", True, "ontem")
    novos = wp.preservar(wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600), antigos)
    assert next(i for i in novos if i["id"] == "pratica:a")["feito"]


def test_resumo():
    itens = wp.montar([_node("a", ["t"])], {"t": 2}, 0, 600)
    wp.marcar(itens, itens[0]["id"], True, "agora")
    r = wp.resumo(itens)
    assert r["feitos"] == 1 and r["total"] == len(itens)
    assert r["minutos_feitos"] == itens[0]["minutos"]
