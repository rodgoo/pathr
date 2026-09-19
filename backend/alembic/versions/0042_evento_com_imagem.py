"""A imagem do evento e o registro de que a região já foi varrida.

Revision ID: 0042_evento_com_imagem
Revises: 0040_noticias
Create Date: 2026-09-19

Duas coisas que faltavam para a aba de Notícias parar de girar:

- `image_url`: a foto que a própria página do evento publica (`og:image` ou o
  `image` do JSON-LD). Sem ela o card é só texto, e o cartaz é metade do que
  faz alguém querer ir.

- `pathr_news_scan`: a marca de "esta região já foi varrida, e quando". Antes,
  o único sinal era a existência de eventos gravados — então região onde a
  busca não achava nada era varrida DE NOVO a cada abertura da tela, sem parar,
  gastando busca e IA a cada vez. É o "Buscando eventos…" que não terminava.

A marca é gravada ANTES da varredura, e não depois: se a varredura falhar no
meio, a próxima abertura precisa encontrar a região como "já tentada há pouco"
e mostrar o que houver, em vez de recomeçar tudo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0042_evento_com_imagem"
down_revision: Union[str, None] = "0040_noticias"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_news_event", sa.Column("image_url", sa.Text(), nullable=True))

    op.create_table(
        "pathr_news_scan",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Quantos eventos entraram na última varredura — é o que distingue
        # "ninguém buscou ainda" de "buscamos e não havia nada".
        sa.Column("found", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint("uq_pathr_news_scan_regiao", "pathr_news_scan", ["city", "state"])
    op.execute("alter table pathr_news_scan enable row level security")
    op.execute("revoke all on pathr_news_scan from anon, authenticated")


def downgrade() -> None:
    op.drop_constraint("uq_pathr_news_scan_regiao", "pathr_news_scan", type_="unique")
    op.drop_table("pathr_news_scan")
    op.drop_column("pathr_news_event", "image_url")
