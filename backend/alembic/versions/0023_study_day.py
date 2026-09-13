"""Os dias em que cada pessoa estudou, para a sequência em dupla dos amigos.

Revision ID: 0023_study_day
Revises: 0022_scan
Create Date: 2026-09-13

A sequência de dois amigos são os dias seguidos em que OS DOIS estudaram. A
fonte é `pathr_activity`, mas ela tem uma linha por ação — cinco quizzes num
dia são cinco linhas —, e contar dias ali para cada amigo seria ler centenas
de linhas por pessoa, esbarrando no limite de linhas do PostgREST.

`pathr_study_day` guarda uma linha por pessoa e dia, e quem a preenche é um
TRIGGER em `pathr_activity`, não o código: há mais de um lugar que grava
atividade (services/progress.py, resumes, plan…), e uma segunda escrita no
código seria a que alguém esquece no próximo lugar. O histórico que já existe
entra no upgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_study_day"
down_revision: Union[str, None] = "0022_scan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathr_study_day",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pathr_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
    )
    op.execute("alter table pathr_study_day enable row level security")
    op.execute("revoke all on pathr_study_day from anon, authenticated")

    op.execute(
        """
        create or replace function pathr_marca_dia_de_estudo() returns trigger
        language plpgsql as $$
        begin
            insert into pathr_study_day (user_id, day)
            values (new.user_id, new.activity_date)
            on conflict do nothing;
            return new;
        end;
        $$
        """
    )
    op.execute(
        """
        create trigger pathr_activity_marca_dia
        after insert on pathr_activity
        for each row execute function pathr_marca_dia_de_estudo()
        """
    )
    op.execute(
        """
        insert into pathr_study_day (user_id, day)
        select distinct user_id, activity_date from pathr_activity
        where activity_date is not null
        on conflict do nothing
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists pathr_activity_marca_dia on pathr_activity")
    op.execute("drop function if exists pathr_marca_dia_de_estudo()")
    op.drop_table("pathr_study_day")
