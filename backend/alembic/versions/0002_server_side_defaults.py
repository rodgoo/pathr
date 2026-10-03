"""Defaults do lado do banco.

Revision ID: 0002_defaults
Revises: 0001_initial
Create Date: 2026-09-08

A migration 0001 criou as tabelas a partir do metadata do SQLModel, e com isso
herdou um problema que só aparece em uso real: os defaults estavam declarados
no Python (`default_factory=uuid.uuid4`, `Field(default=0)`), e o Python só os
aplica quando o SQLAlchemy monta o INSERT.

Este app nunca monta. Em runtime tudo passa por PostgREST (ver o cabeçalho de
app/models.py), que envia o JSON que o router construiu — sem a coluna. Ela
chega NULL e o banco recusa: "null value in column id violates not-null
constraint". Foi assim que o seed do catálogo de tags falhou, e teria falhado
igual no primeiro cadastro de usuário.

O conserto está em `_mirror_defaults_to_database()` (app/models.py), que copia
todo default do Python para o banco. Esta migration aplica o mesmo espelho às
tabelas que já existem.

Deriva do metadata em vez de listar as 132 colunas à mão: uma lista escrita
aqui sairia de sincronia com o modelo na primeira coluna nova, que é
exatamente o tipo de divergência que causou o bug original.

## Só coluna que já existe

A 0001 passou a criar só as 28 tabelas (com só as colunas) que existiam no
dia em que esta migration foi escrita (ver o cabeçalho dela) — tabela nova
(passkey, atividade prática, notícias...) e coluna nova em tabela antiga
(`pathr_profile.country`, de 0003 em diante) nascem só nas migrations
seguintes. Sem filtrar por TABELA e por COLUNA, este laço tentava
`ALTER TABLE ... ALTER COLUMN "country"` antes de a coluna existir, e
`alembic upgrade head` do zero quebrava aqui com "relation/column does not
exist" — pego rodando esta correção contra um Postgres de verdade, não só a
suíte de testes (que não sobe banco). A 0027, que faz o mesmo espelho para o
que foi criado depois da 0002, já filtrava por `information_schema.columns`;
esta migration ganhou a mesma trava.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula (e corrige) SQLModel.metadata

revision: str = "0002_defaults"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIX = "pathr_"


def _colunas_existentes(conexao) -> set[tuple[str, str]]:
    linhas = conexao.execute(
        sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name LIKE 'pathr\\_%'"
        )
    )
    return {(linha.table_name, linha.column_name) for linha in linhas}


def _columns_with_defaults(conexao) -> list[tuple[str, str, str]]:
    """(tabela, coluna, expressão SQL) para todo default declarado no modelo,
    restrito às colunas que JÁ EXISTEM no banco neste ponto da migração.

    A expressão sai do compilador de DDL do próprio dialeto, e não de uma
    interpolação nossa. A diferença importa: um default como `{}` num JSONB
    precisa virar `'{}'` com aspas, enquanto `gen_random_uuid()` precisa
    ficar SEM elas. Escrever essa distinção à mão foi o que quebrou a primeira
    versão desta migration — e é exatamente o que este compilador já resolve,
    já que foi ele quem gerou o CREATE TABLE da 0001.
    """
    existentes = _colunas_existentes(conexao)
    dialect = postgresql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)

    found: list[tuple[str, str, str]] = []
    for table in SQLModel.metadata.tables.values():
        if not table.name.startswith(PREFIX):
            continue
        for column in table.columns:
            if (table.name, column.name) not in existentes:
                continue
            rendered = compiler.get_column_default_string(column)
            if rendered is None:
                continue
            found.append((table.name, column.name, rendered))
    return found


def upgrade() -> None:
    conexao = op.get_bind()
    for table, column, expression in _columns_with_defaults(conexao):
        op.execute(
            sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT {expression}')
        )


def downgrade() -> None:
    conexao = op.get_bind()
    for table, column, _expression in _columns_with_defaults(conexao):
        op.execute(sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT'))
