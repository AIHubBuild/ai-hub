"""Operational health endpoints.

``/health`` is a liveness probe: it only verifies that the process is
serving requests and never touches the database or the AI provider.
``/ready`` is a readiness probe: it runs a single ``SELECT 1`` against
the application database and returns 503 when the database is
unavailable. Neither endpoint exposes connection strings, credentials,
or exception details.

Both routes are mounted unversioned (``/health``, ``/ready``) and under
the versioned API (``/api/v1/health``, ``/api/v1/ready``).
"""

import asyncio
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_app_settings

logger = logging.getLogger(__name__)

router = APIRouter()

_CACHE_HEADERS = {"Cache-Control": "no-store"}
READINESS_TIMEOUT_SECONDS = 2.0


def _base_payload(settings: Settings, status: str) -> dict:
    return {
        "status": status,
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


def _check_database(engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@router.get("/health")
async def health(request: Request, response: Response) -> dict:
    """Liveness: the process is up. No dependency checks."""
    settings = get_app_settings(request)
    response.headers.update(_CACHE_HEADERS)
    return _base_payload(settings, "ok")


@router.head("/health", include_in_schema=False)
async def health_head() -> Response:
    """HEAD support for uptime monitors.

    Returns the same success status and cache headers as GET with an
    empty body. FastAPI does not add HEAD automatically to GET routes.
    """
    return Response(status_code=200, headers=_CACHE_HEADERS)


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness: the database answers a trivial bounded query."""
    settings = get_app_settings(request)
    try:
        await asyncio.wait_for(
            run_in_threadpool(_check_database, request.app.state.engine),
            timeout=READINESS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        # Log the type only; driver errors can include connection details
        # and timeout responses must not expose exception details.
        logger.warning(
            "readiness_check_failed error_type=%s", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content=_base_payload(settings, "unavailable"),
            headers=_CACHE_HEADERS,
        )

    return JSONResponse(
        content=_base_payload(settings, "ok"), headers=_CACHE_HEADERS
    )
