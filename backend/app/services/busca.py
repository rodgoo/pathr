"""Sanitização de termo de busca digitado, para os DOIS jeitos de filtrar no
PostgREST — que exigem tratamentos diferentes e por isso viviam copiados e
divergindo (o de admin.py, por exemplo, esquecia o `_`).

1. Forma PARAMETRIZADA — `.ilike("coluna", padrao)`: o padrão vai como valor, e
   `%` `_` `\\` são os curingas do LIKE. Basta ESCAPAR: `escapar_ilike`.

2. Forma de STRING de filtro — `.or_("coluna.ilike.*termo*,...")`: aqui o termo
   entra no meio de uma expressão onde vírgula/parêntese são operador, `*`/`%`
   são curinga e `\\`/`"`/`:` têm sentido próprio. A string não tem como escapar
   curinga, então o jeito seguro é REMOVER esses caracteres: `limpar_para_filtro`.
"""


def escapar_ilike(termo: str) -> str:
    """Escapa os curingas do ilike (`\\`, `%`, `_`) para procurar o caractere
    literal em vez de ampliar a busca. Para a forma `.ilike("col", f"%{t}%")`.

    O `\\` vem primeiro: escapá-lo depois de `%`/`_` escaparia os próprios
    escapes recém-inseridos.
    """
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Caracteres que a STRING de filtro do PostgREST (`or=(col.ilike.*x*,...)`) lê
# como sintaxe. Numa busca digitada tudo isso é texto; deixá-lo passar é
# injeção de filtro (listar todo mundo com um `*`, quebrar o `or=` com `,()`).
SINTAXE_DO_FILTRO = frozenset('%_*,().:"\\')


def limpar_para_filtro(termo: str) -> str:
    """Remove os caracteres de sintaxe do filtro `.or_(...)`. Para o termo que
    entra numa expressão de string, onde não dá para escapar curinga."""
    return "".join(letra for letra in termo if letra not in SINTAXE_DO_FILTRO)
