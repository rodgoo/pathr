"""Exemplos de código para depurar, pedidos ou sugeridos no "Perguntar".

Revision ID: 0032_doubt_examples
Revises: 0031_knowledge_base
Create Date: 2026-09-14

A pessoa pede um exemplo ("me mostra em código") ou o tutor sugere um. O
exemplo é gerado pelo mesmo gerador do Laboratório (código + passo a passo
conferido) e fica ligado à fala que o trouxe:

- `suggestions`: os exemplos que o tutor sugeriu naquela resposta
  ([{linguagem, topico}]), para a tela oferecer o botão "Gerar exemplo";
- `walkthrough_id`: o exemplo gerado, para a tela abrir no depurador.
  SET NULL: apagar o exemplo no Laboratório não apaga a conversa.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision: str = "0032_doubt_examples"
down_revision: Union[str, None] = "0031_knowledge_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_doubt_message",
        sa.Column("suggestions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "pathr_doubt_message",
        sa.Column(
            "walkthrough_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_walkthrough.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("pathr_doubt_message", "walkthrough_id")
    op.drop_column("pathr_doubt_message", "suggestions")
