"""API error handling.

Global exception handlers that emit the standardized error envelope
from `docs/07_API_Design.md` §10: ``{"success": false, "message": ...}``.
Raised dict details (e.g. from the auth dependency) pass through
untouched; string details are wrapped. Unhandled exceptions become an
enveloped 500 so clients always receive a parseable error body.

Logging is metadata-only. Unhandled exceptions log the request id,
method, route template, duration, and exception type. Exception
messages, tracebacks, prompts, model output, and response bodies are
never logged because they can contain user content or credentials.
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import route_template

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _headers(request: Request, base: dict | None = None) -> dict:
    headers = dict(base or {})
    request_id = _request_id(request)
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"success": False, "message": str(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=_headers(request, getattr(exc, "headers", None)),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    message = str(exc.errors()[0].get("msg", "Request validation failed."))
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": message},
        headers=_headers(request),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    started = getattr(request.state, "request_started_at", None)
    duration_ms = (
        int((time.perf_counter() - started) * 1000) if started else -1
    )
    logger.error(
        "unhandled_exception method=%s route=%s status=500 duration_ms=%s "
        "request_id=%s exc_type=%s",
        request.method,
        route_template(request),
        duration_ms,
        _request_id(request) or "unknown",
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred.",
        },
        headers=_headers(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
