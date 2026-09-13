"""Relatos: reclamações e sugestões enviadas pelas pessoas, com foto opcional.

Revision ID: 0021_report
Revises: 0020_social
Create Date: 2026-09-13

A foto NÃO é uma URL. Guardar um endereço enviado pelo cliente e mostrá-lo na
tela da moderação é o caminho clássico de XSS na sessão de quem modera — a
conta com mais poder no app. O arquivo sobe pela API, tem a assinatura dos
bytes conferida e vai para um bucket privado; esta tabela guarda só o caminho
interno, que o cliente nunca escolhe.

`page` é o nome da tela de onde a pessoa relatou, como texto. Nunca vira link.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_report"
down_revision: Union[str, None] = "0020_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_report",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page", sa.String(), nullable=True),
        sa.Column("attachment_path", sa.String(), nullable=True),
        sa.Column("attachment_type", sa.String(), nullable=True),
        # aberto | em_analise | resolvido
        sa.Column("status", sa.String(), nullable=False, server_default="aberto"),
        sa.Column("moderator_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind in ('reclamacao','sugestao')", name="ck_pathr_report_kind"),
        sa.CheckConstraint("status in ('aberto','em_analise','resolvido')", name="ck_pathr_report_status"),
    )
    op.create_index("ix_pathr_report_user_id", "pathr_report", ["user_id"])
    op.create_index("ix_pathr_report_status_created", "pathr_report", ["status", "created_at"])
    op.execute("alter table pathr_report enable row level security")
    op.execute("revoke all on pathr_report from anon, authenticated")


def downgrade() -> None:
    op.drop_index("ix_pathr_report_status_created", table_name="pathr_report")
    op.drop_index("ix_pathr_report_user_id", table_name="pathr_report")
    op.drop_table("pathr_report")
