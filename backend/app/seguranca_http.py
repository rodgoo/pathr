"""Cabeçalhos de segurança em toda resposta da API.

A API respondia sem nenhum. Na maior parte do tempo ela devolve JSON e isso
passa despercebido, mas ela também devolve arquivos que USUÁRIOS enviaram —
foto de perfil, foto anexada a um relato. Sem `nosniff`, o navegador pode
"adivinhar" que um arquivo declarado como imagem é HTML e executá-lo na origem
da API, que é vizinha do site (`*.pathr.notter.com.br`). O upload confere a
assinatura dos bytes; este cabeçalho é a segunda barreira, para o dia em que a
primeira falhar.

Os outros:

- `Content-Security-Policy: default-src 'none'` — a API não serve página
  nenhuma em produção (a documentação interativa fica desligada). Se algum
  dia uma resposta for interpretada como HTML, ela não carrega nem roda nada.
- `frame-ancestors 'none'` / `X-Frame-Options` — nada da API é para ficar
  dentro de um quadro de outro site.
- `Strict-Transport-Security` — só HTTPS, e o navegador lembra disso.
- `Referrer-Policy: no-referrer` — os endereços da API carregam ids, e não há
  motivo para eles irem parar em log de terceiro.
- `Cross-Origin-Resource-Policy: same-site` — as imagens da API só podem ser
  embutidas pelo próprio site, não por qualquer página que conheça a URL.

Em desenvolvimento a CSP fica de fora: `/docs` usa scripts de CDN, e ela o
quebraria.
"""

from __future__ import annotations

from app.config import settings

_SEMPRE = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-site"),
]

_PRODUCAO = [
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
]


class CabecalhosDeSeguranca:
    def __init__(self, app):
        self.app = app
        self.extras = _SEMPRE + (_PRODUCAO if settings.is_production else [])

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def com_cabecalhos(mensagem):
            if mensagem.get("type") == "http.response.start":
                existentes = {nome.lower() for nome, _ in mensagem.get("headers", [])}
                # Não sobrescreve o que a rota decidiu de propósito.
                mensagem["headers"] = list(mensagem.get("headers", [])) + [
                    (nome, valor) for nome, valor in self.extras if nome not in existentes
                ]
            await send(mensagem)

        await self.app(scope, receive, com_cabecalhos)
