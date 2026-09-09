"""Checagem de saúde — prontidão de SCHEMA, não só "o processo respondeu".

Existe por causa de uma janela concreta de deploy: o container novo sobe com
código que já usa uma coluna nova, mas o banco (ou o cache de schema do
PostgREST) ainda está no schema antigo. Nesse intervalo toda rota que toca a
coluna responde 500, e o app parece quebrado sem estar.

Por isso `/health` só devolve 200 quando as tabelas centrais deste app estão
visíveis pelo PostgREST. A Fly (ver backend/fly.toml) usa esta rota como
`healthCheckPath`: enquanto ela não passar, ele segura o deploy em vez de
promover uma versão que responderia 500.

O que este check NÃO faz, de propósito: comparar a revisão do Alembic. O
`start.sh` roda `alembic upgrade head` ANTES do uvicorn, e uma migration que
falha derruba o boot — se o processo chegou aqui, a migration passou. Duplicar
essa verificação só criaria um segundo lugar para dar falso negativo, e um
health check que falha por engano faz o orquestrador reiniciar um serviço
saudável.
"""

import logging
from typing import Any

from fastapi import APIRouter, Response, status

from app.config import settings

logger = logging.getLogger("pathr.health")

router = APIRouter(tags=["operação"])

# Uma amostra, não a lista inteira das 28 tabelas: se estas quatro estão
# visíveis, a migration rodou e o PostgREST recarregou o schema. Consultar
# todas seria 28 idas ao banco por checagem, várias vezes por minuto.
_CORE_TABLES = ("pathr_user", "pathr_tag", "pathr_roadmap", "pathr_resume")


@router.get("/health")
def health(response: Response) -> dict[str, Any]:
    """200 quando o app pode atender de verdade; 503 enquanto não pode."""
    checks: dict[str, Any] = {"schema": _schema_ready()}
    healthy = all(check["ok"] for check in checks.values())

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "environment": settings.environment,
        "checks": checks,
    }


def _schema_ready() -> dict[str, Any]:
    """As tabelas centrais respondem pelo PostgREST?

    `limit(0)`: interessa se a tabela EXISTE e está no cache do schema, não o
    conteúdo. Trazer linha seria custo sem informação a mais.
    """
    try:
        from app.database import get_supabase

        supabase = get_supabase()
        for table in _CORE_TABLES:
            supabase.table(table).select("*").limit(0).execute()
    except Exception as exc:  # noqa: BLE001 — a mensagem é o resultado do check
        logger.warning("health: schema indisponível (%s)", exc.__class__.__name__)
        return {
            "ok": False,
            # Sem o texto do erro: ele pode carregar a URL do projeto Supabase,
            # e /health é público.
            "detail": f"tabelas do PathR indisponíveis ({exc.__class__.__name__})",
        }
    return {"ok": True, "tables": len(_CORE_TABLES)}
