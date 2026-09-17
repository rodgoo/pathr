"""Notícias: eventos de tecnologia perto da pessoa, e quem confirmou presença.

Revision ID: 0040_noticias
Revises: 0039_banco_de_respostas
Create Date: 2026-09-16

`pathr_news_event` guarda o que a busca (Tavily/Brave, com a IA completando o
que faltar) encontrou sobre um evento: quando é, se é gratuito, e o prazo de
inscrição — quando o texto de origem não diz, os dois campos de inscrição
ficam `null` e a TELA é quem decide a frase ("Datas de inscrição ainda não
foram definidas"), não o banco. `source_url` é único: é a chave que evita
gravar o mesmo evento de novo a cada busca do dia.

`pathr_news_attendance` é o "Eu vou!": uma linha por pessoa por evento.
`pathr_profile.show_attendance` é a privacidade disso — se a presença aparece
no cartão que outras contas veem (mesmo padrão de `discoverable`, ver
social.py), ligado por padrão porque é o que faz sentido para quem quer
combinar de ir junto.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0040_noticias"
down_revision: Union[str, None] = "0039_banco_de_respostas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_news_event",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("venue", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("event_start", sa.Date(), nullable=False),
        sa.Column("event_end", sa.Date(), nullable=True),
        # null = não foi possível determinar se é gratuito ou pago.
        sa.Column("is_free", sa.Boolean(), nullable=True),
        sa.Column("price_info", sa.Text(), nullable=True),
        sa.Column("registration_start", sa.Date(), nullable=True),
        sa.Column("registration_end", sa.Date(), nullable=True),
        sa.Column("ticket_url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="busca"),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_pathr_news_event_source_url", "pathr_news_event", ["source_url"])
    op.create_index("ix_pathr_news_event_regiao", "pathr_news_event", ["state", "city", "event_start"])
    op.execute("alter table pathr_news_event enable row level security")
    op.execute("revoke all on pathr_news_event from anon, authenticated")

    op.create_table(
        "pathr_news_attendance",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id", PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "event_id", PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_news_event.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_pathr_news_attendance_pessoa_evento", "pathr_news_attendance", ["user_id", "event_id"]
    )
    op.execute("alter table pathr_news_attendance enable row level security")
    op.execute("revoke all on pathr_news_attendance from anon, authenticated")

    op.add_column(
        "pathr_profile",
        sa.Column("show_attendance", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("pathr_profile", "show_attendance")
    op.drop_table("pathr_news_attendance")
    op.drop_index("ix_pathr_news_event_regiao", table_name="pathr_news_event")
    op.drop_constraint("uq_pathr_news_event_source_url", "pathr_news_event", type_="unique")
    op.drop_table("pathr_news_event")
