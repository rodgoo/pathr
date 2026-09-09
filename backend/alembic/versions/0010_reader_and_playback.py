"""Modo leitura e posicao de reproducao.

Revision ID: 0010_reader_and_playback
Revises: 0009_activity_draft_and_resume
Create Date: 2026-09-09

O material abria em OUTRA aba: para ver o video ou ler o artigo a pessoa saia
do PathR, e o progresso so existia se ela voltasse e marcasse a mao. Agora o
conteudo abre dentro do site, e o progresso e medido enquanto ela consome.

## O cache do modo leitura, em pathr_resource

O artigo extraido fica na linha do RECURSO, e nao na do usuario: a tabela e
compartilhada (a url e unica), entao uma busca serve todo mundo que abrir o
mesmo material. Sem isso, cada leitor bateria de novo no site de origem para
receber exatamente o mesmo texto.

`reader_status` separa tres desfechos que a tela trata de forma diferente:
ok (mostra), failed (mostra o motivo e o link original) e pending (nunca
buscado). `reader_fetched_at` da a validade: artigo e corrigido e atualizado,
e um cache eterno mostraria para sempre a primeira versao vista.

## A posicao, em pathr_user_resource

`position_seconds` e do video, e e numero porque o player devolve segundos e
retomar exige o segundo exato. Convive com `position_note`, que e texto livre
e continua servindo ao que a pessoa escreve a mao.

`progress_pct` ja existia na tabela e nenhuma tela escrevia nele. Passa a ser
escrito pelos dois caminhos: a fracao assistida do video e a fracao rolada do
artigo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_reader_and_playback"
down_revision: Union[str, None] = "0009_activity_draft_and_resume"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_resource", sa.Column("reader_html", sa.Text(), nullable=True))
    op.add_column("pathr_resource", sa.Column("reader_words", sa.Integer(), nullable=True))
    op.add_column(
        "pathr_resource",
        sa.Column("reader_status", sa.String(length=16), nullable=False, server_default="pending"),
    )
    op.add_column("pathr_resource", sa.Column("reader_error", sa.String(length=300), nullable=True))
    op.add_column(
        "pathr_resource", sa.Column("reader_fetched_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column(
        "pathr_user_resource", sa.Column("position_seconds", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pathr_user_resource", "position_seconds")
    op.drop_column("pathr_resource", "reader_fetched_at")
    op.drop_column("pathr_resource", "reader_error")
    op.drop_column("pathr_resource", "reader_status")
    op.drop_column("pathr_resource", "reader_words")
    op.drop_column("pathr_resource", "reader_html")
