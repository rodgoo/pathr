"""Ajustes de rota: compactar pelo domínio medido, reforçar pela lacuna,
reagendar pelo ritmo. Sem banco."""

from datetime import date, timedelta

from app.services import route_adjust as ra


def _mod(nid, tags, horas=4.0, semana=(1, 1), ordem=0, status="todo", fase=None):
    return {
        "id": nid,
        "title": f"M{nid}",
        "kind": "skill",
        "tag_ids": tags,
        "estimated_hours": horas,
        "week_start": semana[0],
        "week_end": semana[1],
        "order_index": ordem,
        "status": status,
        "parent_id": fase,
    }


def _ev(**extra):
    base = dict(
        nivel_por_tag={},
        pendentes_por_tag={},
        nota_quiz_por_node={},
        nota_feynman_por_node={},
        horas_planejadas=8.0,
        horas_reais=None,
        semana_atual=1,
    )
    base.update(extra)
    return ra.Evidencia(**base)


def test_ritmo_em_horas_por_semana():
    hoje = date(2026, 9, 20)
    por_dia = {hoje - timedelta(days=d): 60 for d in range(14)}
    assert ra.horas_por_semana(por_dia, hoje, 14) == 7.0


def test_dominio_medido_compacta():
    mudancas, campos = ra.propor([_mod("a", ["t"], horas=6)], _ev(nivel_por_tag={"t": (4, "quiz")}))
    assert mudancas[0]["tipo"] == "compactar"
    assert campos["a"]["estimated_hours"] == 3.0


def test_dominio_declarado_no_curriculo_nao_compacta():
    """O currículo é o que a pessoa escreveu sobre si. Compactar por ele pularia
    justamente o que ela superestimou."""
    mudancas, _ = ra.propor([_mod("a", ["t"], horas=6)], _ev(nivel_por_tag={"t": (4, "cv")}))
    assert not any(m["tipo"] == "compactar" for m in mudancas)


def test_lacuna_recorrente_reforca_com_teto():
    mudancas, campos = ra.propor([_mod("a", ["t"], horas=10)], _ev(pendentes_por_tag={"t": 3}))
    assert mudancas[0]["tipo"] == "reforcar" and "3 conceitos" in mudancas[0]["motivo"]
    assert campos["a"]["estimated_hours"] == 14.0  # +50% seria 15; o teto é +4h


def test_quiz_e_feynman_baixos_reforcam():
    mudancas, _ = ra.propor(
        [_mod("a", ["t"])], _ev(nota_quiz_por_node={"a": 30.0}, nota_feynman_por_node={"a": 40})
    )
    assert "quiz em 30%" in mudancas[0]["motivo"] and "40/100" in mudancas[0]["motivo"]


def test_reforco_nao_se_repete():
    """Sem esse limite, um módulo difícil ganharia horas toda semana."""
    mudancas, _ = ra.propor(
        [_mod("a", ["t"])], _ev(pendentes_por_tag={"t": 5}, ja_reforcados={"a"})
    )
    assert not any(m["tipo"] == "reforcar" for m in mudancas)


def test_ritmo_lento_estica_o_cronograma():
    nodes = [_mod(str(i), ["t"], horas=8, semana=(i + 1, i + 1), ordem=i) for i in range(3)]
    mudancas, campos = ra.propor(nodes, _ev(horas_reais=2.0))
    reagendar = next(m for m in mudancas if m["tipo"] == "reagendar")
    assert reagendar["depois"]["fim_semana"] > reagendar["antes"]["fim_semana"]
    assert "2.0h" in reagendar["motivo"]
    assert campos["0"]["week_end"] - campos["0"]["week_start"] >= 3  # 8h a 2h/semana


def test_ritmo_no_planejado_nao_mexe():
    assert ra.propor([_mod("a", ["t"], horas=8)], _ev(horas_reais=7.5)) == ([], {})


def test_modulo_concluido_fica_onde_esta():
    nodes = [
        _mod("feito", ["t"], horas=8, semana=(1, 1), status="done"),
        _mod("aberto", ["t"], horas=8, semana=(2, 2), ordem=1),
    ]
    _, campos = ra.propor(nodes, _ev(horas_reais=2.0, semana_atual=2))
    assert "feito" not in campos


def test_fase_acompanha_os_filhos():
    fase = {"id": "f", "kind": "phase", "week_start": 1, "week_end": 1, "order_index": 0}
    nodes = [fase, _mod("a", ["t"], horas=8, fase="f"), _mod("b", ["t"], horas=8, ordem=1, fase="f")]
    _, campos = ra.propor(nodes, _ev(horas_reais=2.0))
    assert campos["f"]["week_end"] == max(campos["a"]["week_end"], campos["b"]["week_end"])


def test_reagendar_enche_a_semana_antes_de_transbordar():
    mods = [_mod(str(i), ["t"], ordem=i) for i in range(3)]
    horas = {"0": 4, "1": 4, "2": 4}
    assert ra.reagendar(mods, horas, 8, 1) == {"0": (1, 1), "1": (1, 1), "2": (2, 2)}
    assert ra.reagendar(mods, horas, 4, 1) == {"0": (1, 1), "1": (2, 2), "2": (3, 3)}
