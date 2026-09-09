"""E-mail transacional via Brevo, na conta do próprio PathR.

Só dois e-mails existem hoje — confirmação de cadastro e recuperação de senha
— e os dois são links. Por isso o corpo é HTML mínimo e escrito à mão em vez
de template engine: um template a mais para manter não paga por dois e-mails.

Sem `brevo_api_key` configurada, `_send` registra no log e devolve False em
vez de levantar. Isso mantém o app usável num clone novo (dá para cadastrar,
o link aparece no log do servidor) e garante que uma falha de e-mail nunca
derrube o cadastro em si.
"""

import logging
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger("pathr.email")

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 10


def _send(to_email: str, to_name: str, subject: str, html: str) -> bool:
    if not settings.brevo_api_key or not settings.brevo_from_email:
        logger.warning(
            "BREVO_API_KEY ausente — e-mail %r para %s não foi enviado. Conteúdo: %s",
            subject,
            to_email,
            html,
        )
        return False
    try:
        response = httpx.post(
            _BREVO_URL,
            headers={"api-key": settings.brevo_api_key, "content-type": "application/json"},
            json={
                "sender": {"email": settings.brevo_from_email, "name": settings.brevo_sender_name},
                "to": [{"email": to_email, "name": to_name or to_email}],
                "subject": subject,
                "htmlContent": html,
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.error("Falha de rede ao enviar e-mail para %s: %s", to_email, exc)
        return False
    if response.status_code >= 400:
        logger.error("Brevo recusou o e-mail para %s: HTTP %s", to_email, response.status_code)
        return False
    return True


def _layout(heading: str, body: str, button_label: str, url: str) -> str:
    """Um HTML só, com estilo inline — cliente de e-mail ignora <style>."""
    return f"""
<div style="font-family:Inter,Arial,sans-serif;background:#161826;color:#e9e9ed;padding:32px">
  <div style="max-width:520px;margin:0 auto;background:#1b1d2b;border-radius:14px;padding:28px">
    <div style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#9184d9">PathR</div>
    <h1 style="font-size:22px;font-weight:500;margin:12px 0 8px">{heading}</h1>
    <p style="font-size:14px;line-height:1.6;color:rgba(233,233,237,.8);margin:0 0 20px">{body}</p>
    <a href="{url}"
       style="display:inline-block;padding:10px 18px;border-radius:8px;border:1px solid #9184d9;
              color:#9184d9;text-decoration:none;font-size:14px">{button_label}</a>
    <p style="font-size:12px;color:rgba(233,233,237,.45);margin:22px 0 0;line-height:1.5">
      Se o botão não funcionar, copie este endereço no navegador:<br>
      <span style="color:rgba(233,233,237,.6);word-break:break-all">{url}</span>
    </p>
  </div>
</div>
""".strip()


def send_verification_email(to_email: str, to_name: str, token: str) -> bool:
    url = f"{settings.frontend_url}/confirmar-email?token={quote(token)}"
    return _send(
        to_email,
        to_name,
        "Confirme seu e-mail no PathR",
        _layout(
            "Confirme seu e-mail",
            "Falta um passo para liberar seu plano de estudos. O link vale por 3 dias.",
            "Confirmar e-mail",
            url,
        ),
    )


def send_password_reset(to_email: str, to_name: str, token: str) -> bool:
    url = f"{settings.frontend_url}/nova-senha?token={quote(token)}"
    return _send(
        to_email,
        to_name,
        "Recuperação de senha do PathR",
        _layout(
            "Defina uma nova senha",
            "Você pediu para redefinir sua senha. O link vale por 1 hora. "
            "Se não foi você, ignore este e-mail — nada muda.",
            "Criar nova senha",
            url,
        ),
    )
