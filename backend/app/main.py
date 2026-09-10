"""Aplicação FastAPI do PathR.

Serve api.pathr.notter.com.br. O frontend (pathr.notter.com.br) é um SPA
estático e nunca fala com o Supabase direto — todo acesso a dado passa por
aqui, que é o que permite usar a service_role key com RLS negando tudo por
padrão.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.ai_providers import AiProviderError
from app.config import settings
from app.services import eventos

logger = logging.getLogger("pathr")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("PathR subindo em %s", settings.environment)
    yield
    logger.info("PathR encerrando")


app = FastAPI(
    title="PathR API",
    description="Plano de estudos pessoal gerado a partir do currículo.",
    version="0.1.0",
    lifespan=lifespan,
    # O schema interativo fica fora do ar em produção: ele descreve toda a
    # superfície de auth para quem estiver olhando, sem ganho para o app.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

class ErroInterno(BaseHTTPMiddleware):
    """Transforma exceção não tratada numa resposta JSON, DENTRO do CORS.

    Sem isto, uma exceção sobe até o tratador padrão do Starlette, que está
    FORA do CORSMiddleware — a resposta 500 sai sem `Access-Control-Allow-
    Origin`, o navegador a descarta antes de o JavaScript vê-la, e o `fetch`
    rejeita. Na tela isso vira "Não consegui falar com o servidor", que manda
    procurar problema de rede quando o problema é um erro nosso, com traceback
    e tudo, esperando no log.

    Foi exatamente o que aconteceu com a geração de roadmap: um NOT NULL
    violado virava, para quem usava, "verifique sua conexão".

    O detalhe da exceção NÃO vai para o cliente — ele pode conter nome de
    coluna, consulta e valor de outra pessoa. Vai para o log, que é onde se
    investiga.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:  # noqa: BLE001
            logger.exception("erro não tratado em %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Algo quebrou do nosso lado. Já registramos o erro."},
            )


# A ORDEM importa e é contraintuitiva: o último `add_middleware` é o mais
class AvisaOutrasTelas(BaseHTTPMiddleware):
    """Publica "algo mudou" depois de toda escrita bem-sucedida.

    Num middleware, e não em cada rota, de propósito. São mais de vinte
    endpoints de escrita hoje e o produto ganha outros a cada semana; uma
    chamada por rota é uma lista que envelhece calada — a rota nova nasce sem
    o aviso, os outros aparelhos param de ver aquela mudança, e ninguém
    descobre porque nada quebra. Aqui a regra é uma só: método que muda coisa
    + resposta de sucesso + sessão identificada.

    A verificação de sessão NÃO é refeita: quem já a fez foi a dependência da
    rota, que deixou o id em `request.state`. Requisição anônima simplesmente
    não tem o campo, e não publica.
    """

    # `/auth/refresh` renova a sessão a cada 30 minutos, em todo aparelho, e
    # não muda nada que uma tela mostre. Publicá-lo faria cada renovação
    # disparar uma rodada de reconsultas em todos os outros aparelhos.
    IGNORADAS = ("/auth/refresh",)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return response
        if not (200 <= response.status_code < 300):
            return response
        if request.url.path.startswith(self.IGNORADAS):
            return response
        user_id = getattr(request.state, "pathr_user_id", "")
        if not user_id:
            return response
        # `origem` volta no aviso para o autor da escrita se reconhecer e
        # ignorar: ele já atualizou a própria tela.
        await eventos.publicar(
            user_id,
            request.url.path,
            request.headers.get("x-pathr-client", ""),
        )
        return response


# EXTERNO. O CORS precisa ficar por fora do tratador acima, para poder
# carimbar o cabeçalho na resposta que ele devolve.
app.add_middleware(ErroInterno)
app.add_middleware(AvisaOutrasTelas)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Obrigatório: a sessão vive em cookie, e sem isso o navegador não o envia.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    # `X-Pathr-Client` identifica a ABA que fez a escrita, para o aviso de
    # volta poder ser ignorado por ela mesma.
    allow_headers=["Authorization", "Content-Type", "X-Pathr-Client"],
    # Sem isto o navegador esconde do JavaScript qualquer cabeçalho que não
    # seja da lista segura do CORS, e o site (pathr.notter.com.br) fala com
    # outra origem (api.pathr.notter.com.br). Os dois abaixo carregam decisões
    # de tela: sem expô-los, o login com segundo fator nunca mostrava o campo
    # de código, e o e-mail não confirmado apareceria como erro genérico.
    expose_headers=["X-Pathr-Mfa", "X-Pathr-Unverified"],
)


@app.exception_handler(AiProviderError)
async def ai_provider_error_handler(_request: Request, exc: AiProviderError):
    """503, não 500: o app está de pé, o que faltou foi cota de terceiro.
    `.detail` é escrito para ser lido pelo usuário e nunca traz corpo de erro
    do provedor."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """Uma frase em português no lugar do array de erros do Pydantic — o
    frontend mostra `detail` direto, sem ter que interpretar o formato."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "query"))
    message = first.get("msg", "dados inválidos")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"{field}: {message}" if field else message},
    )


from app import health  # noqa: E402
from app.routers import (  # noqa: E402
    auth,
    eventos as eventos_router,
    explanations,
    languages,
    library,
    profile,
    quizzes,
    resumes,
    roadmap,
    tags,
)


@app.on_event("startup")
async def _abre_canal_de_avisos() -> None:
    """O ouvinte entre máquinas. Não sobe em teste nem sem banco: `iniciar`
    checa isso, e uma falha de conexão lá dentro degrada para avisos só desta
    máquina em vez de derrubar o boot."""
    eventos.iniciar_listener()


@app.on_event("shutdown")
async def _fecha_canal_de_avisos() -> None:
    await eventos.parar_listener()


app.include_router(health.router)
app.include_router(eventos_router.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(resumes.router)
app.include_router(tags.router)
app.include_router(roadmap.router)
app.include_router(library.router)
app.include_router(quizzes.router)
app.include_router(languages.router)
app.include_router(explanations.router)
