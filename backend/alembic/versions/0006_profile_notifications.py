"""Preferencias de e-mail no perfil.

Revision ID: 0006_notifications
Revises: 0005_concept_review
Create Date: 2026-09-09

A aba "Avisos e privacidade" existia no desenho e nao tinha onde gravar: o
perfil nao guardava nenhuma preferencia de e-mail, entao os cinco interruptores
da tela nao tinham destino.

JSONB e nao cinco colunas booleanas porque a lista de avisos acompanha o
produto. Cada aviso novo custaria uma migration mais um deploy coordenado com
o frontend, e a alternativa -- criar as cinco colunas de uma vez -- ja nasceria
errada no dia em que o sexto aviso aparecesse.

Default '{}' e nao a lista com todos ligados: quem nunca abriu a aba nao
declarou preferencia nenhuma, e o padrao de cada aviso mora no codigo
(routers/profile.py, AVISOS), onde pode mudar sem tocar em linha de banco.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_notifications"
down_revision: Union[str, None] = "0005_concept_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_profile",
        sa.Column(
            "notifications",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("pathr_profile", "notifications")
