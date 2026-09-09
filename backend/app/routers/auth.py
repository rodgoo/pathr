"""Cadastro, entrada, sessão e recuperação de conta.

A sessão é um par: um JWT curto (`pathr_access`) que carrega o id da linha de
sessão, e um token opaco longo (`pathr_refresh`) que só existe para trocar por
um par novo. Os dois vão em cookie HttpOnly — o JavaScript da página nunca os
lê, então um XSS não leva a sessão embora.

Rotação do refresh: cada uso queima o token e emite outro, guardando de quem
ele veio (`rotated_from`). Se um token já usado reaparecer, isso é sinal de
que alguém copiou o cookie, e a resposta é derrubar a família inteira de
sessões daquele usuário em vez de só recusar aquele pedido.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from supabase import Client

from app.config import settings
from app.database import get_supabase
from app.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    client_ip,
    get_current_user,
    get_current_user_allow_unverified,
    user_agent,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MessageOut,
    MfaActivateOut,
    MfaActivateRequest,
    MfaSetupOut,
    ResetPasswordRequest,
    SessionOut,
    SignupRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.security import (
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_totp_secret,
    hash_password,
    hash_token,
    is_locked,
    new_token,
    next_failure_state,
    password_problems,
    reset_failure_state,
    totp_provisioning_uri,
    totp_qr_code_svg,
    verify_password,
    verify_totp_code,
)
from app.services.email import send_password_reset, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])

# Validade dos tokens de e-mail. Verificação dura mais porque a pessoa pode
# só abrir a caixa de entrada no dia seguinte; reset de senha é curto porque
# um link vivo demais no e-mail é uma chave esquecida na porta.
_VERIFY_TTL = timedelta(days=3)
_RESET_TTL = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_out(user: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(user["id"]),
        email=user["email"],
        name=user.get("name") or "",
        email_verified=bool(user.get("email_verified_at")),
        mfa_enabled=bool(user.get("mfa_enabled")),
        onboarding_completed=bool(user.get("onboarding_completed")),
        locale=user.get("locale") or "pt-BR",
        timezone_name=user.get("timezone_name") or "America/Sao_Paulo",
        theme=user.get("theme") or "system",
    )


def _log_event(
    supabase: Client,
    event_type: str,
    *,
    user_id: Optional[str] = None,
    request: Optional[Request] = None,
    detail: Optional[dict] = None,
) -> None:
    """Trilha de auditoria (`pathr_security_event`).

    Best-effort de propósito: perder uma linha de log não pode impedir alguém
    de entrar na própria conta.
    """
    try:
        supabase.table("pathr_security_event").insert(
            {
                "user_id": user_id,
                "event_type": event_type,
                "ip": client_ip(request),
                "user_agent": user_agent(request),
                "detail": detail or {},
            }
        ).execute()
    except Exception:  # noqa: BLE001
        pass


def _find_user_by_email(supabase: Client, email: str) -> Optional[dict]:
    rows = (
        supabase.table("pathr_user")
        .select("*")
        .eq("email", email.strip().lower())
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Cookies HttpOnly + Secure + SameSite.

    `secure=True` mesmo em desenvolvimento porque o dev server roda em HTTPS
    (localhost com certificado), e um cookie que muda de flag entre ambientes
    esconde justamente a classe de bug que só aparece em produção.
    """
    shared = {
        "httponly": True,
        "secure": True,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    if settings.cookie_domain:
        shared["domain"] = settings.cookie_domain

    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_minutes * 60,
        **shared,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_days * 24 * 3600,
        **shared,
    )


def _clear_session_cookies(response: Response) -> None:
    shared: dict[str, Any] = {"path": "/"}
    if settings.cookie_domain:
        shared["domain"] = settings.cookie_domain
    response.delete_cookie(ACCESS_COOKIE, **shared)
    response.delete_cookie(REFRESH_COOKIE, **shared)


def _issue_session(
    supabase: Client,
    user: dict,
    response: Response,
    request: Optional[Request],
    *,
    rotated_from: Optional[str] = None,
) -> SessionOut:
    """Cria a linha de sessão e devolve o par de tokens."""
    session_id = str(uuid.uuid4())
    refresh_token = new_token()
    supabase.table("pathr_refresh_token").insert(
        {
            "id": session_id,
            "user_id": str(user["id"]),
            "token_hash": hash_token(refresh_token),
            "expires_at": (_now() + timedelta(days=settings.refresh_token_days)).isoformat(),
            "rotated_from": rotated_from,
            "user_agent": user_agent(request),
            "ip": client_ip(request),
        }
    ).execute()

    access_token = create_access_token(user["id"], session_id)
    _set_session_cookies(response, access_token, refresh_token)
    return SessionOut(
        user=_user_out(user),
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
    )


