"""Registro do que ja foi enviado, para nao enviar duas vezes.

Revision ID: 0014_email_log
Revises: 0013_passkeys
Create Date: 2026-09-11

O disparo roda de hora em hora e decide por pessoa, no fuso dela. A janela de
envio e de duas horas de proposito -- a maquina na Fly suspende e leva segundos
para acordar, e uma comparacao exata de hora perderia o aviso do dia por causa
de um minuto. E a unicidade (usuario, tipo, dia) que impede a repeticao, nao a
estreiteza da janela.

`sent_on` e DATE e nao timestamp: o que importa e "ja saiu hoje para esta
pessoa", no dia LOCAL dela.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_email_log"
down_revision: Union[str, None] = "0013_passkeys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_email_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "kind", "sent_on", name="uq_pathr_email_log"),
    )
    op.create_index("ix_pathr_email_log_user_id", "pathr_email_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_email_log_user_id", table_name="pathr_email_log")
    op.drop_table("pathr_email_log")
