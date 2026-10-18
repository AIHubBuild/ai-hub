"""Request correlation and access logging.

Every request receives a fresh ``X-Request-ID`` that is echoed in the
response and attached to log records. Only metadata is logged: method,
route template, status, duration, and request id. Query strings, headers,
bodies, prompts, model output, and credentials are never logged.

Route templates are used instead of concrete paths so resource
identifiers in path parameters are not written to logs.
"""

import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "<unmatched>"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id and emit one metadata-only access log line."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        request.state.request_started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = int(
            (time.perf_counter() - request.state.request_started_at) * 1000
        )
        response.headers["X-Request-ID"] = request_id

        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        logger.log(
            level,
            "request method=%s route=%s status=%s duration_ms=%d request_id=%s",
            request.method,
            route_template(request),
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
