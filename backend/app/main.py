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

from app.ai_providers import AiProviderError
from app.config import settings

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Obrigatório: a sessão vive em cookie, e sem isso o navegador não o envia.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
from app.routers import auth, english, library, profile, quizzes, resumes, roadmap, tags  # noqa: E402

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(resumes.router)
app.include_router(tags.router)
app.include_router(roadmap.router)
app.include_router(library.router)
app.include_router(quizzes.router)
app.include_router(english.router)
