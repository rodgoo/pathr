"""O tempo de estudo de um material concluído.

Artigo e documentação não têm duração cadastrada — só vídeo tem — e concluir
um deles gravava ZERO minutos. Quem leu quatro artigos inteiros via "12 min
de estudo" no painel, e a média, o melhor dia e o heatmap mentiam junto.
"""

from app.routers.library import _minutos_do_material
from app.routers.profile import _minutos_da_atividade
from app.services.progress import minutos_de_leitura


def test_leitura_arredonda_para_cima_e_zero_sem_texto():
    assert minutos_de_leitura(None) == 0
    assert minutos_de_leitura(0) == 0
    assert minutos_de_leitura(1) == 1
    assert minutos_de_leitura(180) == 1
    assert minutos_de_leitura(181) == 2


def test_informado_vence_duracao_que_vence_estimativa():
    artigo = {"duration_min": None, "reader_words": 2520}
    video = {"duration_min": 30, "reader_words": None}
    assert _minutos_do_material(0, artigo) == 14
    assert _minutos_do_material(0, video) == 30
    assert _minutos_do_material(9, artigo) == 9


def test_atividade_antiga_de_artigo_zerada_e_estimada_e_marcada():
    linha = {"kind": "resource_done", "minutes": 0, "ref_id": "r1"}
    materiais = {"r1": {"duration_min": None, "reader_words": 2520}}
    assert _minutos_da_atividade(linha, materiais) == (14, True)


def test_minutos_gravados_nao_sao_reestimados():
    linha = {"kind": "resource_done", "minutes": 20, "ref_id": "r1"}
    assert _minutos_da_atividade(linha, {"r1": {"reader_words": 9000}}) == (20, False)


def test_outras_atividades_sem_minutos_continuam_zero():
    """Criar o plano não é tempo de estudo, e não vira estimativa."""
    linha = {"kind": "roadmap_created", "minutes": 0, "ref_id": None}
    assert _minutos_da_atividade(linha, {}) == (0, False)
