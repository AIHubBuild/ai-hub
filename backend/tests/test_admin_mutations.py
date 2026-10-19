"""Administrative incident and manual entitlement mutation tests."""

import time
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models import Base
from app.models.admin import (
    AdminAuditEvent,
    AdminUser,
    UserEntitlement,
)
from app.models.ai_run_record import AIRunRecord

TEST_SECRET = "test-admin-mutations-secret-0123456789abcdef0123456789"
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
            database_url=f"sqlite:///{tmp_path / 'admin-mutations.db'}",
            supabase_jwt_secret=TEST_SECRET,
        )
    )
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        session.add(AdminUser(user_id=ADMIN_ID))
        session.commit()
    return app


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)


def test_incident_endpoints_are_admin_only(client):
    assert client.get("/api/v1/admin/incidents").status_code == 401
    assert client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(USER_ID),
        json={
            "title": "Test incident",
            "description": "Test description",
            "category": "platform",
            "priority": "high",
        },
    ).status_code == 403


def test_incident_rejects_blank_or_null_required_fields(client):
    blank_title = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "   ",
            "description": "Test description",
            "category": "platform",
        },
    )
    assert blank_title.status_code == 422

    blank_description = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Valid title",
            "description": "   ",
            "category": "platform",
        },
    )
    assert blank_description.status_code == 422


def test_incident_update_rejects_null_status_and_priority(app, client):
    created = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Null field test",
            "description": "Should not reach the database",
            "category": "platform",
        },
    ).json()["data"]

    for field in ("status", "priority"):
        response = client.patch(
            f"/api/v1/admin/incidents/{created['incident_id']}",
            headers=auth_headers(),
            json={field: None},
        )
        assert response.status_code == 422

    with app.state.session_factory() as session:
        assert (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "incident.update")
            .count()
            == 0
        )


def test_entitlement_rejects_blank_reason(client):
    response = client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
        json={"tier": "pro", "reason": "   "},
    )
    assert response.status_code == 422


def test_create_incident_is_audited_without_description(app, client):
    response = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Elevated AI errors",
            "description": "Private operational details",
            "category": "ai",
            "priority": "high",
            "linked_user_id": USER_ID,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Elevated AI errors"
    assert data["status"] == "open"
    assert data["linked_user_id"] == USER_ID

    with app.state.session_factory() as session:
        event = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "incident.create")
            .one()
        )
        assert event.success is True
        assert event.target_type == "incident"
        assert event.target_id == data["incident_id"]
        assert "description" not in event.details
        assert "Private operational details" not in str(event.details)


def test_update_incident_requires_resolution_summary(app, client):
    created = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Printer outage",
            "description": "Printer unavailable",
            "category": "hardware",
            "priority": "medium",
        },
    ).json()["data"]

    without_summary = client.patch(
        f"/api/v1/admin/incidents/{created['incident_id']}",
        headers=auth_headers(),
        json={"status": "resolved"},
    )
    assert without_summary.status_code == 400

    resolved = client.patch(
        f"/api/v1/admin/incidents/{created['incident_id']}",
        headers=auth_headers(),
        json={
            "status": "resolved",
            "resolution_summary": "Replaced the printer queue.",
        },
    )
    assert resolved.status_code == 200
    data = resolved.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolution_summary"] == "Replaced the printer queue."
    assert data["resolved_at"] is not None

    with app.state.session_factory() as session:
        events = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "incident.update")
            .all()
        )
        assert len(events) == 2
        assert [event.success for event in events] == [False, True]
        assert "Replaced the printer queue." not in str(events[-1].details)


def test_incident_list_and_detail_include_history(app, client):
    created = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "VPN issue",
            "description": "Users cannot connect",
            "category": "network",
            "priority": "critical",
        },
    ).json()["data"]

    listing = client.get(
        "/api/v1/admin/incidents?status=open&priority=critical",
        headers=auth_headers(),
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1

    detail = client.get(
        f"/api/v1/admin/incidents/{created['incident_id']}",
        headers=auth_headers(),
    )
    assert detail.status_code == 200
    assert len(detail.json()["data"]["history"]) == 1


def test_manual_entitlement_upsert_and_audit(app, client):
    response = client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
        json={
            "tier": "pro",
            "limits": {"monthly_requests": 100},
            "reason": "Manual support review",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["tier"] == "pro"

    update = client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
        json={
            "tier": "free",
            "limits": None,
            "reason": "Trial entitlement ended",
        },
    )
    assert update.status_code == 200
    assert update.json()["data"]["tier"] == "free"

    with app.state.session_factory() as session:
        entitlement = session.get(UserEntitlement, USER_ID)
        assert entitlement is not None
        assert entitlement.tier == "free"
        events = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "entitlement.update")
            .order_by(AdminAuditEvent.created_at.asc())
            .all()
        )
        assert [event.success for event in events] == [True, True]
        assert events[0].details["old_tier"] is None
        assert events[0].details["new_tier"] == "pro"
        assert events[1].details["old_tier"] == "pro"
        assert events[1].details["new_tier"] == "free"
        assert "Manual support review" not in str(events[0].details)


def test_invalid_entitlement_tier_is_rejected(app, client):
    response = client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
        json={"tier": "enterprise", "reason": "not allowed"},
    )
    assert response.status_code == 422


def test_entitlement_list_and_detail(client):
    client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
        json={"tier": "pro", "reason": "manual grant"},
    )

    listing = client.get(
        "/api/v1/admin/entitlements?tier=pro",
        headers=auth_headers(),
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1

    detail = client.get(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["source"] == "manual"


def test_incident_rejects_unknown_assignee(app, client):
    response = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Invalid assignee test",
            "description": "Should be rejected",
            "category": "platform",
            "priority": "low",
            "assigned_admin_id": "770e8400-e29b-41d4-a716-446655440002",
        },
    )

    assert response.status_code == 400
    with app.state.session_factory() as session:
        event = (
            session.query(AdminAuditEvent)
            .filter(AdminAuditEvent.action == "incident.create")
            .one()
        )
        assert event.success is False
        assert event.reason == "invalid_reference"


def test_entitlement_endpoints_are_admin_only(client):
    assert client.get("/api/v1/admin/entitlements").status_code == 401
    assert client.put(
        f"/api/v1/admin/users/{USER_ID}/entitlement",
        headers=auth_headers(USER_ID),
        json={"tier": "pro", "reason": "not allowed"},
    ).status_code == 403


def test_incident_accepts_valid_linked_request(app, client):
    run_id = "11111111-1111-1111-1111-111111111111"
    with app.state.session_factory() as session:
        session.add(
            AIRunRecord(
                run_id=run_id,
                user_id=USER_ID,
                domain="resume_ats",
                workflow_id="resume_ats/ats_pipeline",
                input_state={"resume_text": "private"},
                status="error",
                error_category="ProviderError",
                latency_ms=100,
            )
        )
        session.commit()

    response = client.post(
        "/api/v1/admin/incidents",
        headers=auth_headers(),
        json={
            "title": "Linked request incident",
            "description": "Operational follow-up",
            "category": "ai",
            "priority": "high",
            "linked_run_id": run_id,
            "linked_user_id": USER_ID,
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["linked_run_id"] == run_id
    assert response.json()["data"]["linked_user_id"] == USER_ID
