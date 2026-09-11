"""Chave de acesso: o domínio, a origem e o nome que cada chave recebe.

Pequeno de propósito. A cerimônia WebAuthn (gerar opções, conferir assinatura,
origem, domínio e contador) é da py_webauthn — criptografia de autenticação
não é lugar para reimplementar. O que sobra para o app decidir mora aqui.
"""

from urllib.parse import urlparse

from app.config import settings


def rp_id() -> str:
    """O domínio a que as chaves ficam presas.

    O host do site, e não da API: a cerimônia acontece no navegador, em
    pathr.notter.com.br, e o navegador só entrega a chave para o domínio em
    que ela foi criada. É isso que torna a chave inútil numa página falsa.
    """
    configurado = settings.webauthn_rp_id.strip()
    if configurado:
        return configurado
    return urlparse(settings.frontend_url).hostname or "localhost"


def origem() -> str:
    """A origem que o navegador declara dentro da assinatura: o site."""
    endereco = urlparse(settings.frontend_url)
    return f"{endereco.scheme}://{endereco.netloc}"


# A ordem importa: o User-Agent do Chrome também diz "Safari", o do Edge diz
# "Chrome", e o do iPhone diz "Mac OS X". O mais específico vem primeiro.
_NAVEGADORES = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("FxiOS/", "Firefox"),
    ("Firefox/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SISTEMAS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "Mac"),
    ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)


def nome_do_aparelho(user_agent: str) -> str:
    """Um nome que a pessoa reconheça na lista: "Chrome no Windows".

    Heurística de User-Agent, e só para o rótulo — nunca para decidir nada de
    segurança. Existe para a lista não virar "Chave de acesso" repetido cinco
    vezes, sem saber qual apagar quando um aparelho for perdido.
    """
    agente = user_agent or ""
    navegador = next((nome for marca, nome in _NAVEGADORES if marca in agente), None)
    sistema = next((nome for marca, nome in _SISTEMAS if marca in agente), None)
    if navegador and sistema:
        return f"{navegador} no {sistema}"
    return navegador or sistema or "Chave de acesso"
