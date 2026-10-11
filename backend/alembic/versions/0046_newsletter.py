"""Newsletter do admin: temas, dias de envio e histórico das edições.

Revision ID: 0046_newsletter
Revises: 0045_parent_id_fk
Create Date: 2026-10-10

`pathr_newsletter_config` é UMA linha por admin: os temas que ele acompanha, em
quais dias e a que horas (no fuso dele) a edição chega, e as duas marcas que
impedem repetição — `last_sent_on` (a edição do dia já saiu) e
`last_attempt_at` (a busca já rodou há pouco e não achou nada: sem ela, um dia
sem notícia nova refaria a busca, e gastaria a cota, a cada hora).

`pathr_newsletter_issue` guarda o que saiu: os itens ficam em `items` (jsonb)
porque é deles que se tira a lista de links já enviados — a mesma notícia não
volta na edição seguinte.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0046_newsletter"
down_revision: Union[str, None] = "0045_parent_id_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_newsletter_config",
        sa.Column(
            "user_id", PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        # Tecnologias (Python, Rust…). O que se quer saber sobre elas vai em
        # `angles`; a busca é o produto das duas listas.
        sa.Column("topics", JSONB(), nullable=False, server_default="[]"),
        # noticias | novidades | trabalhos | polemicas — acumulam.
        sa.Column("angles", JSONB(), nullable=False, server_default='["noticias"]'),
        # diaria | dias_uteis | fim_de_semana | semanal | mensal | personalizada
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="semanal"),
        # 0 = segunda … 6 = domingo. Vale para "semanal" e "personalizada".
        sa.Column("weekdays", JSONB(), nullable=False, server_default="[0]"),
        # 1..28: o dia 29-31 não existe em todo mês, e a edição pularia meses.
        sa.Column("month_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("send_hour", sa.Integer(), nullable=False, server_default="8"),
                # Itens por busca (tecnologia × ângulo), não por tecnologia.
        sa.Column("items_per_topic", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("last_sent_on", sa.Date(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("alter table pathr_newsletter_config enable row level security")
    op.execute("revoke all on pathr_newsletter_config from anon, authenticated")

    op.create_table(
        "pathr_newsletter_issue",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id", PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        # agendada | manual
        sa.Column("kind", sa.String(length=12), nullable=False, server_default="agendada"),
        sa.Column("items", JSONB(), nullable=False, server_default="[]"),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_newsletter_issue_user", "pathr_newsletter_issue", ["user_id", "created_at"])
    op.execute("alter table pathr_newsletter_issue enable row level security")
    op.execute("revoke all on pathr_newsletter_issue from anon, authenticated")


def downgrade() -> None:
    op.drop_index("ix_pathr_newsletter_issue_user", table_name="pathr_newsletter_issue")
    op.drop_table("pathr_newsletter_issue")
    op.drop_table("pathr_newsletter_config")
