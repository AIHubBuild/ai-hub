"""API error handling.

Global HTTPException handler that emits the standardized error envelope
from `docs/07_API_Design.md` §10: ``{"success": false, "message": ...}``.
Raised dict details (e.g. from the auth dependency) pass through
untouched; string details are wrapped.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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
        headers=getattr(exc, "headers", None),
    )
