"""O domínio do e-mail existe e recebe mensagens?

## Por que olhar o DNS no cadastro

A validação de formato (`EmailStr`) aceita `ana@naoexiste-xyz.com`. Conta com
e-mail assim nunca confirma — mas o cadastro já gastou um envio de e-mail, uma
linha no banco e uma vaga no limite por IP de quem cadastrou de verdade. É o
jeito mais barato de encher o app de contas falsas. Perguntar ao DNS custa
milissegundos e corta isso na porta.

## A regra (RFC 5321 e RFC 7505)

- tem registro MX → recebe e-mail; exceto o "MX nulo" (um MX apontando para
  `.`), que é o domínio dizendo explicitamente que NÃO recebe;
- não tem MX, mas tem A/AAAA → pelo padrão, o e-mail vai para esse endereço;
- o domínio não existe (NXDOMAIN), ou não tem nem MX nem endereço → recusa.

## Quando o DNS falha

Tempo esgotado ou servidor de nomes fora: o cadastro PASSA. Recusar gente real
porque um resolvedor piscou é pior que deixar passar um domínio duvidoso — que
ainda precisa confirmar o e-mail para entrar, e a conta não confirmada é
apagada pela faxina (services/faxina.py).

## E-mail descartável

Domínios de caixa temporária (mailinator, 10minutemail…) existem e recebem —
é justamente para cadastro falso que servem. Ficam numa lista fixa, com os
subdomínios deles.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)

_TEMPO_LIMITE = 3.0
_CACHE_OK = 3600.0
_CACHE_RUIM = 600.0
_CACHE_MAX = 5000
_cache: dict[str, tuple[Optional[str], float]] = {}

NAO_EXISTE = "O domínio deste e-mail não existe. Confira o endereço."
NAO_RECEBE = "Este domínio não recebe e-mails. Use outro endereço."
DESCARTAVEL = "E-mail temporário não é aceito. Use um endereço seu, que você acessa."

DESCARTAVEIS = frozenset(
    """
    mailinator.com mailinator.net mailinator.org 10minutemail.com 10minutemail.net 10minemail.com
    guerrillamail.com guerrillamail.net guerrillamail.org guerrillamail.biz guerrillamailblock.com sharklasers.com
    grr.la pokemail.net spam4.me yopmail.com yopmail.net yopmail.fr cool.fr.nf jetable.fr.nf
    temp-mail.org temp-mail.io tempmail.com tempmail.net tempmailo.com tempmail.plus tempr.email
    throwawaymail.com trashmail.com trashmail.net trashmail.de trashmail.me mytrashmail.com
    getnada.com nada.email dispostable.com maildrop.cc mailnesia.com mailcatch.com mintemail.com
    fakeinbox.com fakemail.net emailondeck.com mohmal.com moakt.com burnermail.io 33mail.com
    mailpoof.com spamgourmet.com spambox.us incognitomail.org anonbox.net discard.email
    emailfake.com email-fake.com fakemailgenerator.com tmpmail.org tmpmail.net tmail.ws
    mail.tm mail.gw inboxkitten.com linshiyouxiang.net 1secmail.com 1secmail.net 1secmail.org
    esiix.com wwjmp.com xojxe.com yoggm.com mailto.plus fexpost.com fexbox.org rover.info
    dropmail.me emltmp.com 10mail.org harakirimail.com mailsac.com tempinbox.com
    spamdecoy.net mailexpire.com deadaddress.com mvrht.com instantemailaddress.com
    luxusmail.org owlymail.com zetmail.com vomoto.com crazymailing.com etempmail.com
    """.split()
)


def _dominio(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower().rstrip(".")


def e_descartavel(dominio: str) -> bool:
    partes = dominio.split(".")
    return any(".".join(partes[i:]) in DESCARTAVEIS for i in range(len(partes) - 1))


def _resolver(dominio: str, tipo: str) -> list[str]:
    """As respostas como texto. Levanta as exceções do dnspython."""
    resolvedor = dns.resolver.Resolver()
    resolvedor.lifetime = _TEMPO_LIMITE
    return [r.to_text() for r in resolvedor.resolve(dominio, tipo)]


def _consultar(dominio: str) -> Optional[str]:
    try:
        registros = _resolver(dominio, "MX")
        destinos = [r.split()[-1].rstrip(".") for r in registros]
        if destinos and all(destino == "" for destino in destinos):
            return NAO_RECEBE  # MX nulo: "0 ."
        return None
    except dns.resolver.NXDOMAIN:
        return NAO_EXISTE
    except dns.resolver.NoAnswer:
        pass  # sem MX: o padrão manda tentar o endereço do próprio domínio
    for tipo in ("A", "AAAA"):
        try:
            if _resolver(dominio, tipo):
                return None
        except dns.resolver.NXDOMAIN:
            return NAO_EXISTE
        except dns.resolver.NoAnswer:
            continue
    return NAO_RECEBE


def problema_do_email(email: str) -> Optional[str]:
    """None se o e-mail pode cadastrar; senão, a frase para a pessoa."""
    dominio = _dominio(email)
    if not dominio or "." not in dominio:
        return NAO_EXISTE
    if e_descartavel(dominio):
        return DESCARTAVEL

    agora = time.monotonic()
    guardado = _cache.get(dominio)
    if guardado and guardado[1] > agora:
        return guardado[0]
    try:
        problema = _consultar(dominio)
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        logger.info("DNS indisponível para validar um domínio de e-mail; cadastro segue")
        return None
    except dns.exception.DNSException:
        logger.info("consulta DNS falhou ao validar um domínio de e-mail; cadastro segue")
        return None

    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[dominio] = (problema, agora + (_CACHE_RUIM if problema else _CACHE_OK))
    return problema
