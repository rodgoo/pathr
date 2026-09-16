"""Feature flags: o estado (todos|admin|ninguem) de cada recurso, quando mudado.

Revision ID: 0036_feature_flag
Revises: 0035_candidatura_automatica
Create Date: 2026-09-16

A tabela guarda só o OVERRIDE feito na tela de admin — uma linha por recurso
mexido. O catálogo do que existe e o estado padrão de cada um mora no código
(services/features.py), então um recurso sem linha aqui fica no padrão, e uma
linha órfã (recurso removido do código) é simplesmente ignorada na leitura.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036_feature_flag"
down_revision: Union[str, None] = "0035_candidatura_automatica"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_feature_flag",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("state", sa.String(), nullable=False, server_default="todos"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("state in ('todos','admin','ninguem')", name="ck_pathr_feature_flag_state"),
    )
    op.execute("alter table pathr_feature_flag enable row level security")
    op.execute("revoke all on pathr_feature_flag from anon, authenticated")


def downgrade() -> None:
    op.drop_table("pathr_feature_flag")
