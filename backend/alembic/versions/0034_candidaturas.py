"""A fila diária de candidaturas: as vagas do dia e o que foi feito com cada uma.

Revision ID: 0034_candidaturas
Revises: 0033_walkthrough_files
Create Date: 2026-09-15

Todo dia o app separa as vagas que mais combinam com a pessoa (o mesmo
ranqueamento da tela de Vagas, sem IA) e guarda aqui. Cada linha é uma
candidatura em algum estado:

- `sugerida`: entrou na fila de hoje, ainda não fez nada;
- `enviada`: o currículo foi enviado por e-mail pelo app, ou a pessoa abriu a
  vaga e marcou como enviada;
- `descartada`: não interessou.

Por que guardar no banco, e não só listar na hora: é o que impede sugerir a
mesma vaga amanhã, é o histórico do que já foi enviado (que ninguém consegue
manter de cabeça depois de vinte candidaturas), e é o que deixa a seleção
rodar 24/7 no servidor — o agendador de hora em hora escreve aqui, e a tela só
lê.

A carta de apresentação fica CIFRADA: ela mistura currículo com objetivo de
carreira, o mesmo tipo de dado que já é cifrado em `pathr_resume`.

RLS ligado já na criação.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0034_candidaturas"
down_revision: Union[str, None] = "0033_walkthrough_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_application",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # O dia da fila, no fuso da pessoa: é por ele que a tela mostra "hoje".
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        # O trecho do anúncio guardado na seleção: é o que a carta usa depois,
        # e a vaga pode ter saído do ar (ou do cache das fontes) até lá.
        sa.Column("snippet", sa.Text(), nullable=True),
        # Escrita sob medida, e só quando a pessoa vai enviar: gerar para vaga
        # que ela nem vai abrir seria pagar IA à toa.
        sa.Column("letter", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("to_email", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="sugerida"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_application_user_day", "pathr_application", ["user_id", "day"])
    op.create_index("ix_pathr_application_user_status", "pathr_application", ["user_id", "status"])
    # A mesma vaga não volta à fila: a chave é a pessoa e o endereço do anúncio.
    op.create_unique_constraint("uq_pathr_application_user_url", "pathr_application", ["user_id", "url"])
    op.execute("alter table pathr_application enable row level security")


def downgrade() -> None:
    op.drop_constraint("uq_pathr_application_user_url", "pathr_application", type_="unique")
    op.drop_index("ix_pathr_application_user_status", table_name="pathr_application")
    op.drop_index("ix_pathr_application_user_day", table_name="pathr_application")
    op.drop_table("pathr_application")
