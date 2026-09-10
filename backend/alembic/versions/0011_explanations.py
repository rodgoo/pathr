"""Feynman: a explicacao da pessoa e a lacuna que ela revela.

Revision ID: 0011_explanations
Revises: 0010_reader_and_playback
Create Date: 2026-09-10

O app tinha tres dos quatro pilares. Quiz e recordacao ativa, o SM-2 e
repeticao espacada, e a reciclagem de erro liga os dois. Faltava o Feynman --
explicar com as proprias palavras -- que e o unico que flagra a ilusao de
competencia: ler sobre closures e achar que entendeu. Quiz nao pega isso,
porque reconhecer a alternativa certa entre quatro e mais facil que produzir a
explicacao do zero.

Historico, e nao upsert como pathr_activity_draft: explicar o mesmo conceito de
novo semanas depois e comparar as duas versoes E o metodo. Sobrescrever
apagaria a evidencia de que a pessoa evoluiu.

`gaps` e o campo que faz isto valer mais que uma nota. Cada lacuna vira um item
em pathr_review_item vencendo hoje, e volta como questao reescrita no proximo
quiz da trilha -- e ai os quatro pilares deixam de ser quatro recursos soltos e
viram um ciclo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_explanations"
down_revision: Union[str, None] = "0010_reader_and_playback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_explanation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("concept", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.String(), nullable=True),
        sa.Column("gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("tag_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("graded_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_pathr_explanation_user_id", "pathr_explanation", ["user_id"])
    op.create_index("ix_pathr_explanation_node_id", "pathr_explanation", ["node_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_explanation_node_id", table_name="pathr_explanation")
    op.drop_index("ix_pathr_explanation_user_id", table_name="pathr_explanation")
    op.drop_table("pathr_explanation")
