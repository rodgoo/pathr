"""Os textos que o SERVIDOR escreve para a tela, nos cinco idiomas.

Veio de um relato com print: o app em inglês, e no meio da interface traduzida
"Recordação ativa · 15 min", "Repetição espaçada", "Em andamento no seu
roadmap: Docker". São frases montadas no servidor e enviadas prontas — a tela
não tem como traduzir o que já chega escrito.
"""

import pytest

from app.services import code_lab, idioma, textos, weekly_plan

IDIOMAS = ("pt", "en", "es", "fr", "de")


@pytest.fixture(autouse=True)
def volta_ao_padrao():
    """O idioma mora num ContextVar: sem restaurar, um teste que troca para
    alemão deixaria os seguintes em alemão."""
    anterior = idioma.idioma_da_requisicao.get()
    yield
    idioma.idioma_da_requisicao.set(anterior)


def test_toda_chave_existe_nos_cinco_idiomas():
    """Uma frase que falta num idioma cai no português calada — e é assim que
    metade da tela fica em duas línguas sem ninguém perceber."""
    faltando = {
        chave: [i for i in IDIOMAS if i not in textos.formas(chave)]
        for chave in textos.chaves()
    }
    assert {c: f for c, f in faltando.items() if f} == {}


def test_o_idioma_do_pedido_escolhe_a_frase():
    for codigo, esperado in (
        ("pt", "Recordação ativa"),
        ("en", "Active recall"),
        ("de", "Aktives Abrufen"),
    ):
        idioma.idioma_da_requisicao.set(codigo)
        assert textos.t("pilar.quiz") == esperado


def test_idioma_sem_traducao_cai_no_portugues():
    idioma.idioma_da_requisicao.set("it")  # não é um dos cinco
    assert textos.t("pilar.quiz") == "Recordação ativa"


def test_chave_desconhecida_aparece_na_tela():
    """Devolver a chave é feio de propósito: aparece no primeiro teste e some
    quando a frase entra na tabela. Devolver vazio esconderia o buraco."""
    assert textos.t("nao.existe") == "nao.existe"


def test_o_plano_da_semana_sai_no_idioma_pedido():
    idioma.idioma_da_requisicao.set("en")
    item = weekly_plan._item("quiz", "Docker quiz", None, None, 15)

    assert item["pilar"] == "Active recall"
    assert "Answering without looking things up" in item["detalhe"]


def test_o_titulo_da_atividade_tambem():
    idioma.idioma_da_requisicao.set("es")
    assert textos.t("atividade.feynman", titulo="Docker") == "Explicar Docker con tus palabras"

    idioma.idioma_da_requisicao.set("de")
    assert textos.t("atividade.revisao", quantos=29) == "29 offene Konzepte wiederholen"


def test_nenhum_pilar_ou_detalhe_ficou_como_texto_fixo():
    """As duas tabelas do plano guardam CHAVE, não frase: se alguém voltar a
    escrever português ali, a tela volta a misturar idiomas."""
    for tabela in (weekly_plan.PILARES, weekly_plan._DETALHES):
        for valor in tabela.values():
            assert textos.formas(valor), f"{valor!r} não é uma chave de textos.py"


def test_a_sugestao_do_laboratorio_nao_tem_portugues_fixo():
    """`code_lab` montava "Em andamento no seu roadmap: X" com f-string."""
    caminho = (code_lab.__file__ or "").replace(".pyc", ".py")
    with open(caminho, encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    for frase in ("no seu roadmap:", "Para o seu nível em", "Próximo passo em"):
        assert f'f"{frase}' not in codigo
