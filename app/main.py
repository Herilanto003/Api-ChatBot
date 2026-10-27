import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    AssistantProviderError,
    AssistantUnavailableError,
    ConversationNotFoundError,
)
from app.db.session import dispose_engine

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le schéma est géré par Alembic : aucune création de table au démarrage.
    yield
    await dispose_engine()


def register_exception_handlers(app: FastAPI) -> None:
    """Traduit les exceptions métier en réponses HTTP, sans fuite d'internes."""

    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found(
        request: Request,
        exc: ConversationNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Conversation introuvable."})

    @app.exception_handler(AssistantProviderError)
    async def assistant_provider_error(
        request: Request,
        exc: AssistantProviderError,
    ) -> JSONResponse:
        logger.warning("Erreur du fournisseur IA : %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "Le fournisseur IA est momentanément indisponible."},
        )

    @app.exception_handler(AssistantUnavailableError)
    async def assistant_unavailable(
        request: Request,
        exc: AssistantUnavailableError,
    ) -> JSONResponse:
        logger.error("Assistant IA indisponible : %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Le service IA est indisponible."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # Le détail (trace de pile incluse) reste dans les logs serveur.
        logger.exception("Erreur inattendue sur %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Une erreur interne est survenue."},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
