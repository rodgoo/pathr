"""A conferencia do traco de execucao.

Um modelo de linguagem erra ordem de execucao e erra aritmetica. Exibir o que
ele disser como se fosse a execucao de verdade ensinaria errado com cara de
autoridade -- pior que nao ter o recurso. Estes testes cobrem a recusa.
"""

import pytest

from app.services import code_lab

CODIGO = "total = 0\n\nfor n in [1, 2]:\n    total += n\n\nprint(total)"


def passo(linha, **extra):
    return {"linha": linha, "acao": f"executa a linha {linha}", **extra}


def test_numera_as_linhas_como_a_tela_mostra():
    assert code_lab.linhas_de(CODIGO) == [
        "total = 0", "", "for n in [1, 2]:", "    total += n", "", "print(total)"
    ]


def test_ignora_quebra_do_windows_e_linha_final_solta():
    assert code_lab.linhas_de("a = 1\r\nb = 2\n\n") == ["a = 1", "b = 2"]


def test_traco_coerente_passa():
    passos = [passo(1), passo(3), passo(4), passo(6, saida="3")]
    assert len(code_lab.conferir(CODIGO, passos)) == 4


def test_laco_pode_repetir_a_mesma_linha():
    """Duas voltas do for sao dois passos na mesma linha -- e o certo."""
    passos = [passo(3), passo(4), passo(3), passo(4), passo(6, saida="3")]
    assert len(code_lab.conferir(CODIGO, passos)) == 5


@pytest.mark.parametrize(
    "quebrado,por_que",
    [
        ([passo(1), passo(99)], "linha que nao existe"),
        ([passo(1), passo(0)], "linha zero: o traco e 1-based"),
        ([passo(1), passo(2)], "linha em branco nao executa"),
        ([passo(1), {"linha": "tres", "acao": "x"}], "linha que nao e numero"),
        ([passo(1), {"linha": 3, "acao": "   "}], "passo sem descricao"),
    ],
)
def test_traco_incoerente_e_recusado_inteiro(quebrado, por_que):
    """Recusar e melhor que consertar: um passo movido em silencio para a
    linha mais proxima ensinaria uma ordem de execucao falsa."""
    assert code_lab.conferir(CODIGO, quebrado) == [], por_que


def test_traco_truncado_e_recusado():
    """O modelo as vezes descreve os primeiros passos e para: a recursao nunca
    desenrola e nada e impresso. Coerente, e ainda assim pior que nada -- a
    pessoa acompanha ate a metade e conclui que o programa termina ali.

    O prompt obriga o programa a imprimir, entao traco sem NENHUMA saida nao
    chegou ao primeiro print."""
    assert code_lab.conferir(CODIGO, [passo(1), passo(3), passo(4)]) == []


def test_traco_completo_com_saida_passa():
    assert len(code_lab.conferir(CODIGO, [passo(1), passo(3), passo(6, saida="3")])) == 3


def test_traco_curto_demais_nao_mostra_execucao():
    assert code_lab.conferir(CODIGO, [passo(1)]) == []
    assert code_lab.conferir(CODIGO, []) == []


def test_codigo_longo_demais_para_o_formato():
    longo = "\n".join(f"x{i} = {i}" for i in range(200))
    assert code_lab.conferir(longo, [passo(1), passo(2)]) == []


def test_estado_vira_texto_sempre():
    """O painel mostra o valor, nao faz conta com ele. Um modelo que devolve 3
    numa hora e '3' na outra nao pode quebrar a tela."""
    passos = [
        passo(1, estado=[{"nome": "total", "valor": 0}]),
        passo(4, estado=[{"nome": "total", "valor": "1"}, {"nome": 123, "valor": "x"}]),
        passo(6, saida="3"),
    ]
    limpos = code_lab.conferir(CODIGO, passos)
    assert limpos[0]["estado"] == [{"nome": "total", "valor": "0"}]
    assert limpos[1]["estado"][1]["nome"] == "123"


def test_estado_malformado_nao_derruba_o_passo():
    limpos = code_lab.conferir(
        CODIGO, [passo(1, estado="nada disso"), passo(3, estado=[1, 2]), passo(6, saida="3")]
    )
    assert [p["estado"] for p in limpos] == [[], [], []]


def test_saida_e_acumulada():
    """Painel de saida de depurador cresce. Mostrar so a linha do passo atual
    faria a impressao anterior sumir ao avancar."""
    passos = code_lab.conferir(
        CODIGO, [passo(1, saida="um"), passo(3), passo(6, saida="dois")]
    )
    assert code_lab.saida_acumulada(passos, 0) == "um"
    assert code_lab.saida_acumulada(passos, 1) == "um"
    assert code_lab.saida_acumulada(passos, 2) == "um\ndois"


def test_catalogo_de_linguagens():
    ids = {linguagem["id"] for linguagem in code_lab.catalogo()}
    assert {"python", "javascript", "rust", "sql"} <= ids
    assert code_lab.existe("python") and not code_lab.existe("cobol")
    assert code_lab.realce("csharp") == "csharp"
    assert code_lab.realce("inventada") == "text"
