"""Cliente Supabase do PathR.

Mesma abordagem do Notter (backend/app/database.py de lá), e pelo mesmo
motivo: o client — e o pool httpx embaixo dele — vive o processo inteiro,
então precisa aguentar duas falhas que aparecem sob uso real.

1. **Conexão keep-alive derrubada do lado do servidor.** De vez em quando o
   httpx reaproveita uma conexão exatamente quando o Supabase a está
   fechando, e o erro sobe como falha de transporte numa requisição que
   estava perfeitamente boa. `retries=3` no transporte cobre isso.

2. **429/503 com resposta bem formada.** `retries` não ajuda aqui: a
   requisição completou, só veio "volte depois". `_RetryingTransport` põe uma
   segunda camada com backoff limitado por cima.

O PathR usa a service_role key: ele é o único chamador confiável do banco
(o frontend só fala com esta API), então não é barrado pelo RLS, que fica
ligado e sem policies — negando por padrão qualquer acesso pelas chaves
anon/authenticated.

O projeto Supabase é exclusivo do PathR. A semelhança com o do Notter é de
código, não de credencial: as chaves são de outro projeto.
"""

import time
from functools import lru_cache

import httpx
from supabase import Client, create_client

from app.config import settings


class _RetryingTransport(httpx.HTTPTransport):
    """Repete uma resposta que pediu para esperar, com backoff exponencial."""

    _RETRY_STATUS_CODES = frozenset({429, 503})
    _MAX_RETRIES = 3

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = super().handle_request(request)
        for attempt in range(self._MAX_RETRIES):
            if response.status_code not in self._RETRY_STATUS_CODES:
                return response
            response.close()
            time.sleep(0.5 * (2**attempt))
            response = super().handle_request(request)
        return response


_RETRYING_TRANSPORT = _RetryingTransport(retries=3)


@lru_cache
def _client() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY não configurados — "
            "copie .env.example para .env.local e preencha."
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    # postgrest-py monta o próprio httpx.Client internamente e não expõe um
    # gancho para injetar transporte na construção; trocar depois do fato é o
    # único caminho. table() e rpc() dividem esta sessão, então uma troca cobre
    # os dois.
    client.postgrest.session._transport = _RETRYING_TRANSPORT
    return client


def get_supabase() -> Client:
    """Dependência do FastAPI e ponto único de acesso ao banco."""
    return _client()
