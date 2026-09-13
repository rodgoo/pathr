"""Raio das vagas presenciais e híbridas.

Revision ID: 0019_job_radius
Revises: 0018_user_course
Create Date: 2026-09-13

A cidade e a UF já estão no perfil desde o cadastro. Falta a distância que a
pessoa aceita ir: vaga presencial a 600 km não é sugestão para quem não pode
se mudar. Nulo é "não escolheu" — vale o padrão do código (50 km); 0 é "só
remotas".
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_job_radius"
down_revision: Union[str, None] = "0018_user_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_profile", sa.Column("job_radius_km", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("pathr_profile", "job_radius_km")
