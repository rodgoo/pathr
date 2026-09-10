"""O checklist da semana, um por pessoa por semana.

Revision ID: 0012_weekly_checklist
Revises: 0011_explanations
Create Date: 2026-09-10

Uma linha por (usuario, segunda-feira da semana), com os itens em JSONB. Os
itens nao viram tabela propria porque nao tem vida fora da semana: sao gerados
juntos, marcados juntos e descartados juntos quando a semana vira. Uma tabela
de itens seria um JOIN a mais em toda abertura da tela inicial para guardar o
que cabe numa coluna.

`roadmap_id` existe para a semana saber de qual plano saiu: gerar um roadmap
novo no meio da semana tem que refazer o checklist, e sem a referencia a lista
velha continuaria apontando para modulos que nao existem mais.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_weekly_checklist"
down_revision: Union[str, None] = "0011_explanations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_weekly_checklist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("roadmap_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_roadmap.id", ondelete="CASCADE"), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_index", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "week_start", name="uq_pathr_weekly_checklist_semana"),
    )
    op.create_index("ix_pathr_weekly_checklist_user_id", "pathr_weekly_checklist", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_weekly_checklist_user_id", table_name="pathr_weekly_checklist")
    op.drop_table("pathr_weekly_checklist")
