"""Atividades práticas em sequência: uma respondida, outra gerada.

Revision ID: 0030_activity_exercise
Revises: 0029_rls_everywhere
Create Date: 2026-09-13

A aba Atividade tinha UMA tarefa por módulo, tirada do objetivo — respondida
ela, não havia mais nada para fazer ali. Agora cada módulo tem uma fila:
`pathr_activity_exercise` guarda cada enunciado gerado, e quando a pessoa
responde (a correção grava `answered_at`, a nota e a explicação corrigida) o
próximo é gerado já sabendo o que veio antes e onde ela errou.

O enunciado mora no BANCO e a correção lê de lá: quem manda a resposta não
escolhe contra qual tarefa ela é corrigida.

RLS ligado já na criação — a 0029 só alcança as tabelas que existiam.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision: str = "0030_activity_exercise"
down_revision: Union[str, None] = "0029_rls_everywhere"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_activity_exercise",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", PGUUID(as_uuid=True), sa.ForeignKey("pathr_roadmap_node.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="pratica"),
        sa.Column("hints", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("generated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column(
            "explanation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_explanation.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_pathr_activity_exercise_user_node",
        "pathr_activity_exercise",
        ["user_id", "node_id", "created_at"],
    )
    op.execute("alter table pathr_activity_exercise enable row level security")


def downgrade() -> None:
    op.drop_index("ix_pathr_activity_exercise_user_node", table_name="pathr_activity_exercise")
    op.drop_table("pathr_activity_exercise")
