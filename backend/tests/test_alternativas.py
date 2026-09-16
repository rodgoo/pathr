"""Alternativas citadas a partir de 1 no texto que a pessoa lê.

O índice interno continua 0 a 3; o que se segura aqui é a explicação: se ela
conta do zero ("a alternativa 0"), todas as citações sobem uma; se já conta a
partir de 1, fica como está.
"""

from app.routers import language_practice, quizzes
from app.services.alternativas import numerar_de_um


def test_texto_que_conta_do_zero_passa_a_contar_de_um():
    assert numerar_de_um("A alternativa 0 está correta; a opção 2 confunde rebase.") == (
        "A alternativa 1 está correta; a opção 3 confunde rebase."
    )
    assert numerar_de_um("As alternativas 0 e 3 são armadilhas; o índice 1 é o certo.") == (
        "As alternativas 1 e 4 são armadilhas; a alternativa 2 é o certo."
    )
    assert numerar_de_um("Option 0 is right, not option 2.") == "Option 1 is right, not option 3."


def test_texto_que_ja_conta_de_um_nao_muda():
    texto = "A alternativa 2 é a certa; a 4 é a armadilha."
    assert numerar_de_um(texto) == texto
    assert numerar_de_um("Versão 0 do protocolo HTTP.") == "Versão 0 do protocolo HTTP."
    assert numerar_de_um(None) is None and numerar_de_um("") == ""


def test_prompts_pedem_contagem_a_partir_de_um():
    assert "a partir de 1" in quizzes.SYSTEM_PROMPT
    fonte = open(language_practice.__file__, encoding="utf-8").read()
    assert "cite alternativas a partir de 1" in fonte


def test_nao_renumera_quando_ja_conta_de_um():
    from app.services.alternativas import numerar_de_um

    # Cita "alternativa 4": num quiz de 4 opções isso prova contagem a partir de
    # 1, então o texto (mesmo com um "0" solto) não pode ser deslocado.
    texto = "A alternativa 0 é distrator; a alternativa 4 está correta."
    assert numerar_de_um(texto) == texto


def test_renumera_texto_claramente_do_zero():
    from app.services.alternativas import numerar_de_um

    assert (
        numerar_de_um("A alternativa 0 erra; a alternativa 2 acerta.")
        == "A alternativa 1 erra; a alternativa 3 acerta."
    )
