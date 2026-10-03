"""Chave estrangeira em pathr_tag.parent_id e pathr_roadmap_node.parent_id.

Revision ID: 0045_parent_id_fk
Revises: 0044_quiz_rascunho
Create Date: 2026-10-03

As duas colunas sempre foram um auto-relacionamento (tag-pai, fase-pai), mas
nasceram sem `ForeignKey` nem na 0001 nem em nenhuma migration depois — um
`parent_id` apontando para um id que nunca existiu, ou que foi apagado sem
`ON DELETE`, nunca dava erro. `app/models.py` já foi corrigido para declarar
as duas FKs (`ondelete="SET NULL"`, a mesma semântica que o código já
pressupõe: apagar a tag-pai solta as filhas da árvore, não as apaga). Esta
migration leva o mesmo contrato para o banco.

Conferido em produção antes de escrever esta migration: nenhuma linha de
`pathr_tag` ou `pathr_roadmap_node` tem `parent_id` órfão (apontando para um
id que não existe), então `ADD CONSTRAINT` não falha.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0045_parent_id_fk"
down_revision: Union[str, None] = "0044_quiz_rascunho"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_pathr_tag_parent_id",
        "pathr_tag",
        "pathr_tag",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pathr_roadmap_node_parent_id",
        "pathr_roadmap_node",
        "pathr_roadmap_node",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_pathr_roadmap_node_parent_id", "pathr_roadmap_node", type_="foreignkey")
    op.drop_constraint("fk_pathr_tag_parent_id", "pathr_tag", type_="foreignkey")
