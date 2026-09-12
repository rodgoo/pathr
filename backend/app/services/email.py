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

from html import escape

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


# ---------------------------------------------------------------------------
# Avisos do plano de estudo
#
# Os três saem do disparo horário (routers/jobs.py) e respeitam as preferências
# da aba "Avisos e privacidade". Cada um só é enviado quando tem o que dizer:
# um lembrete de uma lista vazia, ou um resumo de uma semana sem nada, treina a
# pessoa a ignorar o remetente.
# ---------------------------------------------------------------------------


def _lista(itens: list[str]) -> str:
    linhas = "".join(
        f'<li style="margin-bottom:6px">{escape(item)}</li>' for item in itens[:6]
    )
    return f'<ul style="padding-left:18px;margin:12px 0">{linhas}</ul>'


def send_daily_plan(to_email: str, to_name: str, pendentes: list[str], minutos: int) -> bool:
    """O que falta hoje, com o tempo que isso leva."""
    quantos = len(pendentes)
    corpo = (
        f"Faltam {quantos} {'item' if quantos == 1 else 'itens'} no seu plano desta semana — "
        f"cerca de {minutos} minutos:{_lista(pendentes)}"
        "Começar pelo primeiro já mantém a sequência de pé."
    )
    return _send(
        to_email,
        to_name,
        "Seu plano de estudo de hoje",
        _layout("Bom dia!", corpo, "Abrir o plano", settings.frontend_url),
    )


def send_weekly_summary(
    to_email: str, to_name: str, feitos: int, total: int, minutos: int, streak: int
) -> bool:
    """A semana que passou, em números que a pessoa reconhece."""
    horas = round(minutos / 60, 1)
    corpo = (
        f"Na semana passada você concluiu <strong>{feitos} de {total}</strong> itens do plano "
        f"e estudou <strong>{horas}h</strong>."
        + (f" Sua sequência está em <strong>{streak} dias</strong>." if streak else "")
        + "<br><br>A semana nova já está montada, no seu nível atual."
    )
    return _send(
        to_email,
        to_name,
        "Como foi a sua semana de estudo",
        _layout("Resumo da semana", corpo, "Ver a semana nova", settings.frontend_url),
    )


def send_streak_at_risk(to_email: str, to_name: str, streak: int) -> bool:
    """O aviso da noite. Só vai para quem tem sequência viva e não estudou hoje."""
    corpo = (
        f"Você está há <strong>{streak} {'dia' if streak == 1 else 'dias'}</strong> seguidos "
        "estudando e ainda não marcou nada hoje. Quinze minutos bastam para manter a sequência."
    )
    return _send(
        to_email,
        to_name,
        "Sua sequência de estudo está em risco",
        _layout("Ainda dá tempo", corpo, "Estudar agora", settings.frontend_url),
    )
