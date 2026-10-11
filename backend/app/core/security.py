"""Authentication & authorization primitives.

Validates Supabase-issued JWT access tokens for protected endpoints,
per `docs/07_API_Design.md` §6 (backend validates JWTs for protected
endpoints) and `docs/04_System_Architecture.md` §10. Tokens are
HS256-signed with the project's JWT secret; the ``sub`` claim carries
the Supabase user UUID.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import Settings, get_app_settings
from app.core.secrets import SecretError, require_secret

AUTH_ALGORITHMS = ["HS256"]

_bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    """Authenticated user identity extracted from a verified JWT."""

    id: str
    email: str | None = None


def _auth_error(message: str) -> HTTPException:
    # Detail is a dict so the global exception handler in app/api/errors.py
    # emits the docs/07_API_Design.md §10 envelope unchanged.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"success": False, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_app_settings),
) -> AuthUser:
    """FastAPI dependency: validate the Bearer token and return the user.

    Raises 401 (envelope-shaped via app/api/errors.py) when the token is
    missing, malformed, expired, or signed with the wrong secret.
    """
    if credentials is None:
        raise _auth_error("Authentication required.")

    try:
        secret = require_secret(settings, "supabase_jwt_secret")
    except SecretError:
        # Misconfiguration is a server problem, not a client problem;
        # still respond 401 to avoid leaking whether auth is configured.
        raise _auth_error("Authentication required.")

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=AUTH_ALGORITHMS,
            options={"require": ["sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise _auth_error("Invalid or expired authentication token.")
    except jwt.InvalidTokenError:
        raise _auth_error("Invalid or expired authentication token.")

    sub = payload.get("sub")
    return AuthUser(
        id=sub,
        email=payload.get("email"),
    )
