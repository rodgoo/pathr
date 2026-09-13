"""Banir conta: quando, por quê e por quem.

Revision ID: 0028_user_ban
Revises: 0027_defaults_again
Create Date: 2026-09-13

Três colunas em `pathr_user`, e não uma tabela de banimentos: o que as rotas
precisam saber a cada pedido é "esta conta está banida agora?", e a resposta
já vem na linha do usuário que `get_current_user` lê de qualquer jeito — sem
consulta a mais em todo pedido do app. O histórico (quem baniu, quem
desbaniu, quando) fica na trilha de auditoria, `pathr_security_event`.

`banned_by` com ON DELETE SET NULL: apagar a conta de quem baniu não pode
apagar nem desfazer o banimento.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0028_user_ban"
down_revision: Union[str, None] = "0027_defaults_again"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_user", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pathr_user", sa.Column("banned_reason", sa.Text(), nullable=True))
    op.add_column(
        "pathr_user",
        sa.Column(
            "banned_by",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_pathr_user_banned_at", "pathr_user", ["banned_at"])


def downgrade() -> None:
    op.drop_index("ix_pathr_user_banned_at", table_name="pathr_user")
    op.drop_column("pathr_user", "banned_by")
    op.drop_column("pathr_user", "banned_reason")
    op.drop_column("pathr_user", "banned_at")
