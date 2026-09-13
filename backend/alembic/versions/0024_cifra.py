"""A data de nascimento passa a ser guardada cifrada.

Revision ID: 0024_cifra
Revises: 0023_study_day
Create Date: 2026-09-13

Texto cifrado (AES-256-GCM, services/cifra.py) não cabe numa coluna `date`,
então ela vira `text`. As datas que já existem viram "AAAA-MM-DD" em claro
neste passo — a leitura aceita as duas formas — e o script
`scripts/cifrar_dados_existentes.py` as cifra logo depois do deploy.

Nenhuma consulta filtra ou ordena por `birth_date` no banco: a idade é
conferida no servidor, sobre a data em claro, antes de gravar.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0024_cifra"
down_revision: Union[str, None] = "0023_study_day"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("alter table pathr_profile alter column birth_date type text using birth_date::text")


def downgrade() -> None:
    # Só funciona antes de cifrar: texto cifrado não vira data. Rodar o
    # downgrade depois do script falha de propósito, em vez de apagar as datas.
    op.execute("alter table pathr_profile alter column birth_date type date using birth_date::date")
