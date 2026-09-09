"""Primitivas de segurança: senha, MFA, tokens.

Mesmas escolhas do Notter — as decisões são boas e já foram tomadas uma vez,
não porque os dois dividam qualquer coisa: Argon2id na senha (não bcrypt —
resistente a GPU e vencedor do Password Hashing Competition), TOTP para o
segundo fator, Fernet para cifrar o segredo TOTP em repouso, e JWT curto no
access token com um refresh token opaco e rotacionado no cookie.

As contas do PathR são dele: outro banco, outra tabela de usuários, outra
sessão.

Nada aqui toca o banco: são funções puras, testáveis sem Supabase.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
import pyotp
import qrcode
import qrcode.image.svg
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet

from app.config import settings

# --- Senha (Argon2id, a variante default do argon2-cffi) ---

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
    return True


def password_problems(password: str) -> list[str]:
    """Regras mínimas, checadas no servidor.

    O frontend mostra as mesmas dicas enquanto a pessoa digita, mas quem
    decide é aqui — um cliente pode ser qualquer coisa.
    """
    problems: list[str] = []
    if len(password) < 10:
        problems.append("precisa de ao menos 10 caracteres")
    if not any(character.isalpha() for character in password):
        problems.append("precisa de ao menos uma letra")
    if not any(character.isdigit() for character in password):
        problems.append("precisa de ao menos um número")
    return problems


# --- Segredo do MFA cifrado em repouso ---


def _fernet() -> Fernet:
    """Construído sob demanda: uma chave ausente só quebra quem usa MFA, não
    o import do módulo (e portanto não o app inteiro)."""
    if not settings.mfa_encryption_key:
        raise RuntimeError("MFA_ENCRYPTION_KEY não configurada.")
    return Fernet(settings.mfa_encryption_key.encode())


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# --- TOTP ---


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.app_name)


def totp_qr_code_svg(uri: str) -> str:
    """SVG em vez de PNG: escala sem borrar e vai inline no JSON da resposta
    sem precisar de outro endpoint para servir a imagem."""
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


def verify_totp_code(secret: str, code: str) -> bool:
    """`valid_window=1` aceita a janela anterior e a seguinte — relógios de
    celular derivam alguns segundos e recusar por isso é hostil sem ganho."""
    return pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)


def generate_backup_codes(count: int = 8) -> list[str]:
    """Códigos de uso único para quando o celular do TOTP se perde.
    Formato XXXX-XXXX, só o hash é guardado."""
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


# --- Tokens opacos (refresh, verificação de e-mail, reset de senha) ---


def new_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """SHA-256 puro, sem salt, de propósito: o token já tem 288 bits de
    entropia, então não há dicionário a proteger, e o hash precisa ser
    determinístico para o lookup por índice funcionar."""
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(candidate: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_token(candidate), stored_hash)


# --- JWT do access token ---


def create_access_token(user_id: uuid.UUID | str, session_id: uuid.UUID | str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.app_name.lower(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# --- Bloqueio por tentativas ---


def is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    if isinstance(locked_until, str):
        locked_until = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
    return locked_until > datetime.now(timezone.utc)


def next_failure_state(user: dict) -> dict:
    """Conta mais uma senha errada e, no limite, tranca por um tempo.

    Trancar por tempo em vez de exigir intervenção evita transformar um
    ataque de força bruta numa negação de serviço contra o dono da conta.
    """
    attempts = int(user.get("failed_attempts") or 0) + 1
    state: dict[str, Any] = {"failed_attempts": attempts}
    if attempts >= settings.max_failed_attempts:
        state["locked_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=settings.lockout_minutes)
        ).isoformat()
        state["failed_attempts"] = 0
    return state


def reset_failure_state() -> dict:
    return {"failed_attempts": 0, "locked_until": None}
