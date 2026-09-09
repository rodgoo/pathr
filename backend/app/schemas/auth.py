"""Formatos de entrada e saída da autenticação."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    # Preenchido só quando o primeiro POST /login respondeu mfa_required.
    mfa_code: Optional[str] = Field(default=None, max_length=16)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    email_verified: bool
    mfa_enabled: bool
    onboarding_completed: bool
    locale: str
    timezone_name: str
    theme: str


class SessionOut(BaseModel):
    user: UserOut
    # Devolvido no corpo além do cookie: um cliente sem cookie (app nativo,
    # script) usa este valor no header Authorization.
    access_token: str
    expires_in: int


class MfaRequired(BaseModel):
    mfa_required: bool = True
    detail: str = "Informe o código do autenticador."


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class MfaActivateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class MfaActivateOut(BaseModel):
    backup_codes: list[str]


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=10, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)


class MessageOut(BaseModel):
    detail: str
