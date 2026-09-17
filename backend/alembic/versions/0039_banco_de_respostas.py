"""O banco de respostas da candidatura, e o passo a passo de cada envio.

Revision ID: 0039_banco_de_respostas
Revises: 0038_uma_atividade_aberta
Create Date: 2026-09-16

Todo formulário de vaga pergunta as mesmas coisas com nomes diferentes: "Nome
completo", "Nome", "Full name"; "Currículo", "CV", "Resume"; "Endereço",
"Logradouro". Respondida uma vez, a resposta vale para todas as próximas — é
disso que trata `pathr_answer_bank`:

- `question_key` é a pergunta NORMALIZADA (services/perguntas.py): as variações
  acima caem todas na mesma chave, e é a chave que torna a resposta
  reutilizável entre sites diferentes;
- `question` guarda como a pergunta apareceu da última vez, para a tela mostrar
  em palavras humanas;
- `answer` é cifrada: são dados pessoais (endereço, telefone, pretensão).

Em `pathr_application`:

- `steps`: o passo a passo do envio ([{passo, situacao, detalhe, em}]), que é o
  que a tela mostra acontecendo — e o que explica depois por que uma
  candidatura parou no meio;
- `pending`: as perguntas que faltaram. O app não inventa resposta em nome de
  ninguém: o que ele não sabe vira campo na tela, a pessoa responde uma vez, e
  a resposta entra no banco acima.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision: str = "0039_banco_de_respostas"
down_revision: Union[str, None] = "0038_uma_atividade_aberta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_answer_bank",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(length=80), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        # De onde veio: "pessoa" (digitou), "perfil", "curriculo".
        sa.Column("source", sa.String(length=20), nullable=False, server_default="pessoa"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_pathr_answer_bank_pergunta", "pathr_answer_bank", ["user_id", "question_key"]
    )
    op.execute("alter table pathr_answer_bank enable row level security")

    op.add_column(
        "pathr_application",
        sa.Column("steps", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "pathr_application",
        sa.Column("pending", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("pathr_application", "pending")
    op.drop_column("pathr_application", "steps")
    op.drop_constraint("uq_pathr_answer_bank_pergunta", "pathr_answer_bank", type_="unique")
    op.drop_table("pathr_answer_bank")
