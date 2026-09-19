"""Apaga os eventos que o pipeline antigo adivinhou.

Revision ID: 0043_limpa_eventos_adivinhados
Revises: 0042_evento_com_imagem
Create Date: 2026-09-19

O pipeline anterior gravava a data de HOJE quando não achava data no trecho da
busca, e a cidade BUSCADA quando a IA não sabia dizer onde era. O resultado está
no banco: eventos anunciados para o dia errado e eventos de outra cidade
marcados como se fossem aqui. O código novo não reescreve o que já foi gravado,
então esses registros ficariam na tela para sempre.

## Como se reconhece um registro do pipeline antigo

`image_url IS NULL`. O pipeline novo sempre grava alguma imagem — o cartaz da
página ou, na falta dele, o ícone do site. Um evento sem imagem nenhuma só pode
ter vindo de antes desta leva.

## O que NÃO é apagado

Evento em que alguém já clicou "Eu vou!". A data pode estar errada, mas a
decisão de ir é da pessoa e o registro é dela — apagar isso para consertar um
campo nosso seria cobrar dela o nosso erro. Esses poucos ficam, e a varredura
os atualiza pelo `source_url` quando reencontrá-los.

`pathr_news_scan` é esvaziada para que toda região seja varrida de novo na
primeira abertura, já com as regras novas.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0043_limpa_eventos_adivinhados"
down_revision: Union[str, None] = "0042_evento_com_imagem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        delete from pathr_news_event e
         where e.image_url is null
           and not exists (
                 select 1 from pathr_news_attendance a where a.event_id = e.id
           )
        """
    )
    op.execute("delete from pathr_news_scan")


def downgrade() -> None:
    # Não há volta: o que foi apagado era dado adivinhado, e recriá-lo seria
    # recriar o defeito. A varredura repõe o que for real.
    pass
