"""O catalogo de idiomas e a conversao entre as reguas.

Offline. O que se testa aqui e a promessa central do modulo: o app mede numa
escala so (CEFR) e apresenta na prova que a pessoa escolheu. Se a conversao
errar, a meta "7.0 no IELTS" vira um alvo que o nivelamento nunca alcanca -- ou
que ele da por alcancado cedo demais, que e pior.
"""

import pytest

from app.services import languages as lang


def test_catalogo_tem_os_idiomas_pedidos():
    codigos = {idioma.codigo for idioma in lang.IDIOMAS}
    assert {"en", "es", "fr", "de", "it", "ja", "zh", "ko", "pt"} <= codigos


def test_todo_idioma_oferece_cefr():
    """Quem nao presta prova nenhuma precisa de uma regua. O CEFR e o piso
    comum, e e a escala em que o app realmente mede."""
    for idioma in lang.IDIOMAS:
        assert any(exame.id == "cefr" for exame in idioma.exames), idioma.codigo


def test_ingles_tem_as_provas_que_o_mercado_pede():
    ids = {exame.id for exame in lang.idioma("en").exames}
    assert {"ielts", "toefl_ibt", "toeic", "cambridge"} <= ids


@pytest.mark.parametrize(
    "idioma,exame,rotulo,cefr",
    [
        ("en", "ielts", "7.0", "C1"),
        ("en", "ielts", "5.5", "B2"),
        ("en", "toefl_ibt", "95", "C1"),
        ("en", "toefl_ibt", "42", "B1"),
        ("en", "cambridge", "FCE", "B2"),
        ("ja", "jlpt", "N2", "B2"),
        ("zh", "hsk", "HSK 5", "B2"),
        ("ko", "topik", "TOPIK 6", "C2"),
        ("de", "testdaf", "TDN 5", "C1"),
        ("pt", "celpe_bras", "Avançado", "C1"),
    ],
)
def test_meta_na_prova_vira_meta_em_cefr(idioma, exame, rotulo, cefr):
    assert lang.cefr_da_meta(idioma, exame, rotulo) == cefr


def test_nivel_medido_volta_para_a_regua_escolhida():
    """O caminho inverso: a tela mostra o que a pessoa entende. Quem estuda
    para o IELTS quer ler 7.0, nao C1."""
    assert lang.meta_no_exame("en", "ielts", "C1") == "7.0"
    assert lang.meta_no_exame("ja", "jlpt", "B2") == "N2"


def test_conversao_de_ida_e_volta_nao_promete_mais_do_que_mediu():
    """C1 no IELTS cobre 7.0 e 8.0. Voltar tem que dar 7.0 -- anunciar 8.0
    seria dar por certo o que nao foi medido."""
    assert lang.meta_no_exame("en", "ielts", "C1") == "7.0"


def test_faixa_desconhecida_nao_inventa_equivalencia():
    assert lang.cefr_da_meta("en", "ielts", "12.0") is None
    assert lang.cefr_da_meta("en", "exame-que-nao-existe", "7.0") is None
    assert lang.cefr_da_meta("xx", "ielts", "7.0") is None


def test_idioma_fora_do_catalogo_e_recusado():
    assert lang.existe("en") is True
    assert lang.existe("EN") is True
    assert lang.existe("klingon") is False
    assert lang.existe("") is False


def test_toda_faixa_aponta_para_um_nivel_valido():
    """Um CEFR digitado errado numa faixa nova quebraria a meta em silencio:
    a conversao devolveria algo que o nivelamento nao sabe medir."""
    for idioma in lang.IDIOMAS:
        for exame in idioma.exames:
            assert exame.faixas, f"{idioma.codigo}/{exame.id} sem faixas"
            for faixa in exame.faixas:
                assert faixa.cefr in lang.CEFR, f"{idioma.codigo}/{exame.id}: {faixa.cefr}"


def test_catalogo_json_tem_o_formato_que_a_tela_espera():
    dados = lang.catalogo()
    primeiro = dados[0]
    assert set(primeiro) == {"codigo", "nome", "nativo", "exames"}
    exame = primeiro["exames"][0]
    assert set(exame) == {"id", "nome", "descricao", "faixas"}
    assert set(exame["faixas"][0]) == {"rotulo", "cefr", "nota"}
