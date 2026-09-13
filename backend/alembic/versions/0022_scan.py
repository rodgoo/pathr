"""Varredura diária: o registro de erros do servidor e a trava do resumo.

Revision ID: 0022_scan
Revises: 0021_report
Create Date: 2026-09-13

`pathr_error_event` guarda cada exceção não tratada que virou 500. Antes ela
só ia para o log da Fly, que roda e some — ninguém contava quantas vezes a
mesma rota quebrou ontem. A mensagem é gravada já REDIGIDA (e-mail, UUID,
número longo e token viram marcador): o texto de uma exceção costuma carregar
o valor que causou o erro, e esse valor é dado de alguém.

`pathr_scan_run` é uma linha por dia: é ela, com a data como chave única, que
impede o resumo de sair duas vezes se a rotina for disparada de novo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_scan"
down_revision: Union[str, None] = "0021_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_error_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("error_type", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_pathr_error_event_occurred_at", "pathr_error_event", ["occurred_at"])
    op.execute("alter table pathr_error_event enable row level security")
    op.execute("revoke all on pathr_error_event from anon, authenticated")

    op.create_table(
        "pathr_scan_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("ran_on", sa.Date(), nullable=False, unique=True),
        sa.Column("summary", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.execute("alter table pathr_scan_run enable row level security")
    op.execute("revoke all on pathr_scan_run from anon, authenticated")


def downgrade() -> None:
    op.drop_table("pathr_scan_run")
    op.drop_index("ix_pathr_error_event_occurred_at", table_name="pathr_error_event")
    op.drop_table("pathr_error_event")
