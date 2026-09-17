"""A chave que liga a extensão do navegador à conta.

Revision ID: 0041_chave_da_extensao
Revises: 0039_banco_de_respostas

O número pula o 0040: ele ficou reservado para a leva de Notícias, escrita em
paralelo e ainda não publicada. Id de revisão é texto, não contagem — o que
importa é a cadeia, e esta se liga a 0039.
Create Date: 2026-09-16

A extensão roda em outra origem (chrome-extension://…) e o cookie de sessão não
vai para lá — de propósito: cookie que atravessa origem é justamente o que torna
CSRF possível. Então a extensão se identifica com uma chave própria, criada na
tela de Candidaturas e colada nela uma vez.

O que fica guardado é só o HASH da chave, como senha: quem ler a tabela não
consegue usar a chave, e a original aparece uma única vez, na hora de criar.

`last_used_at` existe para a tela poder dizer "usada há dois dias" — é assim que
a pessoa reconhece uma chave que não usa mais e revoga.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0041_chave_da_extensao"
down_revision: Union[str, None] = "0039_banco_de_respostas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_extension_token",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256 do segredo. A chave em si nunca é gravada.
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=80), nullable=False, server_default="Extensão"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_extension_token_user", "pathr_extension_token", ["user_id"])
    op.execute("alter table pathr_extension_token enable row level security")


def downgrade() -> None:
    op.drop_index("ix_pathr_extension_token_user", table_name="pathr_extension_token")
    op.drop_table("pathr_extension_token")
