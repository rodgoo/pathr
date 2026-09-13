"""O progresso do plano conta o que já se fez nos módulos em andamento.

Caso de produção: quiz feito num módulo de 6h, e o card "Continue", a barra do
plano e a lateral seguiam em 0% porque só módulo concluído contava.
"""

from app.services import progresso as P


def _semana(*itens):
    return {"items": [dict(zip(("node_id", "tipo", "feito"), item)) for item in itens]}


def test_quiz_feito_move_o_modulo_e_o_plano():
    modulos = [
        {"id": "git", "status": "doing", "progress_pct": 0, "estimated_hours": 6},
        {"id": "docker", "status": "todo", "progress_pct": 0, "estimated_hours": 6},
    ]
    listas = [_semana(("git", "material", False), ("git", "quiz", True), ("git", "feynman", False),
                      ("git", "atividade", False), (None, "revisao", False))]
    avanco = P.avanco_por_modulo(listas)
    assert avanco == {"git": 0.25}
    assert P.resumo(modulos, avanco)["progress_pct"] == 12  # 6 * 0,25 / 12
    assert P.com_avanco(modulos, avanco)[0]["progress_pct"] == 25


def test_item_repetido_em_duas_semanas_conta_uma_vez_e_vale_se_feito_em_qualquer():
    listas = [_semana(("git", "quiz", False), ("git", "feynman", False)),
              _semana(("git", "quiz", True), ("git", "feynman", False))]
    assert P.avanco_por_modulo(listas) == {"git": 0.5}


def test_concluido_vale_inteiro_pulado_sai_e_andamento_nao_chega_a_100():
    modulos = [
        {"id": "a", "status": "done", "estimated_hours": 10},
        {"id": "b", "status": "skipped", "estimated_hours": 50},
        {"id": "c", "status": "doing", "estimated_hours": 10},
    ]
    avanco = {"c": 1.0}
    assert P.avanco_do_modulo(modulos[2], avanco) == 0.95
    # (10 + 9,5) / 20; o pulado não pesa.
    assert P.resumo(modulos, avanco)["progress_pct"] == 98
    assert P.resumo(modulos, avanco)["done_nodes"] == 1


def test_modulo_maior_pesa_mais():
    modulos = [{"id": "curto", "status": "done", "estimated_hours": 2},
               {"id": "longo", "status": "todo", "estimated_hours": 18}]
    assert P.resumo(modulos, {})["progress_pct"] == 10
