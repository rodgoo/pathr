"""O estado das integrações externas, para a aba de Configurações.

A regra mora em services/status_apis.py. Só para SUPER ADMIN, e não qualquer
sessão: o relatório não traz chave nenhuma, mas diz quais serviços o app usa,
se têm chave configurada e como estão — informação operacional da infra, não
de uso pessoal, e não é para qualquer conta ver (mesmo padrão de
routers/recursos.py para as feature flags).
"""

from fastapi import APIRouter, Depends

from app.routers.admin import exigir_super_admin
from app.services import status_apis

router = APIRouter(prefix="/status", tags=["operação"])


@router.get("/apis")
async def status_das_apis(atualizar: bool = False, _admin: dict = Depends(exigir_super_admin)):
    """`atualizar=true` refaz as checagens, no máximo uma vez por minuto."""
    return await status_apis.relatorio(atualizar=atualizar)
