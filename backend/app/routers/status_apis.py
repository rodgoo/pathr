"""O estado das integrações externas, para a aba de Configurações.

A regra mora em services/status_apis.py. A rota exige sessão: o relatório não
traz chave nenhuma, mas diz quais serviços o app usa e como estão, e isso não é
para quem nem entrou.
"""

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.services import status_apis

router = APIRouter(prefix="/status", tags=["operação"])


@router.get("/apis")
async def status_das_apis(atualizar: bool = False, _current_user: dict = Depends(get_current_user)):
    """`atualizar=true` refaz as checagens, no máximo uma vez por minuto."""
    return await status_apis.relatorio(atualizar=atualizar)