def _issue_email_token(supabase: Client, user_id: str, purpose: str, ttl: timedelta) -> str:
    """Emite um token de e-mail e invalida os anteriores do mesmo propósito.

    Sem a invalidação, um link antigo de reset continuaria valendo depois de
    a pessoa pedir outro — e "pedi de novo porque o primeiro vazou" é
    exatamente o caso em que isso importa.
    """
    supabase.table("pathr_email_token").update({"used_at": _now().isoformat()}).eq(
        "user_id", user_id
    ).eq("purpose", purpose).is_("used_at", "null").execute()

    raw = new_token()
    supabase.table("pathr_email_token").insert(
        {
            "user_id": user_id,
            "purpose": purpose,
            "token_hash": hash_token(raw),
            "expires_at": (_now() + ttl).isoformat(),
        }
    ).execute()
    return raw


def _consume_email_token(supabase: Client, token: str, purpose: str) -> Optional[dict]:
    """Valida e queima o token. Devolve o usuário, ou None se não servir."""
    rows = (
        supabase.table("pathr_email_token")
        .select("*")
        .eq("token_hash", hash_token(token))
        .eq("purpose", purpose)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    row = rows[0]
    if row.get("used_at"):
        return None
    expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if expires_at <= _now():
        return None

    supabase.table("pathr_email_token").update({"used_at": _now().isoformat()}).eq(
        "id", row["id"]
    ).execute()

    users = supabase.table("pathr_user").select("*").eq("id", row["user_id"]).limit(1).execute().data
    return users[0] if users else None


@router.post("/signup", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Cria a conta e já devolve sessão.

    A pessoa entra direto e só precisa confirmar o e-mail para usar as rotas
    que dependem dele — exigir a confirmação antes de qualquer coisa faz
    metade das pessoas abandonar antes de ver o produto.
    """
    problems = password_problems(payload.password)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha fraca: " + ", ".join(problems) + ".",
        )

    email = payload.email.strip().lower()
    if _find_user_by_email(supabase, email):
        # Mensagem propositalmente igual à de sucesso do ponto de vista de quem
        # sonda: não confirma nem nega que o e-mail existe... exceto que aqui
        # ele precisa saber, porque é um cadastro. O tradeoff é assumido —
        # sem isso a pessoa fica presa sem entender por quê.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com este e-mail. Tente entrar ou recuperar a senha.",
        )

    created = (
        supabase.table("pathr_user")
        .insert(
            {
                "email": email,
                "name": payload.name.strip(),
                "password_hash": hash_password(payload.password),
            }
        )
        .execute()
        .data[0]
    )

    # Perfil, streak e módulo de idioma nascem junto: toda rota depois disto
    # assume que existem, e criá-los sob demanda espalharia esse "se não
    # existir, cria" por dez lugares.
    user_id = str(created["id"])
    supabase.table("pathr_profile").insert({"user_id": user_id}).execute()
    supabase.table("pathr_streak").insert({"user_id": user_id}).execute()
    supabase.table("pathr_english_profile").insert({"user_id": user_id}).execute()

    token = _issue_email_token(supabase, user_id, "verify_email", _VERIFY_TTL)
    send_verification_email(created["email"], created.get("name") or "", token)
    _log_event(supabase, "signup", user_id=user_id, request=request)

    return _issue_session(supabase, created, response, request)


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Entrada por e-mail e senha, com segundo fator quando ativo."""
    user = _find_user_by_email(supabase, payload.email)

    # Mesma resposta para e-mail inexistente e senha errada: dizer qual dos
    # dois falhou entrega uma lista de e-mails cadastrados a quem sondar.
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos."
    )
    if not user:
        _log_event(supabase, "login_fail", request=request, detail={"reason": "unknown_email"})
        raise invalid

    if is_locked(user):
        _log_event(supabase, "login_locked", user_id=str(user["id"]), request=request)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas. Tente novamente em {settings.lockout_minutes} minutos.",
        )

    if not verify_password(payload.password, user["password_hash"]):
        supabase.table("pathr_user").update(next_failure_state(user)).eq("id", user["id"]).execute()
        _log_event(supabase, "login_fail", user_id=str(user["id"]), request=request)
        raise invalid

    if user.get("mfa_enabled"):
        if not payload.mfa_code:
            # 401 com um corpo que o frontend reconhece: ainda não é sessão,
            # mas também não é senha errada.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Informe o código do autenticador.",
                headers={"X-Pathr-Mfa": "required"},
            )
        if not _mfa_code_accepted(supabase, user, payload.mfa_code):
            supabase.table("pathr_user").update(next_failure_state(user)).eq(
                "id", user["id"]
            ).execute()
            _log_event(supabase, "mfa_fail", user_id=str(user["id"]), request=request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Código inválido."
            )

    supabase.table("pathr_user").update(reset_failure_state()).eq("id", user["id"]).execute()
    _log_event(supabase, "login_ok", user_id=str(user["id"]), request=request)
    return _issue_session(supabase, user, response, request)


