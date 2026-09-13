"""Cursos com certificado que a pessoa já possui.

Revision ID: 0018_user_course
Revises: 0017_language_practice
Create Date: 2026-09-13

`course_id` é texto e não FK: o catálogo de cursos mora no código
(services/courses.py), não no banco. Um curso que saia do catálogo deixa a
linha órfã, e a leitura a ignora — apagar o certificado que a pessoa marcou
só porque a lista de cursos mudou seria perder dado dela.

Uma linha por pessoa e curso: marcar duas vezes não duplica.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_user_course"
down_revision: Union[str, None] = "0017_language_practice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_user_course",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "course_id", name="uq_pathr_user_course"),
    )
    op.create_index("ix_pathr_user_course_user_id", "pathr_user_course", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_user_course_user_id", table_name="pathr_user_course")
    op.drop_table("pathr_user_course")
