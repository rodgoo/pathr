"""Vários usuários: nome de usuário, amizades, limites e permissões fechadas.

Revision ID: 0020_social
Revises: 0019_job_radius
Create Date: 2026-09-13

## Nome de usuário

`pathr_user.username`, único sem distinção de caixa (índice em
`lower(username)`). As contas que já existem ganham um derivado do nome aqui
mesmo, pela mesma regra do cadastro (services/usernames.py) — a coluna só
vira NOT NULL depois de todas preenchidas.

## Amizade

Uma linha por par, com quem pediu e quem recebeu. O índice único em
(menor id, maior id) impede que A convide B enquanto B convida A: sem ele, os
dois convites cruzados virariam duas amizades pela metade.

`pathr_profile.discoverable` deixa a pessoa fora das sugestões. Ligado por
padrão — é uma rede de estudo, e sugerir é o propósito —, mas desligável.

## Permissões

O backend fala com o banco pela chave de serviço, que ignora RLS. Os papéis
públicos do Supabase (`anon`, `authenticated`) não são usados por nada do
PathR, e mesmo assim tinham SELECT, INSERT, UPDATE, DELETE e TRUNCATE em todas
as tabelas. A RLS sem política já barrava as linhas — mas não o TRUNCATE, que
a RLS não alcança. Revogar tudo fecha a porta que não servia a ninguém.
"""

import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_social"
down_revision: Union[str, None] = "0019_job_radius"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _candidatos(nome: str) -> list[str]:
    """Cópia congelada da regra de services/usernames.py.

    Migração não importa código do app: se a regra mudar amanhã, esta
    migração precisa continuar gerando o mesmo resultado de hoje.
    """
    conectivos = {"da", "das", "de", "di", "do", "dos", "du", "e", "y"}
    agnomes = {"filho", "neto", "junior", "jr", "sobrinho", "segundo", "terceiro"}
    ascii_ = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    palavras = re.findall(r"[a-z0-9]+", ascii_.lower())
    partes = [p for p in palavras if p not in conectivos] or palavras or ["estudante"]
    if len(partes) > 2 and len("".join(partes)) > 24:
        familia = [p for p in partes[1:] if p not in agnomes] or partes[1:]
        partes = [partes[0], familia[-1]]
    if not partes[0][0].isalpha():
        partes[0] = "u" + partes[0]
    junto = "".join(partes)[:24].rstrip("_")
    separado = "_".join(partes)[:24].rstrip("_")
    saida = [junto]
    if len(partes) > 1:
        saida.append(separado)
    saida.append(junto[:23] + "_")
    for n in range(2, 500):
        s = str(n)
        saida.append(junto[: 24 - len(s)] + s)
    reservados = {"admin", "api", "app", "pathr", "root", "suporte", "support", "sistema", "staff"}
    return [c for c in dict.fromkeys(saida) if len(c) >= 3 and c.strip("_") not in reservados]


def upgrade() -> None:
    conexao = op.get_bind()

    # --- nome de usuário -----------------------------------------------------
    op.add_column("pathr_user", sa.Column("username", sa.String(), nullable=True))
    tomados: set[str] = set()
    for user_id, nome in conexao.execute(
        sa.text("select id, name from pathr_user order by created_at")
    ).fetchall():
        escolhido = next(c for c in _candidatos(nome or "") if c not in tomados)
        tomados.add(escolhido)
        conexao.execute(
            sa.text("update pathr_user set username = :u where id = :id"),
            {"u": escolhido, "id": user_id},
        )
    op.alter_column("pathr_user", "username", nullable=False)
    op.create_index(
        "uq_pathr_user_username_lower",
        "pathr_user",
        [sa.text("lower(username)")],
        unique=True,
    )

    op.add_column(
        "pathr_profile",
        sa.Column("discoverable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # --- amizade -------------------------------------------------------------
    op.create_table(
        "pathr_friendship",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("addressee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), nullable=False),
        # pending | accepted. Recusar apaga a linha: guardar a recusa diria
        # a quem convidou, numa nova tentativa, que foi recusado.
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("requester_id <> addressee_id", name="ck_pathr_friendship_not_self"),
        sa.CheckConstraint("status in ('pending','accepted')", name="ck_pathr_friendship_status"),
    )
    op.create_index(
        "uq_pathr_friendship_pair",
        "pathr_friendship",
        [sa.text("least(requester_id, addressee_id)"), sa.text("greatest(requester_id, addressee_id)")],
        unique=True,
    )
    op.create_index("ix_pathr_friendship_requester", "pathr_friendship", ["requester_id"])
    op.create_index("ix_pathr_friendship_addressee", "pathr_friendship", ["addressee_id"])

    # --- limites -------------------------------------------------------------
    op.create_table(
        "pathr_rate_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_pathr_rate_event_lookup", "pathr_rate_event", ["action", "key", "created_at"])

    for tabela in ("pathr_friendship", "pathr_rate_event"):
        op.execute(f"alter table {tabela} enable row level security")

    # --- permissões ----------------------------------------------------------
    op.execute("revoke all on all tables in schema public from anon, authenticated")
    op.execute("revoke all on all sequences in schema public from anon, authenticated")
    # E para o que for criado depois: sem isto, a próxima tabela nasceria de
    # novo com tudo liberado para os papéis públicos.
    op.execute(
        "alter default privileges in schema public revoke all on tables from anon, authenticated"
    )
    op.execute(
        "alter default privileges in schema public revoke all on sequences from anon, authenticated"
    )


def downgrade() -> None:
    op.drop_index("ix_pathr_rate_event_lookup", table_name="pathr_rate_event")
    op.drop_table("pathr_rate_event")
    op.drop_index("ix_pathr_friendship_addressee", table_name="pathr_friendship")
    op.drop_index("ix_pathr_friendship_requester", table_name="pathr_friendship")
    op.drop_index("uq_pathr_friendship_pair", table_name="pathr_friendship")
    op.drop_table("pathr_friendship")
    op.drop_column("pathr_profile", "discoverable")
    op.drop_index("uq_pathr_user_username_lower", table_name="pathr_user")
    op.drop_column("pathr_user", "username")
    # As permissões revogadas não voltam: devolvê-las reabriria o TRUNCATE que
    # esta migração existe para fechar.
