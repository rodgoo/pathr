"""Um duplo mínimo do cliente Supabase, para testar regras de autenticação.

A suíte é offline (ver conftest.py), então as rotas que falam com o banco só
podem ser exercitadas com um substituto. Este arquivo implementa apenas o que
as rotas de auth realmente encadeiam — `select/eq/limit/execute`,
`insert`, `update/eq` e `delete/eq` —, e nada além disso: um duplo que aceita
mais do que o código usa dá a falsa impressão de cobrir mais.

As linhas ficam em dicionários por tabela, comparadas por igualdade simples.
Não é um Postgres; é o suficiente para responder "esta rota recusa quem não
confirmou o e-mail?".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional


class _Resultado:
    def __init__(self, data: list[dict], count: Optional[int] = None):
        self.data = data
        self.count = count


class _Consulta:
    def __init__(self, banco: "FakeSupabase", tabela: str):
        self._banco = banco
        self._tabela = tabela
        self._filtros: list[tuple[str, Any]] = []
        # Filtros de pertinência (`in_`), separados dos de igualdade porque a
        # comparação é outra: "está nesta lista", e não "é igual a isto".
        self._filtros_in: list[tuple[str, set[str]]] = []
        self._operacao = "select"
        self._payload: Any = None
        self._limite: Optional[int] = None
        # Filtros que não são igualdade: `lte` e as negações de `not_`.
        self._predicados: list[Any] = []
        self._ordem: list[tuple[str, bool]] = []

    @property
    def not_(self) -> "_Negacao":
        """`not_.is_("x", "null")` — usado pelo treino de idioma."""
        return _Negacao(self)

    def lte(self, coluna: str, valor: Any) -> "_Consulta":
        # Comparação de texto: datas ISO-8601 com o mesmo fuso ordenam igual.
        self._predicados.append(
            lambda linha: linha.get(coluna) is not None and str(linha.get(coluna)) <= str(valor)
        )
        return self

    # -- construção da consulta -------------------------------------------
    def select(self, *_args: Any, **_kwargs: Any) -> "_Consulta":
        self._operacao = "select"
        return self

    def insert(self, payload: Any) -> "_Consulta":
        self._operacao = "insert"
        self._payload = payload
        return self

    def upsert(self, payload: Any, **_kwargs: Any) -> "_Consulta":
        self._operacao = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict) -> "_Consulta":
        self._operacao = "update"
        self._payload = payload
        return self

    def delete(self) -> "_Consulta":
        self._operacao = "delete"
        return self

    def eq(self, coluna: str, valor: Any) -> "_Consulta":
        self._filtros.append((coluna, valor))
        return self

    def in_(self, coluna: str, valores: Any) -> "_Consulta":
        # str() nos dois lados, como em `_casa`: o PostgREST devolve UUID como
        # texto e o código compara ora com UUID, ora com str.
        self._filtros_in.append((coluna, {str(v) for v in (valores or [])}))
        return self

    def is_(self, coluna: str, valor: Any) -> "_Consulta":
        # O PostgREST usa is_(coluna, "null") para IS NULL. Guardamos como um
        # filtro de None, que é como a linha aparece no dicionário.
        self._filtros.append((coluna, None if valor in ("null", None) else valor))
        return self

    def limit(self, quantidade: int) -> "_Consulta":
        self._limite = quantidade
        return self

    def order(self, coluna: Optional[str] = None, *_args: Any, desc: bool = False, **_kwargs: Any) -> "_Consulta":
        # Ordena de verdade: o treino mostra os exercícios pela posição, e um
        # duplo que ignorasse a ordem passaria num teste que o banco reprova.
        if coluna:
            self._ordem.append((coluna, desc))
        return self

    # -- execução ----------------------------------------------------------
    def _casa(self, linha: dict) -> bool:
        # str() dos dois lados: o PostgREST devolve UUID como texto, e o
        # código compara ora com UUID ora com str.
        for coluna, valor in self._filtros:
            atual = linha.get(coluna)
            if valor is None:
                if atual is not None:
                    return False
            elif str(atual) != str(valor):
                return False
        for coluna, valores in self._filtros_in:
            if str(linha.get(coluna)) not in valores:
                return False
        return all(predicado(linha) for predicado in self._predicados)

    def execute(self) -> _Resultado:
        linhas = self._banco.tabelas.setdefault(self._tabela, [])

        if self._operacao == "select":
            achadas = [l for l in linhas if self._casa(l)]
            for coluna, desc in reversed(self._ordem):
                achadas.sort(
                    key=lambda l: (l.get(coluna) is None, str(l.get(coluna) or "").zfill(12)
                                   if isinstance(l.get(coluna), int) else str(l.get(coluna) or "")),
                    reverse=desc,
                )
            if self._limite is not None:
                achadas = achadas[: self._limite]
            return _Resultado([dict(l) for l in achadas], count=len(achadas))

        if self._operacao == "insert":
            novas = self._payload if isinstance(self._payload, list) else [self._payload]
            for nova in novas:
                # O Postgres preenche id e created_at por default do servidor
                # (ver _mirror_defaults_to_database em app/models.py), e o
                # PostgREST devolve a linha já preenchida. Sem imitar isso, o
                # código que lê created["id"] logo após o insert quebraria só
                # no teste — um falso positivo ao contrário.
                nova = dict(nova)
                nova.setdefault("id", str(uuid.uuid4()))
                nova.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                linhas.append(nova)
            novas = [dict(l) for l in linhas[-len(novas):]]
            self._banco.escritas.append((self._tabela, "insert", novas))
            return _Resultado(novas)

        if self._operacao == "update":
            atingidas = [l for l in linhas if self._casa(l)]
            for linha in atingidas:
                linha.update(self._payload)
            self._banco.escritas.append((self._tabela, "update", self._payload))
            return _Resultado([dict(l) for l in atingidas])

        if self._operacao == "delete":
            restantes = [l for l in linhas if not self._casa(l)]
            removidas = len(linhas) - len(restantes)
            linhas[:] = restantes
            self._banco.escritas.append((self._tabela, "delete", removidas))
            return _Resultado([])

        raise AssertionError(f"operação não suportada pelo duplo: {self._operacao}")


class _Negacao:
    def __init__(self, consulta: _Consulta):
        self._consulta = consulta

    def is_(self, coluna: str, valor: Any) -> _Consulta:
        alvo = None if valor in ("null", None) else valor
        if alvo is None:
            self._consulta._predicados.append(lambda linha: linha.get(coluna) is not None)
        else:
            self._consulta._predicados.append(lambda linha: str(linha.get(coluna)) != str(alvo))
        return self._consulta


class FakeSupabase:
    def __init__(self, **tabelas: list[dict]):
        self.tabelas: dict[str, list[dict]] = {k: [dict(l) for l in v] for k, v in tabelas.items()}
        self.escritas: list[tuple[str, str, Any]] = []

    def table(self, nome: str) -> _Consulta:
        return _Consulta(self, nome)

    # -- consultas de conveniência para as asserções ------------------------
    def linhas(self, tabela: str) -> list[dict]:
        return self.tabelas.get(tabela, [])

    def eventos(self) -> list[str]:
        return [l.get("event_type") for l in self.linhas("pathr_security_event")]
