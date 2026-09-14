"""Dependências de requisição: quem está chamando, e de onde.

A sessão vive em dois cookies: um access token JWT curto e um refresh token
opaco e longo. O access token carrega `sid` (o id da linha em
`pathr_refresh_token`), então uma sessão revogada para de valer no próximo
uso mesmo com o JWT ainda dentro da validade — sem isso, "sair de todos os
dispositivos" não faria nada por até `access_token_minutes`.

O header `Authorization: Bearer` é aceito em paralelo para clientes que não
guardam cookie (um app nativo, um script). O cookie continua sendo o caminho
do navegador, porque é o único que o JavaScript da página não consegue ler.
"""

import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.services.moderacao import CONTA_SUSPENSA, esta_banido
from app.security import decode_access_token

ACCESS_COOKIE = "pathr_access"
REFRESH_COOKIE = "pathr_refresh"


def client_ip(request: Optional[Request]) -> Optional[str]:
    """O IP real do chamador.

    **Na Fly, só `fly-client-ip` é confiável.** A API recebe o tráfego direto
    do proxy da Fly — sem Cloudflare e sem o Caddy que este código supunha à
    frente (verificado em 2026-09-13: `server: Fly`, sem `cf-ray`). O proxy da
    Fly sobrescreve `fly-client-ip` com o endereço TCP que ele observou; já
    `cf-connecting-ip` e o começo de `x-forwarded-for` chegam exatamente como
    o cliente mandou. Confiar neles deixava qualquer um escolher o próprio IP
    a cada requisição: o log de segurança registrava o endereço inventado, e
    qualquer limite por IP virava enfeite.

    Fora da Fly só em DESENVOLVIMENTO vale a ordem antiga. Em produção sem a
    Fly (um host novo, uma variável que sumiu) os cabeçalhos do cliente não
    valem nada: o endereço é o da conexão. Errar para o lado seguro custa só
    precisão no log; errar para o outro devolve a qualquer um o poder de
    escolher o próprio IP e passar por cima dos limites.
    """
    if request is None:
        return None
    if os.environ.get("FLY_APP_NAME"):
        fly = request.headers.get("fly-client-ip")
        if fly:
            return fly.strip()
        return request.client.host if request.client else None
    if settings.is_production:
        return request.client.host if request.client else None
    cloudflare = request.headers.get("cf-connecting-ip")
    if cloudflare:
        return cloudflare.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    raw = request.headers.get("user-agent")
    # A coluna é texto livre; truncar evita que um header absurdo entupa a
    # linha de auditoria.
    return raw[:400] if raw else None


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def _session_is_live(supabase: Client, session_id: str, user_id: Any = None) -> bool:
    """A sessão referenciada pelo JWT ainda vale — e é da pessoa do token?

    O dono é conferido aqui, e não só pela assinatura do JWT: se a chave de
    assinatura um dia vazar, forjar um token não pode bastar trocar o `sub`
    por outra conta e reaproveitar o id de uma sessão viva qualquer.

    Um erro de rede aqui devolve True: derrubar todo mundo porque o Supabase
    piscou é pior que aceitar por mais alguns minutos um JWT cuja sessão foi
    revogada — a revogação volta a valer assim que a consulta funcionar.
    """
    try:
        rows = (
            supabase.table("pathr_refresh_token")
            .select("id,user_id,revoked_at,expires_at")
            .eq("id", session_id)
            .limit(1)
            .execute()
            .data
        )
    except Exception:  # noqa: BLE001
        return True
    if not rows:
        return False
    row = rows[0]
    if user_id is not None and str(row.get("user_id")) != str(user_id):
        return False
    if row.get("revoked_at"):
        return False
    expires_at = row.get("expires_at")
    if expires_at:
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if parsed <= datetime.now(timezone.utc):
            return False
    return True


def _unauthorized(detail: str = "Sessão inválida ou expirada.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_user(
    request: Request, supabase: Client = Depends(get_supabase)
) -> dict[str, Any]:
    """O usuário autenticado, ou 401. E-mail não verificado é recusado aqui."""
    user = _resolve_user(request, supabase)
    if not user.get("email_verified_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirme seu e-mail para continuar.",
        )
    return user


def get_current_user_allow_unverified(
    request: Request, supabase: Client = Depends(get_supabase)
) -> dict[str, Any]:
    """Para as poucas rotas que a pessoa precisa alcançar antes de confirmar o
    e-mail: reenviar a confirmação, ver o próprio cadastro, sair."""
    return _resolve_user(request, supabase)


def _resolve_user(request: Request, supabase: Client) -> dict[str, Any]:
    # O id resolvido fica em `request.state` porque o middleware que avisa as
    # outras telas roda DEPOIS da rota, quando as dependências já saíram de
    # cena. É a única forma de ele saber de quem foi a escrita sem repetir a
    # verificação de sessão inteira.
    token = request.cookies.get(ACCESS_COOKIE) or _bearer_token(request)
    if not token:
        raise _unauthorized("Não autenticado.")

    payload = decode_access_token(token)
    if not payload:
        raise _unauthorized()

    session_id = payload.get("sid")
    if not session_id or not _session_is_live(supabase, session_id, payload.get("sub")):
        raise _unauthorized("Sessão encerrada. Entre novamente.")

    try:
        rows = (
            supabase.table("pathr_user")
            .select("*")
            .eq("id", payload.get("sub"))
            .limit(1)
            .execute()
            .data
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco indisponível agora. Tente de novo em instantes.",
        ) from exc

    if not rows:
        raise _unauthorized()

    user = rows[0]
    # Banida: fora de TODA rota, mesmo com um access token ainda válido. As
    # sessões já foram revogadas ao banir; isto cobre o intervalo até a
    # revogação ser lida, e qualquer sessão que tenha escapado dela.
    if esta_banido(user):
        raise _unauthorized(CONTA_SUSPENSA)
    user["session_id"] = session_id
    request.state.pathr_user_id = str(user["id"])
    return user
