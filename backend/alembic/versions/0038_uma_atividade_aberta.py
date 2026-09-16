"""Uma única atividade ABERTA por módulo — fecha a corrida de check-then-act.

Revision ID: 0038_uma_atividade_aberta
Revises: 0037_device_id
Create Date: 2026-09-16

Dois cliques (ou duas abas) chegavam juntos, os dois viam "nenhuma atividade
aberta" e os dois geravam uma — duas atividades abertas no mesmo módulo. O
índice parcial único garante que o banco recuse a segunda; o código trata a
recusa devolvendo a que venceu.

Antes de criar o índice, mantém só a atividade aberta mais nova por
(user_id, node_id): as duplicadas são enunciados gerados ainda não respondidos,
sem trabalho da pessoa a perder.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0038_uma_atividade_aberta"
down_revision: Union[str, None] = "0037_device_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        delete from pathr_activity_exercise a
        using pathr_activity_exercise b
        where a.answered_at is null
          and b.answered_at is null
          and a.user_id = b.user_id
          and a.node_id = b.node_id
          and (a.created_at < b.created_at
               or (a.created_at = b.created_at and a.id < b.id))
        """
    )
    op.execute(
        "create unique index ux_pathr_activity_open "
        "on pathr_activity_exercise (user_id, node_id) where answered_at is null"
    )


def downgrade() -> None:
    op.execute("drop index if exists ux_pathr_activity_open")
