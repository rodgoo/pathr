"""Defaults do lado do banco, de novo, para as tabelas criadas depois da 0002.

Revision ID: 0027_defaults_again
Revises: 0026_friend_notices
Create Date: 2026-09-13

A 0002 copiou para o banco os defaults do Python das tabelas que existiam
naquele dia. As migrações seguintes que criaram tabela com `op.create_table`
escrito à mão não repetiram o espelho — e a `pathr_activity_draft` (0009)
nasceu com `id` sem default. Pelo PostgREST o INSERT chega sem a coluna, o
banco recusa ("null value in column id"), e o rascunho da atividade prática
nunca gravou: a tela dizia "não consegui gravar".

Esta migração refaz o espelho para todas as tabelas, com duas travas que a
0002 não precisava:

- só coluna que EXISTE no banco (o modelo pode ter coluna de migração futura);
- só coluna SEM default hoje — um default escrito à mão numa migração vence o
  do modelo, e não é esta migração que vai trocá-lo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

from app import models  # noqa: F401 — popula (e corrige) SQLModel.metadata

revision: str = "0027_defaults_again"
down_revision: Union[str, None] = "0026_friend_notices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIX = "pathr_"


def upgrade() -> None:
    conexao = op.get_bind()
    sem_default = {
        (linha.table_name, linha.column_name)
        for linha in conexao.execute(
            sa.text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name LIKE 'pathr\\_%' "
                "AND column_default IS NULL"
            )
        )
    }
    dialect = postgresql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)
    for tabela in SQLModel.metadata.tables.values():
        if not tabela.name.startswith(PREFIX):
            continue
        for coluna in tabela.columns:
            if (tabela.name, coluna.name) not in sem_default:
                continue
            expressao = compiler.get_column_default_string(coluna)
            if expressao is None:
                continue
            op.execute(
                sa.text(f'ALTER TABLE "{tabela.name}" ALTER COLUMN "{coluna.name}" SET DEFAULT {expressao}')
            )


def downgrade() -> None:
    # Nada a desfazer com segurança: não há registro de quais colunas estavam
    # sem default, e tirar um default que funciona só recriaria o defeito.
    pass
