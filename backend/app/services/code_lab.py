"""Códigos prontos com execução comentada, linha a linha.

## O problema que isto resolve

Ler código pronto ensina pouco. A pessoa passa os olhos, reconhece as palavras
e segue — a mesma ilusão de competência que o Feynman (routers/explanations.py)
existe para quebrar, só que com código. O que ensina é ver o programa RODAR: a
linha que está executando agora, o que cada variável vale nesse instante, e o
que já foi impresso.

É isso que um depurador dá a quem já sabe usar um. Quem está aprendendo não
tem ambiente montado, não sabe pôr breakpoint, e desiste antes. Aqui o passo a
passo vem junto com o código.

## O traço é conferido, não acreditado

Quem produz o traço é um modelo de linguagem, e modelo de linguagem erra
aritmética e erra ordem de execução. Exibir o que ele disser como se fosse a
execução de verdade seria ensinar errado com cara de autoridade — pior que não
ter o recurso.

Então o traço passa por `conferir()` antes de virar tela: passo que aponta
para linha que não existe, passo que aponta para linha em branco, traço vazio
ou grande demais são recusados. Isso não prova que o traço está certo — prova
que ele é COERENTE com o código exibido, que é o erro que aparece na prática
quando o modelo inventa.

O que resta de incerteza é dito na tela, não escondido: a execução é comentada,
não medida. Por isso o prompt exige programa curto, determinístico, sem
entrada, sem rede e sem aleatoriedade — as três coisas que tornariam o traço
impossível de conferir até rodando.
"""

from __future__ import annotations

from typing import Any

# As linguagens oferecidas. `rotulo` é o que aparece na tela; `realce` é o
# identificador de sintaxe que o bloco de código usa.
LINGUAGENS: tuple[dict[str, str], ...] = (
    {"id": "python", "rotulo": "Python", "realce": "python"},
    {"id": "javascript", "rotulo": "JavaScript", "realce": "javascript"},
    {"id": "typescript", "rotulo": "TypeScript", "realce": "typescript"},
    {"id": "java", "rotulo": "Java", "realce": "java"},
    {"id": "csharp", "rotulo": "C#", "realce": "csharp"},
    {"id": "go", "rotulo": "Go", "realce": "go"},
    {"id": "rust", "rotulo": "Rust", "realce": "rust"},
    {"id": "c", "rotulo": "C", "realce": "c"},
    {"id": "cpp", "rotulo": "C++", "realce": "cpp"},
    {"id": "php", "rotulo": "PHP", "realce": "php"},
    {"id": "ruby", "rotulo": "Ruby", "realce": "ruby"},
    {"id": "kotlin", "rotulo": "Kotlin", "realce": "kotlin"},
    {"id": "swift", "rotulo": "Swift", "realce": "swift"},
    {"id": "dart", "rotulo": "Dart", "realce": "dart"},
    {"id": "sql", "rotulo": "SQL", "realce": "sql"},
    {"id": "bash", "rotulo": "Shell / Bash", "realce": "bash"},
)

_POR_ID = {linguagem["id"]: linguagem for linguagem in LINGUAGENS}

NIVEIS: tuple[str, ...] = ("iniciante", "intermediario", "avancado")

# Um traço mais curto que isto não mostra execução nenhuma; mais longo que isto
# ninguém percorre até o fim, e é sinal de que o modelo gerou um programa
# grande demais para o formato.
_MINIMO_DE_PASSOS = 2
_MAXIMO_DE_PASSOS = 60
_MAXIMO_DE_LINHAS = 80


def existe(linguagem: str) -> bool:
    return linguagem in _POR_ID


def realce(linguagem: str) -> str:
    return _POR_ID.get(linguagem, {}).get("realce", "text")


def rotulo(linguagem: str) -> str:
    return _POR_ID.get(linguagem, {}).get("rotulo", linguagem)


def catalogo() -> list[dict[str, str]]:
    return [dict(linguagem) for linguagem in LINGUAGENS]


def linhas_de(codigo: str) -> list[str]:
    """As linhas como a tela vai numerá-las: 1-based, sem o \n final solto."""
    return codigo.replace("\r\n", "\n").rstrip("\n").split("\n")


def conferir(codigo: str, passos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deixa passar só o traço coerente com o código. Devolve [] se não houver.

    Recusar é melhor que consertar: um passo que aponta para a linha errada,
    silenciosamente movido para a linha mais próxima, ensinaria uma ordem de
    execução falsa com a mesma cara de certeza. Sem traço coerente, a tela
    mostra o código e a explicação e diz que o passo a passo não saiu.
    """
    linhas = linhas_de(codigo)
    if not linhas or len(linhas) > _MAXIMO_DE_LINHAS:
        return []

    limpos: list[dict[str, Any]] = []
    for passo in passos[:_MAXIMO_DE_PASSOS]:
        try:
            numero = int(passo.get("linha"))
        except (TypeError, ValueError):
            return []
        if not 1 <= numero <= len(linhas):
            return []
        # Linha em branco não executa. Um traço que para numa delas não está
        # descrevendo este programa.
        if not linhas[numero - 1].strip():
            return []
        acao = str(passo.get("acao") or "").strip()
        if not acao:
            return []

        estado = passo.get("estado")
        limpos.append(
            {
                "linha": numero,
                "acao": acao,
                "estado": _estado(estado),
                "saida": str(passo.get("saida") or ""),
            }
        )

    if len(limpos) < _MINIMO_DE_PASSOS:
        return []

    # O traço precisa CHEGAR AO FIM, e não só ser coerente onde existe.
    #
    # O modelo às vezes descreve os três primeiros passos e para — a recursão
    # nunca desenrola, o laço nunca fecha, e nada é impresso. Isso passa em
    # todas as checagens acima (as linhas existem, não estão em branco, têm
    # descrição) e ainda assim é pior que traço nenhum: a pessoa acompanha até
    # a metade e conclui que o programa termina ali.
    #
    # O prompt obriga o programa a imprimir. Então um traço que não contém
    # NENHUMA saída não chegou ao primeiro print — é truncado, por definição.
    if not any(passo["saida"] for passo in limpos):
        return []

    return limpos


def _estado(bruto: Any) -> list[dict[str, str]]:
    """As variáveis vivas no fim do passo, como pares nome/valor em texto.

    Texto e não número: o painel mostra o valor, não faz conta com ele, e um
    modelo que devolve `3` numa hora e `"3"` na outra não pode quebrar a tela.
    """
    if not isinstance(bruto, list):
        return []
    saida: list[dict[str, str]] = []
    for item in bruto[:12]:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome") or "").strip()
        if not nome:
            continue
        saida.append({"nome": nome[:40], "valor": str(item.get("valor", ""))[:120]})
    return saida


def saida_acumulada(passos: list[dict[str, Any]], ate: int) -> str:
    """Tudo que o programa imprimiu até o passo `ate` (inclusive, 0-based).

    Acumulada e não por passo: o painel de saída de um depurador cresce, e
    mostrar só a linha do passo atual faria a impressão anterior sumir ao
    avançar — o oposto do que a pessoa precisa ver para seguir o programa.
    """
    pedacos = [p["saida"] for p in passos[: ate + 1] if p.get("saida")]
    return "\n".join(pedacos)
