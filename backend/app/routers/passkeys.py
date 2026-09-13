"""Chave de acesso (WebAuthn): cadastrar, listar, remover e entrar.

## Por que ela, e por que ao lado da senha

A chave privada nunca sai do aparelho, e a assinatura fica presa ao domínio:
uma página falsa com a cara do PathR não consegue usar a chave, porque o
navegador não a entrega fora de pathr.notter.com.br. Senha pode ser digitada
na página errada; chave de acesso não. E roubar o banco não dá acesso a nada —
só o lado público mora aqui.

Ela entra AO LADO da senha, e não no lugar: quem troca de aparelho sem chave
sincronizada precisa de um caminho de volta.

## Entrar com chave dispensa o código do autenticador

A chave já é dois fatores num gesto: o aparelho (algo que a pessoa tem) e a
biometria ou o PIN que o desbloqueia (algo que ela é ou sabe). Por isso a
verificação de usuário é EXIGIDA nas duas cerimônias — sem ela a chave seria
só "algo que se tem", e aí sim pediria o segundo fator.

## O que não é reimplementado aqui

Gerar opções e conferir assinatura, origem, domínio e contador é da
py_webauthn. Este arquivo guarda desafios e credenciais, e emite a sessão pelo
MESMO caminho do login por senha (`_issue_session`).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from supabase import Client
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings
from app.database import get_supabase
from app.deps import client_ip, get_current_user, user_agent
from app.routers.auth import _issue_session, _log_event
from app.schemas.auth import SessionOut
from app.security import is_locked, reset_failure_state
from app.services import limites
from app.services import passkeys as chaves

router = APIRouter(prefix="/auth/passkeys", tags=["autenticação"])

# Tempo de tocar no leitor de digital ou digitar o PIN, com folga. Mais que
# isso é um desafio esperando ser reapresentado.
_VALIDADE = timedelta(minutes=5)
_EXPIROU = "O pedido de chave de acesso expirou. Tente de novo."


class VerificarCadastro(BaseModel):
    challenge_id: str
    credential: dict[str, Any]
    name: Optional[str] = Field(default=None, max_length=80)


class VerificarEntrada(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _quando(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    try:
        lido = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return lido if lido.tzinfo else lido.replace(tzinfo=timezone.utc)


def _guardar_desafio(
    supabase: Client, purpose: str, desafio: bytes, user_id: Optional[str] = None
) -> str:
    linha = (
        supabase.table("pathr_webauthn_challenge")
        .insert(
            {
                "user_id": user_id,
                "purpose": purpose,
                "challenge": bytes_to_base64url(desafio),
                "expires_at": (_agora() + _VALIDADE).isoformat(),
            }
        )
        .execute()
        .data[0]
    )
    return str(linha["id"])


def _consumir_desafio(
    supabase: Client, challenge_id: str, purpose: str, user_id: Optional[str] = None
) -> bytes:
    """O desafio, já marcado como usado. Levanta 400 se não servir mais.

    Marca ANTES de verificar a assinatura: uma resposta rejeitada também gasta
    o desafio. Deixá-lo reutilizável daria infinitas tentativas com o mesmo
    número a quem erra de propósito.
    """
    try:
        uuid.UUID(challenge_id)
    except ValueError:
        # Id malformado iria ao PostgREST como uuid inválido e voltaria 500.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_EXPIROU)
    linhas = (
        supabase.table("pathr_webauthn_challenge")
        .select("*")
        .eq("id", challenge_id)
        .limit(1)
        .execute()
        .data
    )
    linha = linhas[0] if linhas else None
    expira = _quando(linha.get("expires_at")) if linha else None
    invalido = (
        linha is None
        or linha.get("purpose") != purpose
        or linha.get("used_at")
        or expira is None
        or expira < _agora()
        or (user_id is not None and str(linha.get("user_id")) != user_id)
    )
    if invalido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_EXPIROU)
    supabase.table("pathr_webauthn_challenge").update({"used_at": _agora().isoformat()}).eq(
        "id", challenge_id
    ).execute()
    return base64url_to_bytes(linha["challenge"])


def _resumo(linha: dict) -> dict[str, Any]:
    return {
        "id": str(linha["id"]),
        "name": linha.get("name"),
        "created_at": linha.get("created_at"),
        "last_used_at": linha.get("last_used_at"),
        "backed_up": bool(linha.get("backed_up")),
    }


@router.get("")
def listar(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    linhas = (
        supabase.table("pathr_passkey")
        .select("id,name,created_at,last_used_at,backed_up")
        .eq("user_id", str(current_user["id"]))
        .order("created_at")
        .execute()
        .data
        or []
    )
    return [_resumo(linha) for linha in linhas]


@router.post("/register/options")
def opcoes_de_cadastro(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    existentes = (
        supabase.table("pathr_passkey").select("credential_id").eq("user_id", user_id).execute().data
        or []
    )
    opcoes = generate_registration_options(
        rp_id=chaves.rp_id(),
        rp_name=settings.webauthn_rp_name,
        user_name=current_user["email"],
        user_id=uuid.UUID(user_id).bytes,
        user_display_name=current_user.get("name") or current_user["email"],
        # Residente (descobrível): é o que deixa entrar sem digitar o e-mail —
        # a própria chave diz de quem é a conta.
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        # O mesmo aparelho não cadastra duas vezes: o navegador recusa na hora.
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(linha["credential_id"]))
            for linha in existentes
        ],
    )
    return {
        "challenge_id": _guardar_desafio(supabase, "register", opcoes.challenge, user_id),
        "options": json.loads(options_to_json(opcoes)),
    }


@router.post("/register/verify", status_code=status.HTTP_201_CREATED)
def confirmar_cadastro(
    payload: VerificarCadastro,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    desafio = _consumir_desafio(supabase, payload.challenge_id, "register", user_id)
    try:
        verificada = verify_registration_response(
            credential=payload.credential,
            expected_challenge=desafio,
            expected_rp_id=chaves.rp_id(),
            expected_origin=chaves.origem(),
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001 — resposta inválida em qualquer forma
        _log_event(
            supabase, "passkey_register_fail", user_id=user_id, request=request,
            detail={"reason": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não consegui confirmar a chave de acesso. Tente de novo.",
        )

    transportes = (payload.credential.get("response") or {}).get("transports") or []
    linha = (
        supabase.table("pathr_passkey")
        .insert(
            {
                "user_id": user_id,
                "credential_id": bytes_to_base64url(verificada.credential_id),
                "public_key": bytes_to_base64url(verificada.credential_public_key),
                "sign_count": int(verificada.sign_count),
                "transports": transportes,
                "name": (payload.name or "").strip()
                or chaves.nome_do_aparelho(user_agent(request) or ""),
                "backed_up": bool(getattr(verificada, "credential_backed_up", False)),
            }
        )
        .execute()
        .data[0]
    )
    _log_event(supabase, "passkey_added", user_id=user_id, request=request)
    return _resumo(linha)


@router.delete("/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    passkey_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = str(current_user["id"])
    nao_achou = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Chave de acesso não encontrada."
    )
    try:
        uuid.UUID(passkey_id)
    except ValueError:
        raise nao_achou
    achadas = (
        supabase.table("pathr_passkey")
        .select("id")
        .eq("id", passkey_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not achadas:
        raise nao_achou
    supabase.table("pathr_passkey").delete().eq("id", passkey_id).eq("user_id", user_id).execute()
    _log_event(supabase, "passkey_removed", user_id=user_id, request=request)
    return None


@router.post("/login/options")
def opcoes_de_entrada(request: Request, supabase: Client = Depends(get_supabase)):
    """Sem `allow_credentials`: a chave é descobrível, e é ela que diz quem é.
    Pedir o e-mail antes contaria a quem sonda quais endereços têm chave.

    Limitada por IP: sem sessão e gravando um desafio por chamada, era a rota
    mais barata para encher uma tabela do banco em laço."""
    limites.consumir(supabase, limites.LOGIN_POR_IP, client_ip(request))
    opcoes = generate_authentication_options(
        rp_id=chaves.rp_id(), user_verification=UserVerificationRequirement.REQUIRED
    )
    return {
        "challenge_id": _guardar_desafio(supabase, "login", opcoes.challenge),
        "options": json.loads(options_to_json(opcoes)),
    }


@router.post("/login/verify", response_model=SessionOut)
def entrar(
    payload: VerificarEntrada,
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Confere a assinatura e emite a MESMA sessão do login por senha.

    Falha de assinatura não conta para o bloqueio de conta, ao contrário da
    senha errada: assinatura não se adivinha por tentativa, e contar deixaria
    qualquer um trancar a conta alheia mandando respostas inventadas.
    """
    desafio = _consumir_desafio(supabase, payload.challenge_id, "login")
    recusada = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Esta chave de acesso não foi reconhecida. Entre com a senha e "
            "cadastre a chave de novo em Configurações."
        ),
    )

    credential_id = str(payload.credential.get("id") or "")
    linhas = (
        supabase.table("pathr_passkey").select("*").eq("credential_id", credential_id).limit(1).execute().data
        if credential_id
        else []
    )
    if not linhas:
        _log_event(supabase, "passkey_fail", request=request, detail={"reason": "unknown_credential"})
        raise recusada
    chave = linhas[0]

    usuarios = (
        supabase.table("pathr_user").select("*").eq("id", str(chave["user_id"])).limit(1).execute().data
    )
    if not usuarios:
        raise recusada
    user = usuarios[0]

    if is_locked(user):
        _log_event(supabase, "login_locked", user_id=str(user["id"]), request=request)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas. Tente novamente em {settings.lockout_minutes} minutos.",
        )

    try:
        verificada = verify_authentication_response(
            credential=payload.credential,
            expected_challenge=desafio,
            expected_rp_id=chaves.rp_id(),
            expected_origin=chaves.origem(),
            credential_public_key=base64url_to_bytes(chave["public_key"]),
            credential_current_sign_count=int(chave.get("sign_count") or 0),
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001 — assinatura, origem ou contador
        _log_event(
            supabase, "passkey_fail", user_id=str(user["id"]), request=request,
            detail={"reason": type(exc).__name__},
        )
        raise recusada

    supabase.table("pathr_passkey").update(
        {"sign_count": int(verificada.new_sign_count), "last_used_at": _agora().isoformat()}
    ).eq("id", str(chave["id"])).execute()

    if not user.get("email_verified_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirme seu e-mail para entrar. Enviamos um link quando você criou a conta.",
            headers={"X-Pathr-Unverified": "1"},
        )

    supabase.table("pathr_user").update(reset_failure_state()).eq("id", user["id"]).execute()
    _log_event(
        supabase, "login_ok", user_id=str(user["id"]), request=request, detail={"method": "passkey"}
    )
    return _issue_session(supabase, user, response, request)
