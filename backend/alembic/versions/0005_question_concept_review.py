"""Reciclagem de erro: conceito da questão e o elo com o item de revisão.

Revision ID: 0005_concept_review
Revises: 0004_tag_curated_at
Create Date: 2026-09-09

`pathr_review_item` existe desde a 0001 com os campos do SM-2 completos, mas
nada nunca escreveu nela: errar uma questão não deixava rastro, e a mesma
lacuna podia se repetir por meses sem o sistema notar. Estas duas colunas são
o que faltava para fechar o ciclo.

`concept` responde "o que esta questão testa", em uma frase. Ele existe porque
agrupar por enunciado não funciona AQUI: a reciclagem reescreve o enunciado de
propósito, então duas perguntas sobre a mesma ideia não se parecem em nada
como texto. Sem um campo próprio, cada reformulação viraria um item de revisão
novo e a pessoa responderia a mesma lacuna cinco vezes em paralelo.

`review_item_id` é o caminho de volta: liga a questão reciclada ao item que a
gerou. Sem ele o acerto de hoje não teria como aposentar o erro de ontem, e o
item ficaria vencendo para sempre.

Ambas anuláveis: as questões que já existem no banco foram geradas antes disso
e não têm conceito nem origem. Elas continuam válidas para responder — só não
alimentam a revisão, o que é o correto para uma pergunta que ninguém sabe o
que testava.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_concept_review"
down_revision: Union[str, None] = "0004_tag_curated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_question", sa.Column("concept", sa.String(), nullable=True))
    op.add_column(
        "pathr_question",
        sa.Column("review_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # A correção percorre as questões da tentativa procurando quais reciclavam
    # algum item. Sem índice isso varre a tabela inteira a cada quiz enviado.
    op.create_index(
        "ix_pathr_question_review_item_id", "pathr_question", ["review_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_pathr_question_review_item_id", table_name="pathr_question")
    op.drop_column("pathr_question", "review_item_id")
    op.drop_column("pathr_question", "concept")
