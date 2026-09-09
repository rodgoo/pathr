"""Schema inicial do PathR.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-08

Esta primeira migration cria as tabelas a partir do metadata do SQLModel em
vez de repetir cada `op.create_table` à mão. São 28 tabelas descritas em
app/models.py, e transcrevê-las aqui criaria uma segunda cópia do schema que
inevitavelmente sairia de sincronia com a primeira.

As migrations SEGUINTES devem ser geradas normalmente com
`alembic revision --autogenerate`, que produz o diff explícito — o atalho
vale só para o marco zero, onde o diff É o schema inteiro.

O filtro por prefixo é a rede de proteção contra um `DATABASE_URL` apontado
para o banco errado: um create_all sem filtro tentaria criar tabelas em cima
de um schema que não é deste app. Ver alembic/env.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula SQLModel.metadata

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIX = "pathr_"


def _pathr_tables() -> list[sa.Table]:
    """Só o que é deste app, na ordem de dependência que o SQLAlchemy resolve."""
    return [
        table
        for table in SQLModel.metadata.sorted_tables
        if table.name.startswith(PREFIX)
    ]


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind, tables=_pathr_tables(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    # Ordem reversa: filho antes do pai, senão a FK barra o drop.
    SQLModel.metadata.drop_all(bind, tables=list(reversed(_pathr_tables())), checkfirst=True)
