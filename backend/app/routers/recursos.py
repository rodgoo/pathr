"""Feature flags: o que a tela do usuário lê e o que o admin liga/desliga.

- `GET /features` — para QUALQUER usuário logado: o mapa `{chave: ligado}` do
  próprio usuário. É por ele que a barra lateral decide mostrar a aba
  Candidaturas ou não. Nunca devolve o estado cru nem a regra.
- `GET /admin/recursos` e `PUT /admin/recursos/{chave}` — só super admin: a
  lista completa com rótulo/descrição/estado e a troca do estado (todos | admin
  | ninguem). O acesso é decidido AQUI, no servidor; a tela só decide se mostra
  a aba de admin.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from app.database import get_supabase
from app.deps import get_current_user
from app.routers.admin import exigir_super_admin
from app.services import features

router = APIRouter(tags=["recursos"])


@router.get("/features")
def meus_recursos(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict[str, bool]:
    """`{chave: ligado}` para o usuário atual."""
    return features.habilitadas_para(current_user, supabase)


@router.get("/admin/recursos")
def listar_recursos(
    _admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> list[dict]:
    """O catálogo inteiro, com o estado de cada flag. Só super admin."""
    return features.catalogo_para_admin(supabase)


class TrocaDeEstado(BaseModel):
    state: str


@router.put("/admin/recursos/{chave}")
def definir_estado(
    chave: str,
    corpo: TrocaDeEstado,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Liga o recurso para todos, só admin, ou ninguém. Só super admin."""
    if not features.existe(chave):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")
    if corpo.state not in features.ESTADOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Estado inválido. Use 'todos', 'admin' ou 'ninguem'.",
        )
    # Upsert: uma linha por flag alterado. `key` é a chave primária, então o
    # mesmo flag mexido duas vezes atualiza em vez de duplicar.
    supabase.table("pathr_feature_flag").upsert(
        {"key": chave, "state": corpo.state, "updated_by": str(admin["id"])},
        on_conflict="key",
    ).execute()
    return {"key": chave, "state": corpo.state}
