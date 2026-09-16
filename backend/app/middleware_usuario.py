"""Anota quem está fazendo a requisição, para a cota de IA saber de quem é.

A IA é chamada fundo dentro dos serviços (`ai_providers._rotate`), sem acesso
à requisição, e a sessão é resolvida numa dependência síncrona — que o
FastAPI roda em outra thread, onde um `ContextVar` gravado se perde antes de
chegar à rota. Um middleware ASGI roda na MESMA tarefa que a rota inteira, e o
valor gravado aqui é visto por tudo que acontece depois.

Só decodifica o JWT, não confere a sessão no banco: o valor serve para CONTAR
uso, nunca para autorizar. Um token revogado ainda assinado contaria cota para
o próprio dono, e a rota recusa o pedido logo em seguida no `get_current_user`.
"""

from __future__ import annotations

from http.cookies import SimpleCookie

from app.deps import ACCESS_COOKIE
from app.security import decode_access_token
from app.services import idioma as idioma_do_app
from app.services.limites import usuario_da_requisicao

# O idioma da tela, que o front manda em toda requisição. É o que faz o texto
# que a IA escreve sair no mesmo idioma dos menus (app/services/idioma.py).
CABECALHO_DE_IDIOMA = "x-pathr-idioma"


def _token(scope) -> str | None:
    cabecalhos = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    autorizacao = cabecalhos.get("authorization", "")
    if autorizacao.lower().startswith("bearer "):
        return autorizacao[7:].strip() or None
    bruto = cabecalhos.get("cookie")
    if not bruto:
        return None
    try:
        biscoito = SimpleCookie()
        biscoito.load(bruto)
    except Exception:  # noqa: BLE001
        return None
    item = biscoito.get(ACCESS_COOKIE)
    return item.value if item else None


class UsuarioDaRequisicao:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        usuario = None
        token = _token(scope)
        if token:
            carga = decode_access_token(token)
            if carga and carga.get("sub"):
                usuario = str(carga["sub"])
        cabecalhos = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        escolhido = idioma_do_app.normalizar(cabecalhos.get(CABECALHO_DE_IDIOMA))

        marca = usuario_da_requisicao.set(usuario)
        marca_do_idioma = idioma_do_app.idioma_da_requisicao.set(escolhido)
        try:
            await self.app(scope, receive, send)
        finally:
            idioma_do_app.idioma_da_requisicao.reset(marca_do_idioma)
            usuario_da_requisicao.reset(marca)
