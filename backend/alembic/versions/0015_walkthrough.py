"""Codigos prontos com execucao comentada linha a linha.

Revision ID: 0015_walkthrough
Revises: 0014_email_log
Create Date: 2026-09-11

`steps` e jsonb e nao tabela filha: o traco so faz sentido inteiro e junto com
o codigo dele. Um passo isolado nao e consultado, nao e ordenado por outra
coisa que nao a propria posicao, e nao vive sem o programa -- uma tabela
separada so pagaria join para nunca ser usada sozinha.

O traco pode estar VAZIO de proposito: services/code_lab.conferir() recusa
traco incoerente com o codigo, e o exemplo continua valendo como codigo
comentado. Por isso nao ha NOT NULL util alem do default.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_walkthrough"
down_revision: Union[str, None] = "0014_email_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_walkthrough",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("level", sa.String(), nullable=False, server_default="iniciante"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False, server_default=""),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("concepts", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_pathr_walkthrough_user_id", "pathr_walkthrough", ["user_id"])
    # A tela filtra por linguagem dentro da propria conta.
    op.create_index("ix_pathr_walkthrough_user_lang", "pathr_walkthrough",
                    ["user_id", "language"])


def downgrade() -> None:
    op.drop_index("ix_pathr_walkthrough_user_lang", table_name="pathr_walkthrough")
    op.drop_index("ix_pathr_walkthrough_user_id", table_name="pathr_walkthrough")
    op.drop_table("pathr_walkthrough")
