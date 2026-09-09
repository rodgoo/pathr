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


def _columns_with_defaults() -> list[tuple[str, str, str]]:
    """(tabela, coluna, expressão SQL) para todo default declarado no modelo.

    A expressão sai do compilador de DDL do próprio dialeto, e não de uma
    interpolação nossa. A diferença importa: um default como `{}` num JSONB
    precisa virar `'{}'` com aspas, enquanto `gen_random_uuid()` precisa
    ficar SEM elas. Escrever essa distinção à mão foi o que quebrou a primeira
    versão desta migration — e é exatamente o que este compilador já resolve,
    já que foi ele quem gerou o CREATE TABLE da 0001.
    """
    dialect = postgresql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)

    found: list[tuple[str, str, str]] = []
    for table in SQLModel.metadata.tables.values():
        if not table.name.startswith(PREFIX):
            continue
        for column in table.columns:
            rendered = compiler.get_column_default_string(column)
            if rendered is None:
                continue
            found.append((table.name, column.name, rendered))
    return found


def upgrade() -> None:
    for table, column, expression in _columns_with_defaults():
        op.execute(
            sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT {expression}')
        )


def downgrade() -> None:
    for table, column, _expression in _columns_with_defaults():
        op.execute(sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT'))
