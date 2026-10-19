"""Admin usage, request, and audit read-model tests."""

from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.audit import record_admin_audit_event
from app.main import create_app
from app.models import Base
from app.models.admin import AdminAuditEvent, AdminUser
from app.models.ai_run_record import AIRunRecord

TEST_SECRET = "test-admin-read-secret-0123456789abcdef0123456789abcdef"
ADMIN_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def make_token(user_id: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "email": "admin@example.com",
            "exp": int(time.time()) + 3600,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def auth_headers(user_id: str = ADMIN_ID) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def build_app(tmp_path) -> FastAPI:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp_path / 'admin-read.db'}",
            supabase_jwt_secret=TEST_SECRET,
        )
    )
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        session.add(AdminUser(user_id=ADMIN_ID))
        session.commit()
    return app


def add_run(
    app: FastAPI,
    *,
    domain: str,
    status: str,
    latency_ms: int,
    created_at: datetime,
    error: str | None = None,
    error_category: str | None = None,
    user_id: str = USER_ID,
) -> str:
    run_id = str(uuid4())
    with app.state.session_factory() as session:
        session.add(
            AIRunRecord(
                run_id=run_id,
                user_id=user_id,
                domain=domain,
                workflow_id=f"{domain}/test",
                model="gpt-4.1-mini",
                input_state={"resume_text": "PRIVATE RESUME"},
                output_state={"result": "PRIVATE OUTPUT"},
                status=status,
                error=error,
                error_category=error_category,
                latency_ms=latency_ms,
                created_at=created_at,
            )
        )
        session.commit()
    return run_id


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)


def seed_runs(app: FastAPI) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "resume_ok": add_run(
            app,
            domain="resume_ats",
            status="success",
            latency_ms=100,
            created_at=now - timedelta(minutes=5),
        ),
        "resume_error": add_run(
            app,
            domain="resume_ats",
            status="error",
            latency_ms=300,
            created_at=now - timedelta(minutes=4),
            error="ProviderError: private provider detail",
            error_category="ProviderError",
        ),
        "support_ok": add_run(
            app,
            domain="support_copilot",
            status="success",
            latency_ms=200,
            created_at=now - timedelta(minutes=3),
        ),
        "old": add_run(
            app,
            domain="resume_ats",
            status="success",
            latency_ms=50,
            created_at=now - timedelta(days=40),
        ),
    }


def test_usage_is_admin_only(client):
    response = client.get("/api/v1/admin/usage")

    assert response.status_code == 401


def test_usage_aggregates_and_filters(app, client):
    seed_runs(app)

    response = client.get(
        "/api/v1/admin/usage?window=30d",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_requests"] == 3
    assert data["successful_requests"] == 2
    assert data["failed_requests"] == 1
    assert data["success_rate"] == 66.67
    assert data["failure_rate"] == 33.33
    assert data["average_latency_ms"] == 200.0
    assert data["max_latency_ms"] == 300
    assert data["token_usage_available"] is False

    filtered = client.get(
        "/api/v1/admin/usage?window=30d&assistant=resume_ats",
        headers=auth_headers(),
    ).json()["data"]
    assert filtered["total_requests"] == 2
    assert filtered["failed_requests"] == 1


def test_usage_rejects_invalid_window(client):
    response = client.get(
        "/api/v1/admin/usage?start=2026-10-18T12:00:00Z"
        "&end=2026-10-17T12:00:00Z",
        headers=auth_headers(),
    )

    assert response.status_code == 400


def test_request_list_paginates_and_filters(app, client):
    runs = seed_runs(app)

    page = client.get(
        "/api/v1/admin/requests?window=30d&page=1&page_size=2",
        headers=auth_headers(),
    )
    assert page.status_code == 200
    body = page.json()["data"]
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2

    failed = client.get(
        "/api/v1/admin/requests?window=30d&status=error",
        headers=auth_headers(),
    ).json()["data"]
    assert failed["total"] == 1
    assert failed["items"][0]["run_id"] == runs["resume_error"]
    assert failed["items"][0]["error_category"] == "ProviderError"

    by_id = client.get(
        f"/api/v1/admin/requests?window=30d&run_id={runs['support_ok']}",
        headers=auth_headers(),
    ).json()["data"]
    assert by_id["total"] == 1

    by_category = client.get(
        "/api/v1/admin/requests?window=30d&error_category=ProviderError",
        headers=auth_headers(),
    ).json()["data"]
    assert by_category["total"] == 1


def test_request_detail_excludes_sensitive_state(app, client):
    runs = seed_runs(app)

    response = client.get(
        f"/api/v1/admin/requests/{runs['resume_error']}",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["run_id"] == runs["resume_error"]
    assert data["error_category"] == "ProviderError"
    assert "input_state" not in data
    assert "output_state" not in data
    assert "error" not in data
    assert "PRIVATE" not in response.text
    assert "private provider detail" not in response.text


def test_request_detail_not_found(app, client):
    response = client.get(
        f"/api/v1/admin/requests/{uuid4()}",
        headers=auth_headers(),
    )

    assert response.status_code == 404


def test_audit_list_is_filtered_and_safe(app, client):
    with app.state.session_factory() as session:
        record_admin_audit_event(
            session,
            actor_user_id=ADMIN_ID,
            admin_user_id=ADMIN_ID,
            actor_is_admin=True,
            action="admin.test",
            target_type="user",
            target_id=USER_ID,
            success=False,
            reason="test reason",
            details={"request_id": "safe-id"},
        )

    response = client.get(
        "/api/v1/admin/audit?window=30d&success=false",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    event = data["items"][0]
    assert event["action"] == "admin.test"
    assert event["actor_user_id"] == ADMIN_ID
    assert event["success"] is False
    assert event["details"] == {"request_id": "safe-id"}
