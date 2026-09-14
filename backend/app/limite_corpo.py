"""Teto do tamanho de QUALQUER requisição, antes de uma rota ser chamada.

A rota de upload já lê com limite (services/upload.py), mas o Starlette monta
o formulário antes da rota — um corpo gigante chegava a ser recebido inteiro.
Pelo `Content-Length` a recusa sai sem ler nada. O navegador sempre manda o
cabeçalho num envio de formulário; um corpo sem ele continua limitado pela
leitura em blocos da rota.

ASGI puro, e não BaseHTTPMiddleware, para responder sem tocar no corpo.
"""

import json


class LimiteDeCorpo:
    def __init__(self, app, maximo_bytes: int) -> None:
        self.app = app
        self.maximo = maximo_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            tamanho = dict(scope.get("headers") or []).get(b"content-length")
            if tamanho is not None:
                try:
                    grande = int(tamanho) > self.maximo
                except ValueError:
                    grande = True
                if grande:
                    corpo = json.dumps({"detail": "Envio grande demais."}).encode()
                    await send({
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(corpo)).encode())],
                    })
                    await send({"type": "http.response.body", "body": corpo})
                    return
        await self.app(scope, receive, send)
