"""Exemplos do Laboratório com vários arquivos.

Revision ID: 0033_walkthrough_files
Revises: 0032_doubt_examples
Create Date: 2026-09-15

Um exemplo real raramente é um arquivo: o workflow do GitHub chama o teste; a
API Spring é Controller, Service, Repository e Entity. `files` guarda o
conjunto ([{caminho, linguagem, conteudo}]) e cada passo do traço diz em qual
arquivo acontece (services/code_lab_projeto.py).

`code` continua sendo gravado com o arquivo principal: exemplos antigos só têm
ele, e quem lê só `code` (o contexto do "Perguntar") segue funcionando.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0033_walkthrough_files"
down_revision: Union[str, None] = "0032_doubt_examples"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_walkthrough",
        sa.Column("files", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("pathr_walkthrough", "files")
