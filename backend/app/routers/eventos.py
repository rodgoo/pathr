"""O canal que avisa as telas abertas de que algo mudou.

Server-Sent Events, e não WebSocket, porque o tráfego é de mão única: o
servidor empurra "reconsulte", o cliente já tem HTTP para escrever. SSE roda
sobre a mesma conexão HTTP, atravessa o Caddy e a Fly sem configuração
especial, reconecta sozinho no navegador (`EventSource`) e reaproveita o
cookie de sessão. Um WebSocket traria upgrade de protocolo, um segundo
caminho de autenticação e um segundo jeito de as coisas quebrarem, para
entregar exatamente a mesma coisa.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.deps import get_current_user
from app.services import eventos

logger = logging.getLogger("pathr.eventos")

router = APIRouter(tags=["eventos"])

# Um comentário SSE (linha iniciada por ":") de tempos em tempos.
#
# Sem ele, um proxy ou um NAT no caminho fecha uma conexão sem tráfego, e o
# navegador só descobre no próximo evento — que nunca chega. O batimento
# também é o que faz o `EventSource` perceber a queda e reconectar.
BATIMENTO_S = 20

# Quanto tempo uma conexão vive antes de o servidor pedir para reabrir.
#
# Existe por causa da hospedagem: a Fly suspende a máquina quando não há
# requisição em voo, e um SSE aberto é uma requisição em voo — um celular
# esquecido aberto seguraria a máquina no ar indefinidamente. Fechando de
# tempos em tempos, a máquina consegue suspender nos intervalos. O cliente
# reabre sozinho; para quem usa, nada acontece.
VIDA_MAXIMA_S = 15 * 60


def _sse(dados: dict[str, Any]) -> str:
    return f"data: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.get("/events")
async def stream(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    """Abre o canal de avisos do usuário autenticado."""
    user_id = str(user["id"])
    fila = eventos.inscrever(user_id)

    async def gerar() -> AsyncIterator[str]:
        # O primeiro evento sai imediatamente: ele confirma ao cliente que o
        # canal está de pé. Sem isso, uma conexão que morre antes do primeiro
        # aviso é indistinguível de uma conexão saudável e silenciosa.
        yield _sse({"rota": "", "origem": "", "aberto": True})
        restante = VIDA_MAXIMA_S
        try:
            while restante > 0:
                if await request.is_disconnected():
                    break
                try:
                    evento = await asyncio.wait_for(fila.get(), timeout=BATIMENTO_S)
                except asyncio.TimeoutError:
                    restante -= BATIMENTO_S
                    yield ": batimento\n\n"
                    continue
                yield _sse(evento)
        except asyncio.CancelledError:
            raise
        finally:
            eventos.cancelar(user_id, fila)

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # O Caddy e a Fly não bufferizam SSE, mas um proxy no meio do
            # caminho pode — e um evento retido no buffer é um evento perdido.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
