"""O rascunho do quiz no servidor: onde a pessoa parou, e o que já respondeu.

Revision ID: 0044_quiz_rascunho
Revises: 0043_limpa_eventos_adivinhados
Create Date: 2026-09-26

O quiz gerado e as respostas ainda não enviadas viviam só no `localStorage` do navegador. Limpar os dados do
site, abrir numa aba anônima, trocar de aparelho ou qualquer falha da tela faziam a pessoa voltar ao botão
"começar quiz" — e a IA reescrevia perguntas que já tinha escrito.

`draft` guarda {index, answers: {question_id: alternativa}, updated_at}. É nulo antes da primeira resposta e volta
a ser nulo quando a tentativa é enviada. Uma coluna nula e sem default: nenhuma linha existente muda, e o servidor
continua funcionando antes desta migração rodar (o rascunho é melhor esforço e simplesmente não é gravado).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0044_quiz_rascunho"
down_revision: Union[str, None] = "0043_limpa_eventos_adivinhados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_quiz", sa.Column("draft", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("pathr_quiz", "draft")
