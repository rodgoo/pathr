"""O que separa um cadastro de pessoa de um cadastro de script.

Contas falsas em série servem para uma coisa: gastar o que o app tem de
limitado — envio de e-mail, linhas no banco, cota de IA de quem confirma. As
travas, da mais barata para a mais cara, e cada uma pega um tipo de ataque:

1. **Campo isca** (`website`): invisível para quem usa a tela, preenchido por
   robô que completa todo campo de formulário. Preenchido, a resposta é a de
   sucesso — o robô não aprende que foi pego — e nada é criado.
2. **Limites** (services/limites.py): por IP (hora e dia), pela FAIXA do IP
   (um /24 ou /48 — trocar de IP dentro da mesma rede não escapa) e um teto
   global, contado só quando a conta vai mesmo ser criada.
3. **Domínio do e-mail** (services/email_dominio.py): o domínio precisa existir
   e receber e-mail, e caixa temporária não entra.
4. **Turnstile** (opcional): o desafio da Cloudflare, ligado quando a chave
   secreta está configurada.
5. **Confirmação obrigatória**: conta sem e-mail confirmado não entra, não usa
   nada, e é apagada em 3 dias pela faxina (services/faxina.py).
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

_TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
ROBO = "Não conseguimos confirmar que você não é um robô. Recarregue a página e tente de novo."


def conferir_turnstile(token: str, ip: Optional[str]) -> None:
    """Recusa com 400 se o Turnstile está ligado e o token não vale.

    A Cloudflare fora do ar não trava o cadastro: as outras travas continuam
    valendo, e recusar gente real por uma queda de terceiro é pior.
    """
    if not settings.turnstile_secret_key:
        return
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ROBO)
    dados = {"secret": settings.turnstile_secret_key, "response": token[:4096]}
    if ip:
        dados["remoteip"] = ip
    try:
        resposta = httpx.post(_TURNSTILE, data=dados, timeout=5.0)
        valido = resposta.status_code == 200 and resposta.json().get("success") is True
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile indisponível; cadastro segue com as outras travas")
        return
    if not valido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ROBO)
