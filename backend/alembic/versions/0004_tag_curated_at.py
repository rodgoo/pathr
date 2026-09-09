"""Carência de curadoria por tag.

Revision ID: 0004_tag_curated_at
Revises: 0003_birth_residence
Create Date: 2026-09-09

A busca de material é cara em cota, não em dinheiro: `search.list` da YouTube
Data API custa 100 das 10.000 unidades diárias, o que dá ~100 buscas por DIA
para o app inteiro — todos os usuários somados. Sem registrar quando uma tag
foi buscada pela última vez, dois usuários abrindo o mesmo módulo de "Docker"
gastariam duas buscas pelo mesmo resultado, e a cota acabaria antes do meio-dia.

Por que uma coluna em `pathr_tag` e não uma tabela nova: o dado é um carimbo
por tag, sem histórico e sem relação própria. Uma tabela de junção com uma
única coluna útil seria um JOIN a mais em toda curadoria para guardar o que
cabe aqui.

Nulo significa "nunca curada", e é esse o estado de todas as 91 tags do seed —
por isso a coluna entra sem default. Um default de `now()` marcaria todo o
catálogo como recém-curado e a primeira busca só aconteceria depois da
carência, com a biblioteca vazia esse tempo todo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_tag_curated_at"
down_revision: Union[str, None] = "0003_birth_residence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_tag",
        sa.Column("curated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # A curadoria varre "tags que precisam de material" ordenando por este
    # campo, com NULL primeiro. Sem índice isso é seq scan no catálogo inteiro
    # a cada chamada.
    op.create_index("ix_pathr_tag_curated_at", "pathr_tag", ["curated_at"])


def downgrade() -> None:
    op.drop_index("ix_pathr_tag_curated_at", table_name="pathr_tag")
    op.drop_column("pathr_tag", "curated_at")
