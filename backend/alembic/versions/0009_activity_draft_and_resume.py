"""Rascunho da atividade no servidor, e onde parei em cada material.

Revision ID: 0009_activity_draft_and_resume
Revises: 0008_user_avatar
Create Date: 2026-09-09

Duas coisas que o app pedia para a pessoa fazer e depois nao guardava direito.

1. `pathr_activity_draft`

   A solucao escrita na atividade pratica morava no `localStorage`, e o
   proprio componente dizia por que: nao havia endpoint para onde mandar. O
   efeito e que o texto ficava preso a UM navegador -- e escrever a solucao do
   zero e o trabalho mais caro de perder ao trocar de maquina.

   Uma linha por (usuario, modulo), com unicidade no par. O que importa e o
   texto atual, nao o historico de cada tecla, entao a escrita e um upsert e
   nao um insert que acumula.

2. `pathr_user_resource.position_note`

   O progresso do material ja era do servidor, mas so em tres estados (salvo,
   em curso, concluido). Dava para dizer que comecou um video de 40 minutos e
   nao dava para dizer onde parou -- entao "continuar vendo" virava "procurar
   de novo". `progress_pct` ja existia na tabela e nenhuma tela escrevia nele.

   `position_note` e texto livre de proposito: "23:10", "capitulo 4", "secao
   sobre indices". Um campo numerico de segundos so serviria a video, e daria
   errado no artigo e no PDF, que sao metade da biblioteca. Quem marca e a
   pessoa, porque o material abre em outra aba e o app nao tem como observar
   um player que nao e dele.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0009_activity_draft_and_resume"
down_revision: Union[str, None] = "0008_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_activity_draft",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("pathr_roadmap_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Um rascunho por modulo por pessoa. E a restricao que faz o upsert ser
    # possivel: sem ela, salvar duas vezes criaria duas linhas e a leitura
    # teria que escolher uma delas por criterio inventado.
    op.create_unique_constraint(
        "uq_pathr_activity_draft_user_node", "pathr_activity_draft", ["user_id", "node_id"]
    )
    op.create_index("ix_pathr_activity_draft_user_id", "pathr_activity_draft", ["user_id"])

    op.add_column(
        "pathr_user_resource", sa.Column("position_note", sa.String(length=200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pathr_user_resource", "position_note")
    op.drop_index("ix_pathr_activity_draft_user_id", table_name="pathr_activity_draft")
    op.drop_constraint(
        "uq_pathr_activity_draft_user_node", "pathr_activity_draft", type_="unique"
    )
    op.drop_table("pathr_activity_draft")
