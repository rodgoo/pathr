"""Cidades do Brasil para o campo de região das Configurações.

A pessoa digita "Vit" e escolhe "Vitória - ES": o que se grava é o nome como
o IBGE escreve, e é esse nome que as vagas conseguem localizar depois.
"""

from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user
from app.services import geo

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/cidades")
def sugerir_cidades(
    q: str = Query(default="", max_length=80),
    _usuario: dict = Depends(get_current_user),
):
    return [cidade.para_tela() for cidade in geo.sugerir(q)]
