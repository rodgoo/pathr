"""Leitura dos erros que o banco devolve, comum a quem grava por PostgREST."""

from __future__ import annotations


def e_violacao_de_unicidade(erro: BaseException) -> bool:
    """O banco recusou por índice único (23505)?

    O cliente do Supabase embrulha o erro do PostgREST de formas diferentes
    conforme a versão — às vezes um objeto com `.code`, às vezes um dicionário,
    às vezes só a mensagem. Procura-se o código nos três, e por último o texto.
    """
    codigo = getattr(erro, "code", None)
    if codigo is None and getattr(erro, "args", None):
        primeiro = erro.args[0]
        if isinstance(primeiro, dict):
            codigo = primeiro.get("code")
    if str(codigo) == "23505":
        return True
    texto = str(erro).lower()
    return "23505" in texto or "duplicate key" in texto or "already exists" in texto
