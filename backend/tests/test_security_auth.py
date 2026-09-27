"""Tests for the JWT validation dependency (core/security.py).

Phase 1: Supabase-style HS256 access tokens, per docs/07_API_Design.md §6.
"""

import time

import jwt
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import AuthUser, get_current_user
from app.main import create_app

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
WRONG_SECRET = "wrong-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"


def make_client(secret: str | None = TEST_SECRET) -> TestClient:
    """Build the real app (with its exception handlers) plus a test-only
    protected route, overriding settings to use the test secret."""
    app = create_app()

    @app.get("/protected")
    async def protected(user: AuthUser = Depends(get_current_user)):
        return {"success": True, "data": {"id": user.id, "email": user.email}}

    async def settings_override() -> Settings:
        return Settings(supabase_jwt_secret=secret or "")

    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


def make_token(
    secret: str = TEST_SECRET,
    *,
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str | None = "alex@example.com",
    exp_delta: int = 3600,
    algorithm: str = "HS256",
) -> str:
    payload: dict = {"sub": sub}
    if email is not None:
        payload["email"] = email
    if exp_delta is not None:
        payload["exp"] = int(time.time()) + exp_delta
    return jwt.encode(payload, secret, algorithm=algorithm)


def test_valid_token_returns_user_identity():
    client = make_client()
    token = make_token()

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert body["data"]["email"] == "alex@example.com"


def test_missing_token_returns_401_with_documented_envelope():
    client = make_client()

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "Authentication required.",
    }


def test_wrong_secret_returns_401():
    client = make_client()
    token = make_token(secret=WRONG_SECRET)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_expired_token_returns_401():
    client = make_client()
    token = make_token(exp_delta=-60)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_malformed_token_returns_401():
    client = make_client()

    response = client.get(
        "/protected", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_token_without_sub_claim_is_rejected():
    client = make_client()
    payload = {"email": "alex@example.com", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_signed_with_wrong_algorithm_is_rejected():
    client = make_client()
    token = make_token(algorithm="HS512")

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_unconfigured_jwt_secret_returns_401_not_500():
    client = make_client(secret=None)
    token = make_token()

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "Authentication required.",
    }
