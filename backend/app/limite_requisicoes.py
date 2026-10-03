"""Teto geral de requisições por IP — defesa contra inundação (flood/DDoS) na camada de aplicação.

## Por que isto, já havendo `services/limites.py`

`limites.py` tem teto por AÇÃO sensível (cadastro, recuperação de senha, geração de quiz, cota de IA...), com
regra pensada para o abuso daquele fluxo específico, gravada no banco. Mas a maioria das rotas — leitura de
perfil, roadmap, a própria listagem de notícias — não tem regra nenhuma: um IP martelando qualquer uma delas
não esbarra em nada até a máquina da Fly saturar.

## Por que a API precisa disto, e o resto do app não tinha

`deploy/README.md` explica: o DNS de `api.pathr.notter.com.br` é propositalmente "cinza" (sem proxy da
Cloudflare), porque o proxy atrapalha o desafio ACME que a Fly usa para emitir o certificado. Sem a borda deles
na frente, não há WAF nem mitigação de DDoS de rede alguma — só o que a própria aplicação fizer. Isto aqui é
essa defesa: não substitui uma mitigação de borda de verdade contra um ataque volumétrico distribuído grande,
mas fecha o caso comum (um endereço, ou poucos, martelando a API) que hoje passa liso.

## Por que em memória, por processo, e não no banco como `limites.py`

Isto é defesa contra INUNDAÇÃO — o objetivo é responder rápido e sem gastar nada caro. Uma consulta ao Supabase
por requisição faria o próprio limite virar o gargalo: a mesma inundação que se quer barrar vira uma inundação
de escrita no banco. `client_ip` (`app/deps.py`) já é confiável na Fly — o `fly-client-ip` é escrito pelo proxy
deles a partir do IP de conexão, não pelo que o cliente manda. O custo de morar em memória é só a Fly rodar
mais de uma máquina ao mesmo tempo: cada uma conta por si, então o teto nominal vira um pouco mais folgado com
duas máquinas acordadas — nunca mais apertado, e nunca menos seguro.

## Por que ASGI puro, e não `BaseHTTPMiddleware`

Mesmo motivo de `LimiteDeCorpo`: a maioria das requisições (as normais, que não esbarram no teto) não pode
pagar o custo de montar uma `Response`/`Request` completos só para passar direto.
"""

from __future__ import annotations

import json
import time

from starlette.requests import Request

from app.deps import client_ip

# Generoso para uso real — a tela faz várias chamadas em paralelo ao abrir uma página — e apertado para
# inundação. Ajuste aqui se o uso legítimo algum dia esbarrar nele; ver o log de 429 em produção antes de
# só aumentar o número às cegas.
JANELA_S = 60
LIMITE_POR_JANELA = 240

# A Fly bate aqui a cada 30s (fly.toml) e monitoramento externo pode bater com frequência parecida: nunca
# podem ser a causa de um 429 que derruba o próprio health check.
ISENTAS = frozenset({"/health"})

# Teto de quantos IPs distintos ficam guardados ao mesmo tempo. Sem isto, um ataque que gira endereço a cada
# pedido (ou um botnet de verdade) faria este dicionário crescer sem fim — a defesa contra inundação virando
# ela mesma uma fuga de memória.
MAXIMO_DE_IPS = 20_000


class LimiteDeRequisicoes:
    def __init__(self, app) -> None:
        self.app = app
        # ip -> (janela de 60s em que a contagem vale, contagem nesta janela)
        self._janelas: dict[str, tuple[int, int]] = {}

    def _permitido(self, ip: str) -> bool:
        agora = int(time.time() // JANELA_S)
        janela, contagem = self._janelas.get(ip, (agora, 0))
        if janela != agora:
            # A janela virou: o endereço começa do zero, não soma com uma
            # contagem de 60s atrás.
            janela, contagem = agora, 0
        contagem += 1
        if ip not in self._janelas and len(self._janelas) >= MAXIMO_DE_IPS:
            # Despeja a entrada mais antiga (ordem de inserção do dict) em vez
            # de varrer por idade: sob inundação de verdade, rápido importa
            # mais que exato — o pior efeito é esquecer um IP legítimo uma
            # janela mais cedo, nunca deixar de proteger.
            self._janelas.pop(next(iter(self._janelas)), None)
        self._janelas[ip] = (janela, contagem)
        return contagem <= LIMITE_POR_JANELA

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in ISENTAS:
            await self.app(scope, receive, send)
            return

        ip = client_ip(Request(scope)) or "desconhecido"
        if self._permitido(ip):
            await self.app(scope, receive, send)
            return

        corpo = json.dumps({"detail": "Muitas requisições deste endereço. Tente de novo em instantes."}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corpo)).encode()),
                    (b"retry-after", str(JANELA_S).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})
