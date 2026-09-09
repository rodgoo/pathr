"""Data de nascimento e residência no perfil.

Perguntados no cadastro. Ficam em pathr_profile, não em pathr_user: não
autenticam nada e são dado pessoal, como o resto daquela tabela.

`country` nasce NOT NULL com default 'BR' no servidor — as linhas que já
existem recebem 'BR' na própria migration, sem passo extra. Os outros três
são nulos porque as contas criadas antes desta mudança nunca responderam a
essas perguntas, e inventar valor para elas seria pior do que admitir que
não sabemos.

Revision ID: 0003_birth_residence
Revises: 0002_defaults
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_birth_residence"
down_revision: Union[str, None] = "0002_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_profile", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("pathr_profile", sa.Column("city", sa.String(), nullable=True))
    op.add_column("pathr_profile", sa.Column("state", sa.String(), nullable=True))
    op.add_column(
        "pathr_profile",
        sa.Column("country", sa.String(), nullable=False, server_default=sa.text("'BR'")),
    )


def downgrade() -> None:
    op.drop_column("pathr_profile", "country")
    op.drop_column("pathr_profile", "state")
    op.drop_column("pathr_profile", "city")
    op.drop_column("pathr_profile", "birth_date")
