"""Idiomas no plural, e a prova que cada pessoa escolhe.

Revision ID: 0007_multi_language
Revises: 0006_notifications
Create Date: 2026-09-09

O modulo nasceu ingles-so: `pathr_english_profile` tinha `user_id` como chave
primaria, o que por construcao permite UM idioma por pessoa. Quem quisesse
estudar espanhol tambem nao tinha onde guardar o segundo nivel.

A chave passa a ser (user_id, language). E a mudanca estrutural: sem ela
nenhuma tela resolveria o problema, porque o banco so tem lugar para uma linha.

`exam` e `exam_target` sao a segunda parte do pedido. O app mede em CEFR por
dentro -- aplicar IELTS ou TOEFL de verdade exigiria banco de itens calibrado
por examinador, que nenhum LLM substitui -- e APRESENTA na regua que a pessoa
usa. Quem quer 7.0 no IELTS pensa em 7.0, nao em C1, e os dois sao o mesmo
ponto. A conversao mora em services/languages.py.

As tabelas mantem o nome `pathr_english_*`. Renomear quatro tabelas com dados
em producao, mais as chaves estrangeiras, por uma questao de nome seria risco
sem retorno num modulo que acabou de ganhar funcao. O nome fica devendo; o
comportamento, nao.

Toda coluna entra com default 'en': as linhas que existem foram criadas quando
so havia ingles, e e isso que elas sao.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_multi_language"
down_revision: Union[str, None] = "0006_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COM_IDIOMA = (
    "pathr_english_profile",
    "pathr_english_assessment",
    "pathr_english_session",
    "pathr_english_vocab",
)


def upgrade() -> None:
    for tabela in _COM_IDIOMA:
        op.add_column(
            tabela,
            sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
        )

    # A regua escolhida e a meta nela. Ficam so no perfil: a tentativa de
    # nivelamento guarda o resultado em CEFR, e converter na leitura evita um
    # historico que muda de significado quando a pessoa troca de exame.
    op.add_column(
        "pathr_english_profile",
        sa.Column("exam", sa.String(length=32), nullable=False, server_default="cefr"),
    )
    op.add_column(
        "pathr_english_profile", sa.Column("exam_target", sa.String(length=40), nullable=True)
    )

    # A troca de chave primaria. O nome da constraint vem do padrao do
    # PostgreSQL (<tabela>_pkey), que e como a 0001 a criou via create_all.
    op.drop_constraint("pathr_english_profile_pkey", "pathr_english_profile", type_="primary")
    op.create_primary_key(
        "pathr_english_profile_pkey", "pathr_english_profile", ["user_id", "language"]
    )

    # As consultas do modulo sempre filtram por idioma junto do usuario.
    op.create_index(
        "ix_pathr_english_vocab_user_language", "pathr_english_vocab", ["user_id", "language"]
    )
    op.create_index(
        "ix_pathr_english_assessment_user_language",
        "pathr_english_assessment",
        ["user_id", "language"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pathr_english_assessment_user_language", table_name="pathr_english_assessment"
    )
    op.drop_index("ix_pathr_english_vocab_user_language", table_name="pathr_english_vocab")
    op.drop_constraint("pathr_english_profile_pkey", "pathr_english_profile", type_="primary")
    # Volta a chave antiga: so sobrevive quem estava em ingles, porque um
    # segundo idioma colidiria na chave de um campo so.
    op.execute("DELETE FROM pathr_english_profile WHERE language <> 'en'")
    op.create_primary_key("pathr_english_profile_pkey", "pathr_english_profile", ["user_id"])
    op.drop_column("pathr_english_profile", "exam_target")
    op.drop_column("pathr_english_profile", "exam")
    for tabela in _COM_IDIOMA:
        op.drop_column(tabela, "language")
