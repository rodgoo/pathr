"""Foto de perfil.

Revision ID: 0008_user_avatar
Revises: 0007_multi_language
Create Date: 2026-09-09

A tela de perfil sempre desenhou um quadrado com as iniciais da pessoa, e nao
havia nada por tras dele: nem coluna, nem rota, nem bucket. Quem tentava
trocar a foto nao estava topando com um defeito -- estava topando com um
recurso que nunca existiu.

Guarda o CAMINHO no bucket, e nao uma URL. O bucket e privado e a imagem sai
pela rota GET /profile/avatar, do mesmo jeito que o curriculo: uma URL publica
aqui deixaria a foto de qualquer pessoa legivel por quem tivesse o endereco, e
enviar uma foto de perfil nao e o mesmo que decidir publica-la.

Nulo significa "sem foto", e e o estado de toda linha que ja existe -- por
isso a coluna entra sem default. As iniciais continuam sendo o que aparece
nesse caso, agora como escolha e nao como unica opcao.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_user_avatar"
down_revision: Union[str, None] = "0007_multi_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pathr_user", sa.Column("avatar_path", sa.String(length=400), nullable=True))


def downgrade() -> None:
    # Só a referência some. O arquivo continua no bucket: apagar imagem de
    # usuário num downgrade de schema tornaria a migration destrutiva de um
    # jeito que não dá para desfazer, e o custo de um arquivo órfão é menor
    # que o de uma foto perdida.
    op.drop_column("pathr_user", "avatar_path")