def _mfa_code_accepted(supabase: Client, user: dict, code: str) -> bool:
    """TOTP, ou um código de backup de uso único."""
    secret_encrypted = user.get("mfa_secret_encrypted")
    if secret_encrypted and verify_totp_code(decrypt_secret(secret_encrypted), code):
        return True
    return _consume_backup_code(supabase, str(user["id"]), code)


def _consume_backup_code(supabase: Client, user_id: str, code: str) -> bool:
    normalized = code.strip().upper().replace(" ", "")
    rows = (
        supabase.table("pathr_mfa_backup_code")
        .select("id,code_hash,used_at")
        .eq("user_id", user_id)
        .is_("used_at", "null")
        .execute()
        .data
        or []
    )
    target = hash_token(normalized)
    for row in rows:
        if row["code_hash"] == target:
            supabase.table("pathr_mfa_backup_code").update({"used_at": _now().isoformat()}).eq(
                "id", row["id"]
            ).execute()
            return True
    return False


@router.post("/refresh", response_model=SessionOut)
def refresh(
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Troca o refresh token por um par novo, queimando o antigo.

    Reuso de um token já rotacionado é tratado como roubo de cookie: revoga
    TODA sessão viva do usuário. O custo de errar aqui é a pessoa logar de
    novo; o custo de não fazer nada é um invasor manter acesso indefinido.
    """
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão ausente.")

    rows = (
        supabase.table("pathr_refresh_token")
        .select("*")
        .eq("token_hash", hash_token(raw))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")

    session = rows[0]
    user_id = str(session["user_id"])

    if session.get("revoked_at"):
        supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
            "user_id", user_id
        ).is_("revoked_at", "null").execute()
        _log_event(supabase, "refresh_reuse", user_id=user_id, request=request)
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão encerrada por segurança. Entre novamente.",
        )

    expires_at = datetime.fromisoformat(str(session["expires_at"]).replace("Z", "+00:00"))
    if expires_at <= _now():
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada.")

    users = supabase.table("pathr_user").select("*").eq("id", user_id).limit(1).execute().data
    if not users:
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")

    supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
        "id", session["id"]
    ).execute()
    return _issue_session(supabase, users[0], response, request, rotated_from=str(session["id"]))


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Encerra esta sessão. Idempotente: sair duas vezes não é erro."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
            "token_hash", hash_token(raw)
        ).is_("revoked_at", "null").execute()
    _clear_session_cookies(response)
    return MessageOut(detail="Sessão encerrada.")


@router.post("/logout-all", response_model=MessageOut)
def logout_all(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user_allow_unverified),
    supabase: Client = Depends(get_supabase),
):
    """Derruba todas as sessões — o botão para quando um dispositivo se perde."""
    supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
        "user_id", str(current_user["id"])
    ).is_("revoked_at", "null").execute()
    _log_event(supabase, "logout_all", user_id=str(current_user["id"]), request=request)
    _clear_session_cookies(response)
    return MessageOut(detail="Todas as sessões foram encerradas.")


@router.get("/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user_allow_unverified)):
    """Quem está logado. Aceita e-mail não confirmado para o frontend poder
    mostrar o aviso de confirmação em vez de um 403 sem contexto."""
    return _user_out(current_user)


@router.post("/verify-email", response_model=MessageOut)
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    user = _consume_email_token(supabase, payload.token, "verify_email")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link inválido ou expirado. Peça um novo e-mail de confirmação.",
        )
    supabase.table("pathr_user").update({"email_verified_at": _now().isoformat()}).eq(
        "id", user["id"]
    ).execute()
    _log_event(supabase, "email_verified", user_id=str(user["id"]), request=request)
    return MessageOut(detail="E-mail confirmado.")


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(
    current_user: dict = Depends(get_current_user_allow_unverified),
    supabase: Client = Depends(get_supabase),
):
    if current_user.get("email_verified_at"):
        return MessageOut(detail="Seu e-mail já está confirmado.")
    token = _issue_email_token(supabase, str(current_user["id"]), "verify_email", _VERIFY_TTL)
    send_verification_email(current_user["email"], current_user.get("name") or "", token)
    return MessageOut(detail="Enviamos um novo link de confirmação.")


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(
    payload: EmailRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    """Sempre responde igual, exista a conta ou não — a resposta não pode ser
    usada para descobrir quem tem cadastro."""
    user = _find_user_by_email(supabase, payload.email)
    if user:
        token = _issue_email_token(supabase, str(user["id"]), "reset_password", _RESET_TTL)
        send_password_reset(user["email"], user.get("name") or "", token)
        _log_event(supabase, "password_reset_requested", user_id=str(user["id"]), request=request)
    return MessageOut(detail="Se houver conta com este e-mail, enviamos o link de recuperação.")


@router.post("/reset-password", response_model=MessageOut)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    problems = password_problems(payload.password)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha fraca: " + ", ".join(problems) + ".",
        )
    user = _consume_email_token(supabase, payload.token, "reset_password")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Link inválido ou expirado."
        )

    supabase.table("pathr_user").update(
        {"password_hash": hash_password(payload.password), **reset_failure_state()}
    ).eq("id", user["id"]).execute()
    # Trocar a senha derruba todas as sessões: se a troca foi por suspeita de
    # invasão, deixar a sessão do invasor viva anularia o gesto.
    supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
        "user_id", user["id"]
    ).is_("revoked_at", "null").execute()
    _log_event(supabase, "password_reset", user_id=str(user["id"]), request=request)
    return MessageOut(detail="Senha alterada. Entre com a nova senha.")


@router.post("/change-password", response_model=MessageOut)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")
    problems = password_problems(payload.new_password)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha fraca: " + ", ".join(problems) + ".",
        )
    supabase.table("pathr_user").update({"password_hash": hash_password(payload.new_password)}).eq(
        "id", current_user["id"]
    ).execute()
    # Mantém ESTA sessão viva e derruba as outras — trocar a senha no
    # computador de casa não deveria expulsar quem está trocando.
    supabase.table("pathr_refresh_token").update({"revoked_at": _now().isoformat()}).eq(
        "user_id", str(current_user["id"])
    ).neq("id", current_user["session_id"]).is_("revoked_at", "null").execute()
    _log_event(supabase, "password_changed", user_id=str(current_user["id"]), request=request)
    return MessageOut(detail="Senha alterada.")


# --------------------------------------------------------------------------
# Segundo fator
# --------------------------------------------------------------------------


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Gera um segredo TOTP e o guarda como PENDENTE.

    Pendente e não ativo: se o segredo entrasse direto em
    `mfa_secret_encrypted`, uma configuração abandonada no meio (app fechado
    antes de escanear) trancaria a pessoa fora da própria conta no próximo
    login. Só `POST /mfa/activate`, que prova que o app está gerando código
    certo, promove o pendente a valendo.
    """
    if current_user.get("mfa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="O segundo fator já está ativo."
        )
    secret = generate_totp_secret()
    supabase.table("pathr_user").update(
        {"mfa_pending_secret_encrypted": encrypt_secret(secret)}
    ).eq("id", current_user["id"]).execute()

    uri = totp_provisioning_uri(secret, current_user["email"])
    return MfaSetupOut(secret=secret, otpauth_uri=uri, qr_svg=totp_qr_code_svg(uri))


@router.post("/mfa/activate", response_model=MfaActivateOut)
def mfa_activate(
    payload: MfaActivateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Confirma o código e liga o segundo fator, devolvendo os códigos de
    backup — mostrados UMA vez, porque só o hash fica guardado."""
    pending = current_user.get("mfa_pending_secret_encrypted")
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comece a configuração do segundo fator antes de confirmar.",
        )
    secret = decrypt_secret(pending)
    if not verify_totp_code(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código inválido.")

    codes = generate_backup_codes()
    user_id = str(current_user["id"])
    supabase.table("pathr_mfa_backup_code").delete().eq("user_id", user_id).execute()
    supabase.table("pathr_mfa_backup_code").insert(
        [{"user_id": user_id, "code_hash": hash_token(code)} for code in codes]
    ).execute()
    supabase.table("pathr_user").update(
        {
            "mfa_enabled": True,
            "mfa_secret_encrypted": pending,
            "mfa_pending_secret_encrypted": None,
        }
    ).eq("id", user_id).execute()
    _log_event(supabase, "mfa_enabled", user_id=user_id, request=request)
    return MfaActivateOut(backup_codes=codes)


@router.post("/mfa/disable", response_model=MessageOut)
def mfa_disable(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Desliga o segundo fator. Pede a senha atual — desligar uma proteção não
    pode ser mais fácil que ligá-la.

    Reaproveita ChangePasswordRequest só pelo campo `current_password`;
    `new_password` é ignorado aqui.
    """
    if not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha incorreta.")
    user_id = str(current_user["id"])
    supabase.table("pathr_mfa_backup_code").delete().eq("user_id", user_id).execute()
    supabase.table("pathr_user").update(
        {
            "mfa_enabled": False,
            "mfa_secret_encrypted": None,
            "mfa_pending_secret_encrypted": None,
        }
    ).eq("id", user_id).execute()
    _log_event(supabase, "mfa_disabled", user_id=user_id, request=request)
    return MessageOut(detail="Segundo fator desativado.")
