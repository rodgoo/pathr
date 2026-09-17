"""Administração de contas: a lista de quem se cadastrou, e banir.

## Quem alcança

Só o super admin (`settings.super_admin_emails`), e não todo moderador:
moderar relatos é ler e responder; banir tira alguém do sistema. Para
qualquer outra conta estas rotas respondem 404 — nem confirmam que existem.

## Banir pede a chave de acesso, na hora

Uma sessão aberta não basta. Um cookie roubado, ou o computador deixado
desbloqueado, daria a quem estiver ali o poder de expulsar qualquer pessoa.
Por isso banir e desbanir exigem uma assinatura NOVA da chave de acesso do
próprio admin — o dedo no leitor ou o PIN do aparelho —, com um desafio de
uso único que só vale para esta cerimônia (`purpose = "moderacao"`) e só para
a conta dele. Sem chave cadastrada, não há como banir: a tela manda cadastrar.

## O que banir faz

- marca `banned_at`, o motivo e quem baniu;
- revoga TODAS as sessões da conta — o acesso cai no próximo pedido, não
  quando o token expirar;
- a partir daí `get_current_user` recusa a conta em qualquer rota, e
  `_issue_session` recusa emitir sessão nova (senha, chave ou renovação);
- a pessoa some da busca, das sugestões e das listas de amigos.

Nada é apagado: desbanir devolve a conta como estava.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from supabase import Client
from webauthn import generate_authentication_options, options_to_json, verify_authentication_response
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement

from app.config import settings
from app.database import get_supabase
from app.deps import get_current_user
from app.routers.auth import _log_event
from app.routers.passkeys import _consumir_desafio, _guardar_desafio
from app.services import cifra
from app.services import passkeys as chaves
from app.services.busca import limpar_para_filtro
from app.services.moderacao import e_super_admin

router = APIRouter(prefix="/admin", tags=["administração"])

_PROPOSITO = "moderacao"
_NAO_ENCONTRADO = "Não encontrado."
_LIMITE = 300


class Assinatura(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


class Banir(Assinatura):
    motivo: str = Field(min_length=3, max_length=500)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def exigir_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not e_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADO)
    return current_user


def _usuario(supabase: Client, user_id: str) -> dict[str, Any]:
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
    linhas = supabase.table("pathr_user").select("*").eq("id", user_id).limit(1).execute().data or []
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
    return linhas[0]


def _resumo(linha: dict[str, Any], admin_id: str) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "name": linha.get("name") or "",
        "username": linha.get("username") or "",
        "email": linha.get("email") or "",
        "has_avatar": bool(linha.get("avatar_path")),
        "created_at": linha.get("created_at"),
        "email_verified": bool(linha.get("email_verified_at")),
        "banned_at": linha.get("banned_at"),
        "banned_reason": linha.get("banned_reason"),
        "is_super_admin": e_super_admin(linha),
        "voce": str(linha["id"]) == admin_id,
    }


@router.get("/usuarios")
def listar_usuarios(
    busca: str = "",
    situacao: str = "todos",
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
):
    """As contas, das mais novas para as mais antigas, com busca por nome, @ ou e-mail."""
    consulta = supabase.table("pathr_user").select(
        "id,name,username,email,avatar_path,created_at,email_verified_at,banned_at,banned_reason"
    )
    termo = limpar_para_filtro(busca.strip().lstrip("@")[:100])
    if termo:
        consulta = consulta.or_(f"name.ilike.*{termo}*,username.ilike.*{termo}*,email.ilike.*{termo}*")
    linhas = consulta.order("created_at", desc=True).limit(_LIMITE).execute().data or []
    if situacao == "banidos":
        linhas = [linha for linha in linhas if linha.get("banned_at")]
    elif situacao == "ativos":
        linhas = [linha for linha in linhas if not linha.get("banned_at")]
    admin_id = str(admin["id"])
    return {"usuarios": [_resumo(linha, admin_id) for linha in linhas], "limite": _LIMITE}


@router.get("/usuarios/{user_id}/avatar")
def avatar_do_usuario(
    user_id: str,
    _admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
):
    alvo = _usuario(supabase, user_id)
    caminho = alvo.get("avatar_path")
    if not caminho:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.")
    try:
        dados = cifra.decifrar_bytes(
            supabase.storage.from_(settings.avatar_bucket).download(caminho),
            cifra.ctx_arquivo(settings.avatar_bucket, caminho),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil.") from exc
    extensao = str(caminho).rsplit(".", 1)[-1].lower()
    tipo = {"png": "image/png", "webp": "image/webp"}.get(extensao, "image/jpeg")
    return Response(content=dados, media_type=tipo, headers={"Cache-Control": "private, max-age=300"})


@router.post("/confirmacao")
def pedir_confirmacao(
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
):
    """O desafio que a chave de acesso do admin vai assinar.

    Só as chaves DELE entram em `allow_credentials`: o navegador nem oferece
    outra, e o servidor confere de novo na assinatura.
    """
    admin_id = str(admin["id"])
    minhas = (
        supabase.table("pathr_passkey").select("credential_id,transports")
        .eq("user_id", admin_id).execute().data or []
    )
    if not minhas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cadastre uma chave de acesso em Configurações › Conta para confirmar esta ação.",
        )
    opcoes = generate_authentication_options(
        rp_id=chaves.rp_id(),
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(linha["credential_id"]))
            for linha in minhas
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {
        "challenge_id": _guardar_desafio(supabase, _PROPOSITO, opcoes.challenge, admin_id),
        "options": json.loads(options_to_json(opcoes)),
    }


def _confirmar_chave(supabase: Client, admin: dict, assinatura: Assinatura, request: Request) -> None:
    """Confere a assinatura nova da chave do próprio admin. Levanta 403 se não servir."""
    admin_id = str(admin["id"])
    desafio = _consumir_desafio(supabase, assinatura.challenge_id, _PROPOSITO, admin_id)
    recusada = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="A chave de acesso não confirmou. Tente de novo.",
    )
    credential_id = str(assinatura.credential.get("id") or "")
    linhas = (
        supabase.table("pathr_passkey").select("*")
        .eq("credential_id", credential_id).eq("user_id", admin_id)
        .limit(1).execute().data or []
    ) if credential_id else []
    if not linhas:
        _log_event(supabase, "admin_confirm_fail", user_id=admin_id, request=request,
                   detail={"reason": "unknown_credential"})
        raise recusada
    chave = linhas[0]
    try:
        verificada = verify_authentication_response(
            credential=assinatura.credential,
            expected_challenge=desafio,
            expected_rp_id=chaves.rp_id(),
            expected_origin=chaves.origem(),
            credential_public_key=base64url_to_bytes(chave["public_key"]),
            credential_current_sign_count=int(chave.get("sign_count") or 0),
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001 — assinatura, origem ou contador
        _log_event(supabase, "admin_confirm_fail", user_id=admin_id, request=request,
                   detail={"reason": type(exc).__name__})
        raise recusada
    supabase.table("pathr_passkey").update(
        {"sign_count": int(verificada.new_sign_count), "last_used_at": _agora()}
    ).eq("id", str(chave["id"])).execute()


@router.post("/usuarios/{user_id}/banir")
def banir(
    user_id: str,
    payload: Banir,
    request: Request,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
):
    admin_id = str(admin["id"])
    # O alvo é conferido ANTES da chave: não faz sentido pedir o dedo no leitor
    # para uma ação que seria recusada de qualquer jeito.
    alvo = _usuario(supabase, user_id)
    if str(alvo["id"]) == admin_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode banir a própria conta.")
    if e_super_admin(alvo):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta conta é de administração e não pode ser banida.")

    _confirmar_chave(supabase, admin, payload, request)

    agora = _agora()
    motivo = payload.motivo.strip()[:500]
    supabase.table("pathr_user").update(
        {"banned_at": agora, "banned_reason": motivo, "banned_by": admin_id}
    ).eq("id", str(alvo["id"])).execute()
    # Todas as sessões caem já — senão a pessoa seguiria dentro até o token expirar.
    supabase.table("pathr_refresh_token").update({"revoked_at": agora}).eq(
        "user_id", str(alvo["id"])
    ).is_("revoked_at", "null").execute()
    _log_event(supabase, "user_banned", user_id=str(alvo["id"]), request=request, detail={"by": admin_id})
    _log_event(supabase, "admin_banned_user", user_id=admin_id, request=request, detail={"target": str(alvo["id"])})
    return _resumo({**alvo, "banned_at": agora, "banned_reason": motivo}, admin_id)


@router.post("/usuarios/{user_id}/desbanir")
def desbanir(
    user_id: str,
    payload: Assinatura,
    request: Request,
    admin: dict = Depends(exigir_super_admin),
    supabase: Client = Depends(get_supabase),
):
    admin_id = str(admin["id"])
    alvo = _usuario(supabase, user_id)
    _confirmar_chave(supabase, admin, payload, request)
    supabase.table("pathr_user").update(
        {"banned_at": None, "banned_reason": None, "banned_by": None}
    ).eq("id", str(alvo["id"])).execute()
    _log_event(supabase, "user_unbanned", user_id=str(alvo["id"]), request=request, detail={"by": admin_id})
    return _resumo({**alvo, "banned_at": None, "banned_reason": None}, admin_id)
