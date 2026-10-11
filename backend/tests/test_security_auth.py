"""Tests for the JWT validation dependency (core/security.py).

Supabase-style tokens per docs/07_API_Design.md §6, in both supported
signing modes:
- HS256 (legacy shared secret), and
- ES256 (current Supabase default) with P-256 keys resolved from a
  JWKS document. JWKS fetching is patched with canned local documents —
  no network calls and no production credentials are involved.
"""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends
from fastapi.testclient import TestClient

import app.core.security as security
from app.core.config import Settings
from app.core.security import AuthUser, get_current_user
from app.main import create_app

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
WRONG_SECRET = "wrong-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"

TEST_SUPABASE_URL = "https://example.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"

ES256_KID = "test-es256-kid"
OTHER_KID = "other-kid"


def make_client(
    secret: str | None = TEST_SECRET,
    supabase_url: str = "",
) -> TestClient:
    """Build the real app (with its exception handlers) plus a test-only
    protected route, using explicit Settings bound to app.state."""
    app = create_app(
        Settings(
            supabase_jwt_secret=secret or "",
            supabase_url=supabase_url,
            database_url="sqlite://",
        )
    )

    @app.get("/protected")
    async def protected(user: AuthUser = Depends(get_current_user)):
        return {"success": True, "data": {"id": user.id, "email": user.email}}

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


# ---------------------------------------------------------------
# ES256 (current Supabase signing method) — local keys only
# ---------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_ec_key():
    return ec.generate_private_key(ec.SECP256R1())


def make_jwk(public_key, kid: str) -> dict:
    numbers = public_key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "kid": kid,
        "x": _b64url(numbers.x.to_bytes(32, "big")),
        "y": _b64url(numbers.y.to_bytes(32, "big")),
    }


def make_es256_token(
    private_key,
    *,
    kid: str,
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str = "es256@example.com",
    iss: str = TEST_ISSUER,
    aud: str = "authenticated",
    exp_delta: int = 3600,
) -> str:
    payload = {"sub": sub, "email": email, "iss": iss, "aud": aud}
    if exp_delta is not None:
        payload["exp"] = int(time.time()) + exp_delta
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


def patch_jwks(monkeypatch, keys: list[dict]):
    def fake_fetch(jwks_url: str) -> dict:
        return {"keys": keys}

    monkeypatch.setattr(security, "_fetch_jwks_json", fake_fetch)
    security._jwks_cache.clear()


def test_es256_token_is_accepted(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(key, kid=ES256_KID)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_es256_token_signed_by_different_key_is_rejected(monkeypatch):
    real_key = make_ec_key()
    attacker_key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(real_key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(attacker_key, kid=ES256_KID)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_with_unknown_kid_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), OTHER_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(key, kid="not-in-jwks")

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_expired_token_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(key, kid=ES256_KID, exp_delta=-60)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_with_wrong_audience_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(key, kid=ES256_KID, aud="anonymous")

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_with_wrong_issuer_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    token = make_es256_token(key, kid=ES256_KID, iss="https://evil.example.com/auth/v1")

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_without_sub_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    payload = {
        "email": "nosub@example.com",
        "iss": TEST_ISSUER,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(
        payload, key, algorithm="ES256", headers={"kid": ES256_KID}
    )

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_without_supabase_url_is_rejected(monkeypatch):
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url="")
    token = make_es256_token(key, kid=ES256_KID)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_hs256_token_signed_with_public_key_is_rejected(monkeypatch):
    """Algorithm-confusion guard: an HS256 token forged with the public
    key material must never verify against the legacy secret path."""
    import hashlib
    import hmac
    import json

    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(supabase_url=TEST_SUPABASE_URL)
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def b64url(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url(
        json.dumps(
            {
                "sub": "550e8400-e29b-41d4-a716-446655440000",
                "exp": int(time.time()) + 3600,
            }
        ).encode()
    )
    signing_input = header + b"." + payload
    signature = b64url(
        hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    )
    token = (signing_input + b"." + signature).decode()

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_es256_token_is_not_accepted_by_legacy_secret_path(monkeypatch):
    """The legacy HS256 secret must never validate an ES256 token."""
    key = make_ec_key()
    patch_jwks(monkeypatch, [make_jwk(key.public_key(), ES256_KID)])
    client = make_client(
        secret=TEST_SECRET, supabase_url="https://other.supabase.co"
    )
    # Token signed for another project's issuer: ES256 path rejects the
    # issuer; the HS256 path must not fall back to the secret.
    token = make_es256_token(key, kid=ES256_KID)

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
