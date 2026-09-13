"""Cidades do Brasil para o campo de região das Configurações.

A pessoa digita "Vit" e escolhe "Vitória - ES": o que se grava é o nome como
o IBGE escreve, e é esse nome que as vagas conseguem localizar depois.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from supabase import Client

from app.database import get_supabase
from app.deps import client_ip, get_current_user
from app.services import geo, limites

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/cidades")
def sugerir_cidades(
    q: str = Query(default="", max_length=80),
    _usuario: dict = Depends(get_current_user),
):
    return [cidade.para_tela() for cidade in geo.sugerir(q)]


# O cadastro sugere a cidade antes de existir conta. A lista de municípios é
# pública (IBGE), então não há o que proteger no conteúdo — o limite por IP só
# evita que a rota vire um serviço grátis de autocomplete para terceiros.
CIDADES_POR_IP = limites.Regra(
    "cidades-publico", 120, timedelta(minutes=10), "Muitas buscas de cidade. Aguarde um instante."
)


@router.get("/cidades/publico")
def sugerir_cidades_no_cadastro(
    request: Request,
    q: str = Query(default="", max_length=80),
    supabase: Client = Depends(get_supabase),
):
    """As mesmas sugestões de `/geo/cidades`, sem sessão, para o cadastro."""
    if len(geo.normaliza(q)) < 2:
        return []
    limites.consumir(supabase, CIDADES_POR_IP, client_ip(request))
    return [cidade.para_tela() for cidade in geo.sugerir(q)]
