"""Identidade do aparelho na sessão: o mesmo navegador reusa a linha na lista.

Revision ID: 0037_device_id
Revises: 0036_feature_flag
Create Date: 2026-09-16

`device_id` vem do cookie `pathr_device`, que sobrevive a logout/login. Com
ele, entrar de novo no mesmo navegador encerra a sessão anterior daquele
aparelho em vez de criar mais um item em "aparelhos conectados". Sessões
antigas ficam com `device_id` NULL e continuam agrupando pela família do login.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_device_id"
down_revision: Union[str, None] = "0036_feature_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_refresh_token", sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_pathr_refresh_token_device_id", "pathr_refresh_token", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_pathr_refresh_token_device_id", table_name="pathr_refresh_token")
    op.drop_column("pathr_refresh_token", "device_id")
