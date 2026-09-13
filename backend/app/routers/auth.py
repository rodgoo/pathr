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
    ResendVerificationRequest,
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
from app.services import cifra, geo, limites, usernames
from app.services.moderacao import e_moderador
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
        username=user.get("username") or "",
        is_moderator=e_moderador(user),
        has_avatar=bool(user.get("avatar_path")),
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
    family_id: Optional[str] = None,
) -> SessionOut:
    """Cria a linha de sessão e devolve o par de tokens.

    `family_id` é o LOGIN a que o token pertence: nasce igual ao id no login e
    é herdado a cada rotação. É por ele que um reuso suspeito derruba só aquele
    aparelho, e não todos os lugares onde a conta está aberta.
    """
    session_id = str(uuid.uuid4())
    refresh_token = new_token()
    supabase.table("pathr_refresh_token").insert(
        {
            "id": session_id,
            "user_id": str(user["id"]),
            "token_hash": hash_token(refresh_token),
            "expires_at": (_now() + timedelta(days=settings.refresh_token_days)).isoformat(),
            "rotated_from": rotated_from,
            "family_id": family_id or session_id,
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


@router.post("/signup", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Cria a conta. NÃO devolve sessão: a entrada exige e-mail confirmado.

    O desenho anterior deixava entrar na hora e cobrava a confirmação depois,
    para não perder quem abandona no meio do cadastro. A troca é deliberada:
    sem a confirmação, qualquer pessoa cria conta com o e-mail de outra, e o
    endereço é o que usamos para recuperar senha. O custo é uma ida à caixa
    de entrada antes do primeiro acesso.
    """
    limites.consumir(supabase, limites.CADASTRO_POR_IP, client_ip(request))
    problems = password_problems(payload.password)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha fraca: " + ", ".join(problems) + ".",
        )

    # Import tardio: social importa `deps`, que este módulo também usa, e
    # no topo os dois routers se importariam em círculo.
    from app.routers.social import gerar_para, ocupados

    desejado = usernames.normalizar(payload.username)
    if desejado:
        motivo = usernames.problema(desejado)
        if motivo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Nome de usuário: {motivo}")
        if ocupados(supabase, [desejado]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este nome de usuário já está em uso. Escolha outro ou deixe em branco.",
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

    base = {
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        # O dia de estudo vira à meia-noite de onde a pessoa mora, não de
        # Brasília (ver services/geo.fuso_de).
        "timezone_name": geo.fuso_de(payload.city, payload.state),
    }
    # O índice único é quem garante o @: duas pessoas "Ana Souza" no mesmo
    # segundo passam as duas pela checagem, e só a segunda é recusada. Para
    # quem não escolheu, tenta de novo com o próximo nome livre; para quem
    # escolheu, a resposta certa é dizer que o nome acabou de ser pego.
    created = None
    for _tentativa in range(3):
        username = desejado or gerar_para(supabase, payload.name)
        try:
            created = supabase.table("pathr_user").insert({**base, "username": username}).execute().data[0]
            break
        except Exception as exc:  # noqa: BLE001
            if "username" not in str(exc).lower():
                raise
            if desejado:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Este nome de usuário acabou de ser escolhido. Escolha outro.",
                ) from exc
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não consegui reservar um nome de usuário. Tente de novo.",
        )

    # Perfil, streak e módulo de idioma nascem junto: toda rota depois disto
    # assume que existem, e criá-los sob demanda espalharia esse "se não
    # existir, cria" por dez lugares.
    user_id = str(created["id"])
    supabase.table("pathr_profile").insert(
        {
            "user_id": user_id,
            # Cifrada no banco (services/cifra.py).
            "birth_date": cifra.cifrar(payload.birth_date.isoformat(), cifra.ctx_nascimento(user_id)),
            "city": payload.city.strip(),
            "state": payload.state.strip(),
            "country": payload.country,
        }
    ).execute()
    supabase.table("pathr_streak").insert({"user_id": user_id}).execute()
    supabase.table("pathr_english_profile").insert({"user_id": user_id}).execute()

    token = _issue_email_token(supabase, user_id, "verify_email", _VERIFY_TTL)
    send_verification_email(created["email"], created.get("name") or "", token)
    _log_event(supabase, "signup", user_id=user_id, request=request)

    # Um aparelho que cria conta nova pode ainda guardar o cookie de sessão de
    # OUTRA conta — já rotacionado há tempo. Se ele sobrevive, a próxima
    # renovação (ao confirmar o e-mail, por exemplo) apresenta esse token velho
    # e dispara a detecção de reuso contra a outra conta. Foi o que desconectou
    # um computador em 13/09. Quem acabou de criar conta não está logado em
    # nenhuma: os cookies saem daqui.
    _clear_session_cookies(response)
    return MessageOut(
        detail="Conta criada. Confirme seu e-mail pelo link que enviamos para entrar."
    )


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Entrada por e-mail e senha, com segundo fator quando ativo."""
    # Por IP, além do bloqueio por conta: o bloqueio segura quem martela UMA
    # conta; este segura quem tenta uma senha comum em mil contas diferentes.
    limites.consumir(supabase, limites.LOGIN_POR_IP, client_ip(request))
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

    if not user.get("email_verified_at"):
        # Só depois da senha conferida. Antes disso, esta resposta diria a
        # quem sonda que o endereço tem conta — o mesmo vazamento que as
        # mensagens iguais de e-mail/senha acima evitam.
        _log_event(supabase, "login_unverified", user_id=str(user["id"]), request=request)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirme seu e-mail para entrar. Enviamos um link quando você criou a conta.",
            headers={"X-Pathr-Unverified": "1"},
        )

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


# Quanto tempo depois de uma troca um token antigo ainda conta como corrida da
# mesma tela, e não como cookie roubado. Cobre a rede lenta do celular; roubo
# de verdade usa o cookie bem depois disso.
JANELA_DE_CORRIDA = timedelta(seconds=60)


def _reuso(supabase: Client, session: dict) -> Optional[str]:
    """O que significa usar este token já revogado.

    - "corrida": ele foi TROCADO há instantes (tem sucessor recente).
    - "roubo": foi trocado há tempo — alguém guardou o cookie velho.
    - None: não tem sucessor — saiu por logout ou já foi derrubado. Não há
      token novo para um invasor estar usando, então não é sinal de roubo.
    """
    sucessores = (
        supabase.table("pathr_refresh_token")
        .select("id,created_at")
        .eq("rotated_from", str(session["id"]))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not sucessores:
        return None
    revogado_em = _parse_momento(session.get("revoked_at"))
    if revogado_em and _now() - revogado_em <= JANELA_DE_CORRIDA:
        return "corrida"
    return "roubo"


def _familia(session: dict) -> str:
    return str(session.get("family_id") or session["id"])


def _revogar_familia(supabase: Client, session: dict) -> None:
    """Revoga a cadeia de rotação de UM login — e só ela.

    Antes, reuso revogava toda sessão viva da conta. O caso que derrubou
    produção (13/09): um celular guardava o cookie antigo de uma conta; ao
    confirmar o e-mail de OUTRA conta criada nele, o app tentou renovar com
    esse cookie velho — indistinguível de roubo — e o castigo caiu no
    computador, logado num login totalmente separado. Revogando a família, o
    token suspeito e tudo que descende dele morrem (um invasor com o cookie
    velho perde o acesso), e os outros aparelhos seguem logados.

    Token anterior à coluna `family_id` (ela chegou na migração 0025, que já
    preenche as cadeias existentes): segue os sucessores pelo `rotated_from`.
    """
    familia = session.get("family_id")
    agora = _now().isoformat()
    if familia:
        supabase.table("pathr_refresh_token").update({"revoked_at": agora}).eq(
            "family_id", str(familia)
        ).is_("revoked_at", "null").execute()
        return
    fila, vistos = [str(session["id"])], set()
    while fila and len(vistos) < 2000:
        atual = fila.pop()
        if atual in vistos:
            continue
        vistos.add(atual)
        supabase.table("pathr_refresh_token").update({"revoked_at": agora}).eq("id", atual).is_(
            "revoked_at", "null"
        ).execute()
        fila.extend(
            str(linha["id"])
            for linha in supabase.table("pathr_refresh_token").select("id").eq("rotated_from", atual).execute().data
            or []
        )


def _parse_momento(valor: Any) -> Optional[datetime]:
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


@router.post("/refresh", response_model=SessionOut)
def refresh(
    request: Request,
    response: Response,
    supabase: Client = Depends(get_supabase),
):
    """Troca o refresh token por um par novo, queimando o antigo.

    Reuso de um token já rotacionado há tempo é tratado como roubo de cookie:
    revoga a FAMÍLIA daquele login (ver `_revogar_familia`). Outros aparelhos
    da mesma conta não caem — derrubá-los por um cookie velho em outro lugar
    era um logout do nada, sem ganho de segurança para o login suspeito.
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
        tipo = _reuso(supabase, session)
        if tipo == "corrida":
            # Duas renovações do MESMO cliente ao mesmo tempo: a primeira
            # trocou o token, a segunda chegou com o anterior. Não é roubo — é
            # a tela disparando várias chamadas que expiraram juntas. Tratar
            # como roubo derrubava todas as sessões no meio de um clique: a
            # ação era desfeita e a conta, desconectada.
            users = supabase.table("pathr_user").select("*").eq("id", user_id).limit(1).execute().data
            if users:
                return _issue_session(
                    supabase, users[0], response, request,
                    rotated_from=str(session["id"]), family_id=_familia(session),
                )
        if tipo == "roubo":
            _revogar_familia(supabase, session)
            _log_event(supabase, "refresh_reuse", user_id=user_id, request=request)
            _clear_session_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sessão encerrada por segurança. Entre novamente.",
            )
        # Sem sucessor: a sessão saiu por logout ou já tinha sido derrubada.
        # Pedir para entrar de novo basta. Revogar tudo aqui era o que fazia
        # dois aparelhos se derrubarem em cadeia — cada 401 de um virava
        # "roubo" contra o outro.
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão encerrada. Entre novamente.",
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
    return _issue_session(
        supabase, users[0], response, request, rotated_from=str(session["id"]), family_id=_familia(session)
    )


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
    limites.consumir(supabase, limites.EMAIL_POR_DESTINO, current_user.get("email"))
    token = _issue_email_token(supabase, str(current_user["id"]), "verify_email", _VERIFY_TTL)
    send_verification_email(current_user["email"], current_user.get("name") or "", token)
    return MessageOut(detail="Enviamos um novo link de confirmação.")


@router.post("/resend-verification-public", response_model=MessageOut)
def resend_verification_public(
    payload: ResendVerificationRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    """Reenvia o link de confirmação sem exigir sessão.

    Necessária desde que o login passou a exigir e-mail confirmado: quem
    perdeu o e-mail não consegue entrar, e a rota autenticada de reenvio
    ficaria inalcançável — a conta existiria sem nenhum caminho de volta.

    Responde igual em todos os casos, como /forgot-password: e-mail sem
    conta, conta já confirmada e envio feito são indistinguíveis de fora.
    """
    generica = MessageOut(
        detail="Se houver uma conta com este e-mail aguardando confirmação, enviamos um novo link."
    )
    limites.consumir(supabase, limites.EMAIL_POR_IP, client_ip(request))
    limites.consumir(supabase, limites.EMAIL_POR_DESTINO, payload.email)
    user = _find_user_by_email(supabase, payload.email)
    if not user or user.get("email_verified_at"):
        return generica

    token = _issue_email_token(supabase, str(user["id"]), "verify_email", _VERIFY_TTL)
    send_verification_email(user["email"], user.get("name") or "", token)
    _log_event(supabase, "verification_resent", user_id=str(user["id"]), request=request)
    return generica


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(
    payload: EmailRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    """Sempre responde igual, exista a conta ou não — a resposta não pode ser
    usada para descobrir quem tem cadastro."""
    # Os dois limites valem exista a conta ou não: limitar só quando existe
    # faria o 429 revelar quais e-mails têm cadastro.
    limites.consumir(supabase, limites.EMAIL_POR_IP, client_ip(request))
    limites.consumir(supabase, limites.EMAIL_POR_DESTINO, payload.email)
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
