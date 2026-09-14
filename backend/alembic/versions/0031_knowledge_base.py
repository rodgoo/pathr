"""A base de conhecimento da conta, e as conversas do "Perguntar".

Revision ID: 0031_knowledge_base
Revises: 0030_activity_exercise
Create Date: 2026-09-13

Regra do produto: nada se perde. Toda dúvida, pergunta errada, lacuna de
correção e palavra consultada é sinal de que a pessoa não sabe ou não entendeu
algo — e precisa voltar em algum momento. Esses sinais nasciam espalhados
(fila de revisão do quiz, pontos de melhora do idioma, vocabulário) ou nem
nasciam (dúvidas). Agora todos entram também num lugar só:

- `pathr_knowledge_item`: um tema por conta, com de onde veio, a tecnologia,
  o módulo, quantas vezes apareceu e se ainda está pendente. É daqui que a
  Trilha atual tira assunto para atividades, quizzes e busca de material.
- `pathr_doubt_thread` / `pathr_doubt_message`: as conversas do "Perguntar"
  (dúvida rápida — ali não se gera exercício), com o contexto em que a dúvida
  surgiu e se a pessoa disse que entendeu.

RLS ligado já na criação.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0031_knowledge_base"
down_revision: Union[str, None] = "0030_activity_exercise"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid(nome: str, alvo: str, ondelete: str, nullable: bool = True) -> sa.Column:
    return sa.Column(nome, PGUUID(as_uuid=True), sa.ForeignKey(alvo, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "pathr_knowledge_item",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("user_id", "pathr_user.id", "CASCADE", nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("concept", sa.Text(), nullable=False),
        sa.Column("concept_key", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        _uuid("tag_id", "pathr_tag.id", "SET NULL"),
        _uuid("node_id", "pathr_roadmap_node.id", "SET NULL"),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pendente"),
        sa.Column("times_seen", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_knowledge_item_user_key", "pathr_knowledge_item", ["user_id", "concept_key"])
    op.create_index("ix_pathr_knowledge_item_user_status", "pathr_knowledge_item", ["user_id", "status", "last_seen_at"])
    op.create_index("ix_pathr_knowledge_item_user_tag", "pathr_knowledge_item", ["user_id", "tag_id"])

    op.create_table(
        "pathr_doubt_thread",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("user_id", "pathr_user.id", "CASCADE", nullable=False),
        sa.Column("context_kind", sa.String(length=20), nullable=False, server_default="geral"),
        sa.Column("context_ref", sa.String(length=64), nullable=True),
        sa.Column("context_title", sa.Text(), nullable=True),
        # O trecho que a pessoa estava vendo ao perguntar (o passo do exemplo,
        # a linha do código): as perguntas seguintes da conversa precisam dele.
        sa.Column("context_excerpt", sa.Text(), nullable=True),
        _uuid("node_id", "pathr_roadmap_node.id", "SET NULL"),
        _uuid("tag_id", "pathr_tag.id", "SET NULL"),
        sa.Column("concept", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="aberta"),
        sa.Column("understood", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pathr_doubt_thread_user_context", "pathr_doubt_thread", ["user_id", "context_kind", "context_ref"])

    op.create_table(
        "pathr_doubt_message",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("thread_id", "pathr_doubt_thread.id", "CASCADE", nullable=False),
        _uuid("user_id", "pathr_user.id", "CASCADE", nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pathr_doubt_message_thread", "pathr_doubt_message", ["thread_id", "created_at"])

    for tabela in ("pathr_knowledge_item", "pathr_doubt_thread", "pathr_doubt_message"):
        op.execute(f"alter table {tabela} enable row level security")


def downgrade() -> None:
    op.drop_index("ix_pathr_doubt_message_thread", table_name="pathr_doubt_message")
    op.drop_table("pathr_doubt_message")
    op.drop_index("ix_pathr_doubt_thread_user_context", table_name="pathr_doubt_thread")
    op.drop_table("pathr_doubt_thread")
    op.drop_index("ix_pathr_knowledge_item_user_tag", table_name="pathr_knowledge_item")
    op.drop_index("ix_pathr_knowledge_item_user_status", table_name="pathr_knowledge_item")
    op.drop_index("ix_pathr_knowledge_item_user_key", table_name="pathr_knowledge_item")
    op.drop_table("pathr_knowledge_item")
