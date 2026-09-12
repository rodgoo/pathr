"""Treino diario de idioma, topico por item e pontos de melhora por idioma.

Revision ID: 0017_language_practice
Revises: 0016_tech_suggestions
Create Date: 2026-09-12

O que cada coluna nova resolve:

pathr_english_item
  language      A resposta precisa saber de que idioma e sem passar pelo
                nivelamento: item de treino nao tem assessment. E o que deixa
                calcular o nivel por habilidade de UM idioma numa consulta so.
  topic         O placar por topico ("preposicoes: 3 de 5") nao existia porque
                o item nao guardava o topico.
  session_id    O treino do dia a que o item pertence.
  payload       O que a tela mostra de cada formato (pecas embaralhadas, pares,
                emoji). O gabarito continua em `correct`, que nunca vai ao
                navegador.
  origin        revisao | reforco | novo | nivelamento -- para o resumo do dia
                dizer quanto foi revisao do que se errou.
  review_item_id O ponto de melhora que este item cobra de novo, para o acerto
                ou erro reagendar AQUELE ponto.
  skipped       Fala sem microfone nao e erro, e nao pode entrar no nivel.

pathr_review_item
  language, skill, topic, band
                A lista de pontos de melhora misturava todos os idiomas, e o
                ponto nao sabia a que habilidade pertencia -- entao nao havia
                como devolve-lo no formato certo. O preenchimento de `language`
                com "en" vale para o que ja existia: conferido em producao, todo
                nivelamento feito ate aqui era de ingles.

pathr_english_session
  practice_day  Um treino por idioma por dia. O indice unico parcial e o que
                impede duas abas abertas de gerarem dois treinos no mesmo dia.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_language_practice"
down_revision: Union[str, None] = "0016_tech_suggestions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_english_item", sa.Column("language", sa.String(), nullable=True))
    op.add_column("pathr_english_item", sa.Column("topic", sa.String(), nullable=True))
    op.add_column(
        "pathr_english_item",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pathr_english_session.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "pathr_english_item",
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column("pathr_english_item", sa.Column("origin", sa.String(), nullable=True))
    op.add_column(
        "pathr_english_item",
        sa.Column(
            "review_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pathr_review_item.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "pathr_english_item",
        sa.Column("skipped", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_pathr_english_item_session_id", "pathr_english_item", ["session_id"])
    op.create_index(
        "ix_pathr_english_item_user_language",
        "pathr_english_item",
        ["user_id", "language", "answered_at"],
    )
    # A mesma posicao do treino nao pode ser gerada duas vezes: o lote em
    # segundo plano e a geracao de reserva podem correr ao mesmo tempo.
    op.create_index(
        "uq_pathr_english_item_session_order",
        "pathr_english_item",
        ["session_id", "order_index"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )
    op.execute(
        """
        UPDATE pathr_english_item AS i
           SET language = a.language
          FROM pathr_english_assessment AS a
         WHERE i.assessment_id = a.id AND i.language IS NULL
        """
    )
    op.execute(
        "UPDATE pathr_english_item SET origin = 'nivelamento' "
        "WHERE assessment_id IS NOT NULL AND origin IS NULL"
    )

    for coluna in ("language", "skill", "topic", "band"):
        op.add_column("pathr_review_item", sa.Column(coluna, sa.String(), nullable=True))
    op.execute(
        "UPDATE pathr_review_item SET language = 'en' "
        "WHERE kind = 'language' AND language IS NULL"
    )

    op.add_column("pathr_english_session", sa.Column("practice_day", sa.Date(), nullable=True))
    op.create_index(
        "uq_pathr_english_session_practice_day",
        "pathr_english_session",
        ["user_id", "language", "practice_day"],
        unique=True,
        postgresql_where=sa.text("mode = 'treino'"),
    )


def downgrade() -> None:
    op.drop_index("uq_pathr_english_session_practice_day", table_name="pathr_english_session")
    op.drop_column("pathr_english_session", "practice_day")
    for coluna in ("band", "topic", "skill", "language"):
        op.drop_column("pathr_review_item", coluna)
    op.drop_index("uq_pathr_english_item_session_order", table_name="pathr_english_item")
    op.drop_index("ix_pathr_english_item_user_language", table_name="pathr_english_item")
    op.drop_index("ix_pathr_english_item_session_id", table_name="pathr_english_item")
    for coluna in ("skipped", "review_item_id", "origin", "payload", "session_id", "topic", "language"):
        op.drop_column("pathr_english_item", coluna)
