"""Alternativas contadas a partir de 1 no texto que a pessoa lê.

Internamente a certa é um índice de 0 a 3 (`correta`, `correct_index`): é
assim que o modelo devolve e que a correção compara. Mas o prompt dizia isso
ao modelo, e ele passou a escrever explicações como "a alternativa 0 está
correta" — para quem lê, a primeira opção é a 1.

Os prompts agora pedem 1 a 4. Para o que já foi gerado (e para o modelo que
escorregar), `numerar_de_um` corrige na saída: se o texto cita a alternativa
0, ele está contando do zero, e todas as citações sobem uma. Sem nenhum 0 não
há como saber, e o texto fica como está.
"""

import re

REGRA_DO_PROMPT = (
    "Na explicação, cite as alternativas contando a partir de 1 (a primeira é a "
    "alternativa 1, a última a 4) ou pelo próprio texto delas — nunca pelo índice."
)

_CITACAO = re.compile(
    r"\b(alternativas?|op[cç](?:ão|ao|ões|oes)|options?|choices?|[íi]ndices?)"
    r"(\s+(?:de\s+)?(?:n[º°o.]\s*)?)"
    r"([0-9](?:\s*(?:,|e|and|ou|or)\s*[0-9])*)\b",
    re.IGNORECASE,
)
_NUMERO = re.compile(r"[0-9]")


def numerar_de_um(texto):
    if not texto or not isinstance(texto, str):
        return texto
    citacoes = list(_CITACAO.finditer(texto))
    numeros = [int(d) for m in citacoes for d in _NUMERO.findall(m.group(3))]
    # Sem nenhum 0, não há prova de contagem a partir do zero: fica como está.
    if 0 not in numeros:
        return texto
    # Cita "alternativa 4" (ou mais): num quiz de 4 opções, o zero-based vai só
    # de 0 a 3, então um 4 prova que o texto JÁ conta a partir de 1. Somar +1
    # aqui estragaria uma citação correta — melhor não mexer no texto ambíguo.
    if any(n >= 4 for n in numeros):
        return texto

    def subir(m: re.Match) -> str:
        palavra = m.group(1)
        # "índice 2" não é como se fala de uma opção: vira "alternativa 3".
        if palavra.lower().startswith(("índice", "indice")):
            palavra = "alternativas" if palavra.lower().endswith("s") else "alternativa"
        numeros = _NUMERO.sub(lambda n: str(int(n.group(0)) + 1), m.group(3))
        return f"{palavra}{m.group(2)}{numeros}"

    # "o índice 1" vira "a alternativa 2", e não "o alternativa 2".
    texto = re.sub(
        r"\b([oO])(s?)(\s+)(?=[íi]ndices?\s+(?:de\s+)?[0-9])",
        lambda m: ("A" if m.group(1) == "O" else "a") + m.group(2) + m.group(3),
        texto,
    )
    return _CITACAO.sub(subir, texto)
