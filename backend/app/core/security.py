"""Authentication & authorization primitives.

Validates Supabase-issued JWT access tokens for protected endpoints,
per `docs/07_API_Design.md` §6. Two signing modes are supported, kept
strictly separate to prevent algorithm-confusion attacks:

- ``ES256`` (current Supabase default): ECC P-256 public keys resolved
  from the project's published JWKS. Issuer and audience are validated.
- ``HS256`` (legacy): the project's legacy shared JWT secret, retained
  only for verifying older tokens already in circulation. The secret is
  never used to verify ES256 tokens, and public keys are never used to
  verify HS256 tokens.

Both modes require the ``sub`` claim; expiry is enforced by PyJWT.
"""

import time

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK, PyJWKClientError
from jwt.exceptions import InvalidTokenError, PyJWTError
from pydantic import BaseModel

from app.core.config import Settings, get_app_settings
from app.core.secrets import SecretError, require_secret

HS256 = "HS256"
ES256 = "ES256"

SUPABASE_AUDIENCE = "authenticated"
JWKS_PATH = "auth/v1/.well-known/jwks.json"
JWKS_CACHE_TTL_SECONDS = 300

_bearer_scheme = HTTPBearer(auto_error=False)

# In-memory JWKS cache: url -> (fetched_at, json). Tests inject canned
# responses by patching _fetch_jwks_json.
_jwks_cache: dict[str, tuple[float, dict]] = {}


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


def _fetch_jwks_json(jwks_url: str) -> dict:
    """Fetch the JWKS document. Test seam — never called with live
    credentials in the automated suite."""
    response = httpx.get(jwks_url, timeout=10.0)
    response.raise_for_status()
    return response.json()


def _get_jwks(jwks_url: str) -> dict:
    now = time.monotonic()
    cached = _jwks_cache.get(jwks_url)
    if cached is not None and now - cached[0] < JWKS_CACHE_TTL_SECONDS:
        return cached[1]
    document = _fetch_jwks_json(jwks_url)
    _jwks_cache[jwks_url] = (now, document)
    return document


def _es256_settings(settings: Settings) -> tuple[str, str]:
    """Return (issuer, jwks_url) derived from the configured Supabase URL."""
    jwks_url = settings.supabase_jwks_url
    if not jwks_url:
        if not settings.supabase_url:
            raise SecretError("supabase_url")
        base = settings.supabase_url.rstrip("/")
        jwks_url = f"{base}/{JWKS_PATH}"
    base_url = settings.supabase_url.rstrip("/") if settings.supabase_url else ""
    issuer = f"{base_url}/auth/v1"
    return issuer, jwks_url


def _es256_public_key(jwks_url: str, token: str):
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except PyJWTError:
        return None
    if not kid:
        return None
    document = _get_jwks(jwks_url)
    for jwk in document.get("keys", []):
        if jwk.get("kid") == kid and jwk.get("kty") == "EC":
            try:
                return PyJWK.from_dict(jwk).key
            except PyJWTError:
                continue
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_app_settings),
) -> AuthUser:
    """FastAPI dependency: validate the Bearer token and return the user.

    Raises 401 (envelope-shaped via app/api/errors.py) when the token is
    missing, malformed, expired, signed with the wrong key, or signed
    with an unsupported algorithm.
    """
    if credentials is None:
        raise _auth_error("Authentication required.")

    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError:
        raise _auth_error("Invalid or expired authentication token.")

    algorithm = header.get("alg")

    if algorithm == HS256:
        # Legacy tokens: HMAC with the project's legacy shared secret.
        try:
            secret = require_secret(settings, "supabase_jwt_secret")
        except SecretError:
            raise _auth_error("Authentication required.")
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[HS256],
                options={"require": ["sub"]},
            )
        except InvalidTokenError:
            raise _auth_error("Invalid or expired authentication token.")

    elif algorithm == ES256:
        # Current tokens: ECC P-256 signature against the project JWKS,
        # with issuer and audience validation.
        try:
            issuer, jwks_url = _es256_settings(settings)
        except SecretError:
            raise _auth_error("Authentication required.")
        try:
            key = _es256_public_key(jwks_url, token)
            if key is None:
                raise _auth_error("Invalid or expired authentication token.")
            payload = jwt.decode(
                token,
                key,
                algorithms=[ES256],
                options={"require": ["sub"]},
                issuer=issuer,
                audience=SUPABASE_AUDIENCE,
            )
        except (InvalidTokenError, PyJWKClientError, httpx.HTTPError):
            raise _auth_error("Invalid or expired authentication token.")

    else:
        raise _auth_error("Invalid or expired authentication token.")

    sub = payload.get("sub")
    return AuthUser(
        id=sub,
        email=payload.get("email"),
    )
