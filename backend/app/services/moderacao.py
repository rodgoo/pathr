"""Quem modera. Uma regra só, usada pela sessão e pelas rotas de relatos.

Duas cópias desta função — uma para a tela saber se mostra a caixa de
moderação, outra para a rota decidir se entrega os relatos — divergiriam na
primeira mudança, e a divergência seria justamente num controle de acesso.
"""

from typing import Any

from app.config import settings


def e_moderador(user: dict[str, Any]) -> bool:
    email = str(user.get("email") or "").strip().lower()
    return bool(email) and email in {m.strip().lower() for m in settings.moderator_emails}
