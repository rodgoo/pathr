"""O aviso de amizade: quando cada pessoa já viu o convite ou o aceite.

Revision ID: 0026_friend_notices
Revises: 0025_token_family
Create Date: 2026-09-13

O pop-up "X te mandou um convite" (e "X aceitou seu convite") aparece uma vez
por pessoa, em qualquer aparelho. Guardar no navegador faria o mesmo aviso
reaparecer no celular depois de visto no computador — por isso a marca fica
no banco, na própria linha da amizade:

- `invite_seen_at`: quem RECEBEU o convite já viu o aviso dele;
- `accept_seen_at`: quem ENVIOU já viu o aviso de que foi aceito.

O que já existia antes desta migração nasce visto: sem isso, a primeira tela
depois do deploy despejaria um pop-up para cada amizade antiga.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_friend_notices"
down_revision: Union[str, None] = "0025_token_family"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_friendship", sa.Column("invite_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pathr_friendship", sa.Column("accept_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("update pathr_friendship set invite_seen_at = now(), accept_seen_at = now()")


def downgrade() -> None:
    op.drop_column("pathr_friendship", "accept_seen_at")
    op.drop_column("pathr_friendship", "invite_seen_at")
