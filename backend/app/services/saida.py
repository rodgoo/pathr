"""A guarda das requisições que saem para endereços de TERCEIROS.

## Por que existe

Três lugares do app pedem uma URL que não foi digitada por nós nem por quem
usa: o leitor de artigo (`reader.py`), a checagem de link dos materiais
(`resource_search.py`) e a de ingressos dos eventos (`noticias.py`). Em todos,
a URL vem de uma busca de terceiros (Tavily, Brave) ou de um texto que a IA
leu — quer dizer, de fora.

Pedido de saída com endereço de fora é SSRF: quem controla o endereço faz o
NOSSO servidor bater onde quiser, inclusive no que só ele alcança — o metadata
da nuvem (169.254.169.254, que entrega credencial), a rede interna da Fly,
`localhost`. A resposta pode nem voltar para o atacante: basta a diferença
entre "respondeu" e "não respondeu" para varrer a rede interna.

O `reader.py` ganhou essa proteção; os outros dois ficaram sem, e a mesma
classe de defeito reapareceu em `noticias._reachable`. Por isso a validação
mora aqui, em um lugar só, e quem faz pedido de saída passa por aqui.

## O que ela faz, e por que não basta "conferir o host"

Conferir o nome e deixar o httpx conectar depois é DNS rebinding: o domínio do
atacante responde um IP público na checagem e um interno na conexão — duas
resoluções, duas respostas diferentes, e a segunda é a que vale.

Aqui a resolução é UMA. Valida-se o IP e conecta-se NELE, com `Host` e SNI
mantendo o domínio (para o servidor virtual certo responder e o certificado
TLS conferir). Cada redirecionamento repete tudo: um link público que
redireciona para 127.0.0.1 é barrado antes de o segundo pedido sair.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.services import reader

logger = logging.getLogger(__name__)

# Cinco saltos: o suficiente para encurtador + canônico + www, e pouco o
# bastante para um laço de redirecionamento não virar espera longa.
MAX_SALTOS = 5

_REDIRECIONAMENTOS = frozenset({301, 302, 303, 307, 308})
# Servidor que recusa HEAD mas serve GET: 405 é o certo, 403 e 501 aparecem na
# prática. Sem esta segunda tentativa, material bom seria descartado como link
# quebrado.
_RECUSA_HEAD = frozenset({403, 405, 501})


class EnderecoRecusado(Exception):
    """O endereço não é da internet pública — o pedido não deve sair."""


def destino_pinado(url: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Traduz a URL para `(alvo no IP validado, cabeçalho Host, extensões SNI)`.

    Usa a validação do `reader`, chamando-a pelo módulo (e não por um nome
    importado) para que um teste que troque `reader._resolver_e_validar` valha
    também aqui — a validação é uma só, de propósito.
    """
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise EnderecoRecusado(url)

    porta = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        ip = reader._resolver_e_validar(partes.hostname, porta)
    except reader.LeituraIndisponivel as erro:
        # O `reader` fala a língua da tela de leitura ("não consegui ler").
        # Aqui é decisão de rede, e quem chama não está lendo nada.
        raise EnderecoRecusado(url) from erro

    hospedeiro = f"[{ip}]" if ":" in ip else ip
    alvo = partes._replace(netloc=f"{hospedeiro}:{porta}").geturl()
    cabecalho = partes.hostname if porta in (80, 443) else f"{partes.hostname}:{porta}"
    return alvo, {"Host": cabecalho}, {"sni_hostname": partes.hostname}


async def _pedir(
    cliente: httpx.AsyncClient, metodo: str, url: str
) -> tuple[Optional[int], Optional[str]]:
    """Um pedido, já pinado. Devolve `(situação, destino do redirecionamento)`.

    `follow_redirects=False` sempre: deixar o httpx seguir o salto sozinho
    devolveria a ele a resolução do próximo endereço — que é exatamente o que
    esta guarda existe para impedir.
    """
    alvo, cabecalhos, extensoes = destino_pinado(url)
    if metodo == "HEAD":
        resposta = await cliente.head(
            alvo, headers=cabecalhos, extensions=extensoes, follow_redirects=False
        )
        return resposta.status_code, resposta.headers.get("location")
    async with cliente.stream(
        "GET", alvo, headers=cabecalhos, extensions=extensoes, follow_redirects=False
    ) as resposta:
        # `stream` para fechar assim que o status chega, sem baixar a página.
        return resposta.status_code, resposta.headers.get("location")


async def alcancavel(cliente: httpx.AsyncClient, url: str, saltos: int = MAX_SALTOS) -> bool:
    """A URL responde? HEAD primeiro, GET quando o servidor recusa HEAD.

    Endereço não público — no começo ou depois de um redirecionamento — é
    `False`, e nenhum pedido sai para ele.
    """
    atual = url
    for _ in range(saltos + 1):
        situacao: Optional[int] = None
        destino: Optional[str] = None

        try:
            situacao, destino = await _pedir(cliente, "HEAD", atual)
        except EnderecoRecusado:
            logger.debug("endereço recusado na saída: %s", atual)
            return False
        except httpx.HTTPError:
            # Tempo esgotado ou conexão derrubada: ainda vale o GET, porque há
            # servidor que simplesmente não atende HEAD.
            situacao = None

        if situacao is not None:
            if situacao in _REDIRECIONAMENTOS and destino:
                atual = urljoin(atual, destino)
                continue
            if situacao < 400:
                return True
            if situacao not in _RECUSA_HEAD:
                return False

        try:
            situacao, destino = await _pedir(cliente, "GET", atual)
        except EnderecoRecusado:
            logger.debug("endereço recusado na saída: %s", atual)
            return False
        except httpx.HTTPError as erro:
            logger.debug("link descartado %s: %s", atual, erro)
            return False

        if situacao in _REDIRECIONAMENTOS and destino:
            atual = urljoin(atual, destino)
            continue
        return situacao < 400

    logger.debug("redirecionou vezes demais: %s", url)
    return False
