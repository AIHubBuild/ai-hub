"""Administrator authorization and account-status tests."""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domains.admin.service import record_admin_audit_event
from app.main import create_app
from app.models import Base
from app.models.admin import (
    AdminAuditEvent,
    AdminUser,
    UserAccountStatus,
)

from tests.profile_test_helpers import seed_complete_profile

TEST_SECRET = "test-admin-secret-0123456789abcdef0123456789abcdef0123456789"
ADMIN_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def make_token(user_id: str, email: str = "user@example.com") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "email_verified": True,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers(user_id: str, email: str = "user@example.com") -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, email)}"}


def build_app(tmp_path) -> FastAPI:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'admin.db'}",
            supabase_jwt_secret=TEST_SECRET,
        )
    )
    Base.metadata.create_all(app.state.engine)
    seed_complete_profile(app, USER_ID)
    return app


def add_admin(app: FastAPI, user_id: str = ADMIN_ID) -> None:
    with app.state.session_factory() as session:
        session.add(AdminUser(user_id=user_id))
        session.commit()


def set_status(app: FastAPI, user_id: str, status: str) -> None:
    with app.state.session_factory() as session:
        session.add(UserAccountStatus(user_id=user_id, status=status))
        session.commit()


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)


def test_admin_endpoint_requires_authentication(client):
    response = client.get("/api/v1/admin/me")

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_ordinary_user_cannot_access_admin_endpoint(client):
    response = client.get("/api/v1/admin/me", headers=auth_headers(USER_ID))

    assert response.status_code == 403
    assert response.json() == {
        "success": False,
        "message": "Administrator access required.",
    }


def test_ordinary_user_cannot_access_admin_read_models(client):
    for path in (
        "/api/v1/admin/usage",
        "/api/v1/admin/requests",
        "/api/v1/admin/audit",
    ):
        response = client.get(path, headers=auth_headers(USER_ID))
        assert response.status_code == 403


def test_denied_admin_attempt_is_audited(app, client):
    response = client.get(
        "/api/v1/admin/usage", headers=auth_headers(USER_ID)
    )

    assert response.status_code == 403
    with app.state.session_factory() as session:
        event = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "admin.access_denied")
            .one()
        )
        assert event.actor_user_id == USER_ID
        assert event.admin_user_id is None
        assert event.actor_is_admin is False
        assert event.success is False
        assert event.target_type == "route"
        assert event.target_id == "/admin/usage"
        assert event.reason == "Administrator access required."


def test_unauthenticated_admin_attempt_does_not_create_audit_event(app, client):
    response = client.get("/api/v1/admin/usage")

    assert response.status_code == 401
    with app.state.session_factory() as session:
        assert session.query(AdminAuditEvent).count() == 0


def test_admin_can_access_admin_endpoint(app, client):
    add_admin(app)

    response = client.get(
        "/api/v1/admin/me",
        headers=auth_headers(ADMIN_ID, "admin@example.com"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Administrator access granted.",
        "data": {"user_id": ADMIN_ID, "email": "admin@example.com"},
    }


def test_suspended_admin_cannot_access_admin_endpoint(app, client):
    add_admin(app)
    set_status(app, ADMIN_ID, "suspended")

    response = client.get("/api/v1/admin/me", headers=auth_headers(ADMIN_ID))

    assert response.status_code == 403
    assert response.json()["message"] == "This account is suspended."

    with app.state.session_factory() as session:
        event = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "admin.access_denied")
            .one()
        )
        assert event.actor_user_id == ADMIN_ID
        assert event.admin_user_id == ADMIN_ID
        assert event.actor_is_admin is True
        assert event.success is False
        assert event.reason == "This account is suspended."


def test_active_user_without_status_row_can_use_protected_endpoint(client):
    response = client.post(
        "/api/v1/support/sessions",
        headers=auth_headers(USER_ID),
    )

    assert response.status_code == 201


def test_suspended_user_is_denied_on_protected_endpoint(app, client):
    set_status(app, USER_ID, "suspended")

    response = client.post(
        "/api/v1/support/sessions",
        headers=auth_headers(USER_ID),
    )

    assert response.status_code == 403
    assert response.json() == {
        "success": False,
        "message": "This account is suspended.",
    }


def test_audit_event_records_admin_action(app):
    with app.state.session_factory() as session:
        event = record_admin_audit_event(
            session,
            admin_user_id=ADMIN_ID,
            action="test.action",
            target_type="user",
            target_id=USER_ID,
            success=True,
            reason="focused test",
            details={"old": "a", "new": "b"},
        )

        assert event.admin_user_id == ADMIN_ID
        assert event.action == "test.action"
        assert event.target_type == "user"
        assert event.target_id == USER_ID
        assert event.success is True
        assert event.reason == "focused test"
        assert event.details == {"old": "a", "new": "b"}
