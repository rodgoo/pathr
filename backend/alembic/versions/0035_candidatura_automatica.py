"""Envio automático e respostas prontas para o formulário da vaga.

Revision ID: 0035_candidatura_automatica
Revises: 0034_candidaturas
Create Date: 2026-09-16

Duas coisas que faltavam para a candidatura acontecer sem trabalho manual:

- `pathr_application.answers`: as respostas já escritas para as perguntas que
  o formulário da vaga costuma fazer (pretensão, disponibilidade, inglês, "conte
  uma experiência com X"), tiradas do currículo e do perfil. A vaga que só
  aceita candidatura pelo site continua sendo respondida pela PESSOA — o app
  entrega o texto pronto para colar, não preenche por ela.
- `pathr_profile.salary_expectation` e `availability`: as duas respostas que não
  estão no currículo e que toda vaga pergunta. Sem elas, a resposta pronta sairia
  com um espaço em branco justo no campo que decide a triagem.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0035_candidatura_automatica"
down_revision: Union[str, None] = "0034_candidaturas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathr_application",
        sa.Column("answers", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("pathr_profile", sa.Column("salary_expectation", sa.String(length=120), nullable=True))
    op.add_column("pathr_profile", sa.Column("availability", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("pathr_profile", "availability")
    op.drop_column("pathr_profile", "salary_expectation")
    op.drop_column("pathr_application", "answers")
