import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai_core import create_ai_core
from app.ai_core.providers.openai import OpenAIProvider
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.router import api_router
from app.api.routes import health
from app.core.config import (
    Settings,
    get_settings,
    validate_production_ai_config,
)
from app.core.logging import configure_logging
from app.db.session import create_engine_from_settings, create_session_factory
from app.domains.resume_ats.domain import wire_resume_ats
from app.domains.support_copilot.domain import wire_support_copilot

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    validate_production_ai_config(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # Error envelopes per docs/07_API_Design.md §10 (HTTP, validation,
    # and unhandled exceptions).
    register_error_handlers(app)
    app.state.settings = settings

    # Database foundation (docs/05_Database_Design.md, docs/09 §4).
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # Shared AI service layer (docs/09_Migration_Analysis.md §3.3).
    # Run records are persisted from day one via the DB-backed store.
    ai_core = create_ai_core(run_store=SQLAlchemyRunRecordStore(session_factory))
    # Provider clients are registered once at the platform level; each
    # domain only registers its own prompts, model config, and workflows.
    # The provider registry name, base URL, model, and thinking mode all
    # come from settings, and the API key is never logged or exposed.
    if settings.ai_api_key:
        ai_core.llm_factory.register_provider(
            settings.ai_provider_name,
            OpenAIProvider(
                api_key=settings.ai_api_key,
                base_url=settings.ai_base_url,
                timeout_seconds=settings.ai_timeout_seconds,
                thinking=settings.thinking_mode,
                reasoning_effort=settings.reasoning_effort,
            ),
        )
    wire_resume_ats(ai_core, settings)
    wire_support_copilot(ai_core, settings)
    app.state.ai_core = ai_core

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Outermost user middleware: assigns the request id and logs request
    # metadata for every response, including CORS preflight responses.
    app.add_middleware(RequestContextMiddleware)

    # Versioned API namespace (see docs/07_API_Design.md).
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Operational health checks, unversioned for uptime monitors and
    # load balancers. The same router is mounted under /api/v1 above.
    app.include_router(health.router, tags=["system"])

    logger.info(
        "application_startup service=%s version=%s environment=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    return app


app = create_app()
