"""Tests for the authenticated self-profile API."""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models import Base
from app.models.profile import UserProfile

TEST_SECRET = "test-profile-secret-0123456789abcdef0123456789"
USER_A = "550e8400-e29b-41d4-a716-446655440010"
USER_B = "660e8400-e29b-41d4-a716-446655440011"


def make_token(
    user_id: str,
    *,
    email: str = "user@example.com",
    email_verified: bool = False,
) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "email_verified": email_verified,
            "exp": int(time.time()) + 3600,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def auth_headers(
    user_id: str = USER_A,
    *,
    email: str = "user@example.com",
    email_verified: bool = True,
) -> dict:
    return {
        "Authorization": (
            f"Bearer {make_token(user_id, email=email, email_verified=email_verified)}"
        )
    }


def build_app(tmp_path) -> FastAPI:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'profile.db'}",
            supabase_jwt_secret=TEST_SECRET,
        )
    )
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)


def profile_payload(**overrides) -> dict:
    payload = {
        "full_name": "Alex Example",
        "phone": "+1 (555) 123-4567",
        "country_code": "us",
        "city": "Seattle",
        "career_goal": "Cloud engineer",
        "marketing_consent": True,
        "terms_accepted": True,
        "privacy_accepted": True,
    }
    payload.update(overrides)
    return payload


def test_profile_requires_authentication(client):
    assert client.get("/api/v1/profile").status_code == 401
    assert client.put(
        "/api/v1/profile", json=profile_payload()
    ).status_code == 401


def test_unverified_email_cannot_access_profile(app, client):
    response = client.get(
        "/api/v1/profile",
        headers=auth_headers(email_verified=False),
    )
    assert response.status_code == 403
    assert response.json()["message"] == "Email verification is required."

    update = client.put(
        "/api/v1/profile",
        headers=auth_headers(email_verified=False),
        json=profile_payload(),
    )
    assert update.status_code == 403
    with app.state.session_factory() as session:
        assert session.get(UserProfile, USER_A) is None


def test_create_and_get_profile(app, client):
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(),
        json=profile_payload(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == USER_A
    assert data["full_name"] == "Alex Example"
    assert data["phone"] == "+1 (555) 123-4567"
    assert data["country_code"] == "US"
    assert data["city"] == "Seattle"
    assert data["career_goal"] == "Cloud engineer"
    assert data["marketing_consent"] is True
    assert data["email"] == "user@example.com"
    assert data["email_verified"] is True
    assert data["terms_accepted_at"] is not None
    assert data["privacy_accepted_at"] is not None

    fetched = client.get(
        "/api/v1/profile", headers=auth_headers()
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"] == data

    with app.state.session_factory() as session:
        stored = session.get(UserProfile, USER_A)
        assert stored is not None
        assert stored.full_name == "Alex Example"
        assert stored.marketing_consent is True


def test_profile_creation_requires_policy_acceptance(app, client):
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(),
        json=profile_payload(
            terms_accepted=False, privacy_accepted=False
        ),
    )

    assert response.status_code == 400
    assert response.json()["success"] is False
    with app.state.session_factory() as session:
        assert session.get(UserProfile, USER_A) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"full_name": " "},
        {"phone": "123"},
        {"phone": "call-me"},
        {"country_code": "USA"},
        {"country_code": "1A"},
        {"user_id": USER_B},
        {"city": "x" * 101},
        {"career_goal": "x" * 201},
    ],
)
def test_profile_validation(client, overrides):
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(),
        json=profile_payload(**overrides),
    )

    assert response.status_code == 422


def test_profile_update_preserves_policy_acceptance(app, client):
    created = client.put(
        "/api/v1/profile",
        headers=auth_headers(),
        json=profile_payload(),
    ).json()["data"]

    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(),
        json=profile_payload(
            full_name="Alex Updated",
            phone=None,
            country_code=None,
            city=None,
            career_goal=None,
            marketing_consent=False,
            terms_accepted=False,
            privacy_accepted=False,
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_name"] == "Alex Updated"
    assert data["phone"] is None
    assert data["country_code"] is None
    assert data["city"] is None
    assert data["career_goal"] is None
    assert data["marketing_consent"] is False
    assert data["terms_accepted_at"] == created["terms_accepted_at"]
    assert data["privacy_accepted_at"] == created["privacy_accepted_at"]


def test_cross_user_profile_isolation(app, client):
    created_a = client.put(
        "/api/v1/profile",
        headers=auth_headers(USER_A, email="a@example.com"),
        json=profile_payload(full_name="User A"),
    )
    assert created_a.status_code == 200

    missing_b = client.get(
        "/api/v1/profile",
        headers=auth_headers(USER_B, email="b@example.com"),
    )
    assert missing_b.status_code == 404

    created_b = client.put(
        "/api/v1/profile",
        headers=auth_headers(USER_B, email="b@example.com"),
        json=profile_payload(full_name="User B"),
    )
    assert created_b.status_code == 200
    assert created_b.json()["data"]["user_id"] == USER_B
    assert created_b.json()["data"]["full_name"] == "User B"

    fetched_a = client.get(
        "/api/v1/profile",
        headers=auth_headers(USER_A, email="a@example.com"),
    )
    assert fetched_a.status_code == 200
    assert fetched_a.json()["data"]["full_name"] == "User A"

    with app.state.session_factory() as session:
        profiles = session.query(UserProfile).all()
        assert len(profiles) == 2
        assert {profile.user_id for profile in profiles} == {
            USER_A,
            USER_B,
        }


def test_verified_email_is_reflected_in_profile(client):
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(email_verified=True),
        json=profile_payload(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["email_verified"] is True
