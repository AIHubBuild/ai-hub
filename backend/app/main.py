from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai_core import create_ai_core
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.api.errors import http_exception_handler
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine_from_settings, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # Error envelope per docs/07_API_Design.md §10.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Database foundation (docs/05_Database_Design.md, docs/09 §4).
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # Shared AI service layer (docs/09_Migration_Analysis.md §3.3).
    # Run records are persisted from day one via the DB-backed store.
    app.state.ai_core = create_ai_core(
        run_store=SQLAlchemyRunRecordStore(session_factory)
    )

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
