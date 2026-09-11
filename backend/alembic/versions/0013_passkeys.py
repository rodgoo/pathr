"""Chave de acesso: as credenciais WebAuthn e os desafios de uso unico.

Revision ID: 0013_passkeys
Revises: 0012_weekly_checklist
Create Date: 2026-09-11

`pathr_passkey` guarda so o lado PUBLICO de cada chave. A privada nunca sai do
aparelho -- e o que torna a chave de acesso imune a vazamento de banco: roubar
esta tabela nao da acesso a conta nenhuma.

`pathr_webauthn_challenge` guarda o desafio de cada cerimonia no servidor,
com uso unico e cinco minutos de validade. A alternativa sem estado (assinar o
desafio e devolve-lo ao cliente) deixaria a mesma resposta ser reapresentada
dentro da validade, e chave sincronizada nao tem contador que denuncie isso.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_passkeys"
down_revision: Union[str, None] = "0012_weekly_checklist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_passkey",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.String(), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("transports", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("name", sa.String(), nullable=False,
                  server_default=sa.text("'Chave de acesso'")),
        sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_passkey_user_id", "pathr_passkey", ["user_id"])
    op.create_index("ix_pathr_passkey_credential_id", "pathr_passkey", ["credential_id"],
                    unique=True)

    op.create_table(
        "pathr_webauthn_challenge",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("challenge", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("pathr_webauthn_challenge")
    op.drop_index("ix_pathr_passkey_credential_id", table_name="pathr_passkey")
    op.drop_index("ix_pathr_passkey_user_id", table_name="pathr_passkey")
    op.drop_table("pathr_passkey")
