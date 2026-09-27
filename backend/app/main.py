from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import http_exception_handler
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # Error envelope per docs/07_API_Design.md §10.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Versioned API namespace (see docs/07_API_Design.md).
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Operational health check, unversioned.
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    return app


app = create_app()
