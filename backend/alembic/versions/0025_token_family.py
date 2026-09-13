"""Família de refresh tokens: reuso suspeito derruba só aquele login.

Revision ID: 0025_token_family
Revises: 0024_cifra
Create Date: 2026-09-13

Até aqui, reusar um token já rotacionado revogava TODAS as sessões da conta.
Em 13/09 isso desconectou um computador porque um celular (outro login) ainda
guardava um cookie antigo da mesma conta. `family_id` identifica o login de
origem; a revogação por reuso passa a valer só para ele.

O preenchimento segue as cadeias existentes pelo `rotated_from`: quem já está
logado herda a família do seu login e não cai por causa desta migração.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_token_family"
down_revision: Union[str, None] = "0024_cifra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_refresh_token", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        with recursive cadeia as (
            select id, id as familia
              from pathr_refresh_token
             where rotated_from is null
            union all
            select t.id, c.familia
              from pathr_refresh_token t
              join cadeia c on t.rotated_from = c.id
        )
        update pathr_refresh_token t
           set family_id = c.familia
          from cadeia c
         where t.id = c.id
        """
    )
    # O que sobrou (cadeia cujo início já foi apagado) vira família de si mesmo.
    op.execute("update pathr_refresh_token set family_id = id where family_id is null")
    op.create_index("ix_pathr_refresh_token_family_id", "pathr_refresh_token", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_refresh_token_family_id", table_name="pathr_refresh_token")
    op.drop_column("pathr_refresh_token", "family_id")
