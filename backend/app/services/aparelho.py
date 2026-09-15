"""O aparelho de uma sessão, dito como a pessoa reconhece: "Chrome no Windows".

O `User-Agent` cru ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit…")
não diz nada para quem olha a lista de sessões. Aqui ele vira navegador e
sistema, que é o que basta para responder "esse aqui sou eu?".

A ordem das regras importa: Edge, Opera e Samsung Internet se anunciam também
como Chrome, e o Chrome se anuncia também como Safari — o mais específico vem
antes. Brave não se identifica no cabeçalho e aparece como Chrome; é limitação
do navegador, não daqui.
"""

import re
from typing import Optional

_NAVEGADORES = (
    (re.compile(r"\bEdg(?:e|A|iOS)?/"), "Edge"),
    (re.compile(r"\bOPR/|\bOpera\b"), "Opera"),
    (re.compile(r"\bSamsungBrowser/"), "Samsung Internet"),
    (re.compile(r"\bFirefox/|\bFxiOS/"), "Firefox"),
    (re.compile(r"\bCriOS/|\bChrome/"), "Chrome"),
    (re.compile(r"\bVersion/[\d.]+.*Safari/"), "Safari"),
)

_SISTEMAS = (
    (re.compile(r"\biPhone\b"), "iPhone"),
    (re.compile(r"\biPad\b"), "iPad"),
    (re.compile(r"\bAndroid\b"), "Android"),
    (re.compile(r"\bWindows\b"), "Windows"),
    (re.compile(r"\bMac OS X\b|\bMacintosh\b"), "macOS"),
    (re.compile(r"\bCrOS\b"), "ChromeOS"),
    (re.compile(r"\bLinux\b"), "Linux"),
)


def navegador(user_agent: Optional[str]) -> str:
    texto = user_agent or ""
    return next((nome for padrao, nome in _NAVEGADORES if padrao.search(texto)), "Navegador desconhecido")


def sistema(user_agent: Optional[str]) -> str:
    texto = user_agent or ""
    return next((nome for padrao, nome in _SISTEMAS if padrao.search(texto)), "sistema desconhecido")


def celular(user_agent: Optional[str]) -> bool:
    return sistema(user_agent) in ("iPhone", "Android")


def descrever(user_agent: Optional[str]) -> str:
    """"Chrome no Windows", "Safari no iPhone"."""
    return f"{navegador(user_agent)} no {sistema(user_agent)}"


def assinatura(user_agent: Optional[str]) -> str:
    """O que conta como "o mesmo aparelho" para o aviso de novo acesso.

    Navegador + sistema, e não o User-Agent inteiro: o número de versão muda a
    cada atualização do Chrome, e um aviso de "novo acesso" por atualização
    ensinaria a pessoa a ignorar o e-mail que um dia importa.
    """
    return f"{navegador(user_agent)}|{sistema(user_agent)}"


def ip_mascarado(ip: Optional[str]) -> Optional[str]:
    """IPv4 sem o último bloco, IPv6 só com os três primeiros grupos.

    Suficiente para a pessoa ver "é da minha rede ou não", sem transformar a
    tela (ou o e-mail) num registro exato de onde ela estava.
    """
    if not ip:
        return None
    if ":" in ip:
        grupos = [g for g in ip.split(":") if g]
        return ":".join(grupos[:3]) + ":…" if grupos else None
    partes = ip.split(".")
    return ".".join(partes[:3]) + ".…" if len(partes) == 4 else None
