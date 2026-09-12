"""Sugestoes de tecnologia guardadas no perfil.

O que aprender a seguir sai de uma chamada de IA sobre o objetivo da pessoa.
Sem guardar, abrir a aba de competencias pagaria essa chamada toda vez -- e a
resposta nao muda de um minuto para o outro, porque o objetivo nao muda.

`tech_suggestions_at` e o que permite refazer quando o objetivo mudar, e nao
so quando o prazo vencer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_tech_suggestions"
down_revision: Union[str, None] = "0015_walkthrough"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_profile",
        sa.Column("tech_suggestions", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "pathr_profile",
        sa.Column("tech_suggestions_at", sa.DateTime(timezone=True), nullable=True),
    )
    # O objetivo que gerou a lista. Sem isto, trocar "quero ser fullstack Java"
    # por "quero ser SRE" continuaria mostrando as sugestoes do plano antigo
    # ate o prazo vencer.
    op.add_column(
        "pathr_profile",
        sa.Column("tech_suggestions_for", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pathr_profile", "tech_suggestions_for")
    op.drop_column("pathr_profile", "tech_suggestions_at")
    op.drop_column("pathr_profile", "tech_suggestions")
