"""Formatos de entrada e saída da autenticação."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# Limites de idade do cadastro. O piso existe porque abaixo dele o tratamento
# de dados de menor exige consentimento de responsável, que este app não
# coleta. O teto é só sanidade: pega o dedo que digitou 1902 em vez de 1992.
IDADE_MINIMA = 14
IDADE_MAXIMA = 110


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    birth_date: date
    city: str = Field(min_length=2, max_length=120)
    # UF no Brasil; para outros países o próprio campo aceita o nome da região.
    state: str = Field(min_length=2, max_length=60)
    country: str = Field(default="BR", min_length=2, max_length=2)

    @field_validator("birth_date")
    @classmethod
    def _idade_plausivel(cls, valor: date) -> date:
        hoje = date.today()
        if valor > hoje:
            raise ValueError("A data de nascimento não pode estar no futuro.")
        # Idade em anos completos: subtrair só os anos erra por um dia quando
        # o aniversário ainda não chegou no ano corrente.
        idade = hoje.year - valor.year - ((hoje.month, hoje.day) < (valor.month, valor.day))
        if idade < IDADE_MINIMA:
            raise ValueError(f"É preciso ter ao menos {IDADE_MINIMA} anos para criar uma conta.")
        if idade > IDADE_MAXIMA:
            raise ValueError("Confira a data de nascimento.")
        return valor

    @field_validator("country")
    @classmethod
    def _pais_maiusculo(cls, valor: str) -> str:
        return valor.upper()


class ResendVerificationRequest(BaseModel):
    """Reenvio pedido de fora da sessão.

    Existe porque o login passou a exigir e-mail confirmado: quem não
    confirmou não consegue entrar, e sem esta rota não teria como pedir outro
    link — ficaria trancado do lado de fora com a conta criada.
    """

    email: EmailStr


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
