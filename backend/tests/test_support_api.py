"""End-to-end tests for the Support Copilot API.

The OpenAI provider is replaced with a scripted test double through the
same ai_core wiring the application uses — no network calls. Sessions
and tickets are persisted and user-scoped; cross-user access is
exercised with two distinct user identities.
"""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai_core import create_ai_core
from app.ai_core.providers.openai import ProviderError
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.core.config import Settings
from app.domains.support_copilot.domain import wire_support_copilot
from app.main import create_app
from app.models import Base
from app.models.support import SupportSession, SupportTicket

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"

USER_A = "550e8400-e29b-41d4-a716-446655440000"
USER_B = "660e8400-e29b-41d4-a716-446655440001"


class FakeProvider:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error

    def complete(self, *, system, user, model, temperature):
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("No canned response available for LLM call")
        return self.responses.pop(0)


def make_token(user_id: str = USER_A) -> str:
    payload = {
        "sub": user_id,
        "email": "alex@example.com",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers(user_id: str = USER_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        openai_api_key="test-key",
        supabase_jwt_secret=TEST_SECRET,
    )
    values.update(overrides)
    return Settings(**values)


def build_app(tmp_path, settings: Settings, provider: FakeProvider | None) -> FastAPI:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    run_store = SQLAlchemyRunRecordStore(app.state.session_factory)
    ai_core = create_ai_core(run_store=run_store)
    if provider is not None:
        ai_core.llm_factory.register_provider("openai", provider)
    wire_support_copilot(ai_core)
    app.state.ai_core = ai_core
    return app


@pytest.fixture
def client(tmp_path):
    provider = FakeProvider(
        responses=[
            # First message: classify + troubleshoot.
            "vpn_issue",
            "Restart your VPN client and try again.",
            # Follow-up message: troubleshoot only.
            "Check the VPN gateway status.",
            # "It works" message: troubleshoot.
            "That should resolve it.",
            # Confirmation message: troubleshoot, then root cause.
            "Please verify one more time.",
            "Issue Type: vpn_issue\nLikely Cause: configuration drift",
        ]
    )
    app = build_app(tmp_path, make_settings(tmp_path), provider)
    with TestClient(app) as test_client:
        yield test_client, app


def create_session(client: TestClient, user_id: str = USER_A):
    return client.post("/api/v1/support/sessions", headers=auth_headers(user_id))


def send_message(
    client: TestClient, session_id: str, message: str, user_id: str = USER_A
):
    return client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message},
        headers=auth_headers(user_id),
    )


# ---------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------


def test_create_session_requires_authentication(client):
    test_client, _ = client
    response = test_client.post("/api/v1/support/sessions")

    assert response.status_code == 401


def test_send_message_requires_authentication(client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/support/sessions/550e8400-e29b-41d4-a716-446655440000/messages",
        json={"message": "hello"},
    )

    assert response.status_code == 401


def test_list_tickets_requires_authentication(client):
    test_client, _ = client
    response = test_client.get("/api/v1/support/tickets")

    assert response.status_code == 401


# ---------------------------------------------------------------
# Session flow (first message → ticket → follow-ups → resolution)
# ---------------------------------------------------------------


def test_create_session_returns_id(client):
    test_client, _ = client
    response = create_session(test_client)

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["session_id"]


def test_first_message_classifies_and_creates_ticket(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]

    response = send_message(test_client, session_id, "Cannot connect to the VPN")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] == "vpn_issue"
    assert data["follow_up_question"] == "Are you receiving any VPN error messages?"
    assert data["escalation_needed"] is False
    ticket = data["ticket"]
    assert ticket["priority"] == "Medium"
    assert ticket["assigned_team"] == "Remote Access Team"
    assert ticket["status"] == "Open"
    assert "### Issue Classification" in data["response"]
    assert "vpn_issue" in data["response"]
    assert ticket["ticket_id"].startswith("INC-")


def test_first_message_persists_session_and_ticket(client):
    test_client, app = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN")

    with app.state.session_factory() as session:
        row = session.get(SupportSession, session_id)
        ticket = session.query(SupportTicket).filter_by(session_id=session_id).one()

    assert row.issue_type == "vpn_issue"
    assert row.user_id == USER_A
    assert len(row.messages) == 2
    assert row.messages[0]["role"] == "user"
    assert row.messages[1]["role"] == "assistant"
    assert ticket.user_id == USER_A
    assert ticket.status == "Open"


def test_follow_up_reuses_issue_type_and_advances_ticket(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN")

    response = send_message(test_client, session_id, "I still cannot connect")

    data = response.json()["data"]
    assert data["issue_type"] == "vpn_issue"
    assert data["follow_up_question"] == ""
    assert data["ticket"]["status"] == "In Progress"


def test_ticket_resolution_generates_root_cause(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN")
    send_message(test_client, session_id, "I still cannot connect")

    response = send_message(test_client, session_id, "It works now, fixed")

    data = response.json()["data"]
    assert data["ticket"]["status"] == "Awaiting Confirmation"

    response = send_message(test_client, session_id, "Confirmed, everything works now")

    data = response.json()["data"]
    assert data["ticket"]["status"] == "Resolved"
    assert data["status"] == "resolved"
    assert "marked as Resolved" in data["response"]
    assert "Likely Cause: configuration drift" in data["response"]


def test_session_detail_returns_messages_and_ticket(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN")

    response = test_client.get(
        f"/api/v1/support/sessions/{session_id}", headers=auth_headers()
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["session_id"] == session_id
    assert len(data["messages"]) == 2
    assert data["ticket"]["status"] == "Open"


def test_session_listing_returns_own_sessions_only(client):
    test_client, _ = client
    create_session(test_client, user_id=USER_A)
    create_session(test_client, user_id=USER_B)

    response_a = test_client.get(
        "/api/v1/support/sessions", headers=auth_headers(USER_A)
    )
    response_b = test_client.get(
        "/api/v1/support/sessions", headers=auth_headers(USER_B)
    )

    assert response_a.status_code == 200
    assert len(response_a.json()["data"]["sessions"]) == 1
    assert len(response_b.json()["data"]["sessions"]) == 1
    assert (
        response_a.json()["data"]["sessions"][0]["session_id"]
        != response_b.json()["data"]["sessions"][0]["session_id"]
    )


def test_session_listing_requires_authentication(client):
    test_client, _ = client
    response = test_client.get("/api/v1/support/sessions")

    assert response.status_code == 401


def test_message_on_resolved_session_returns_409(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN")
    send_message(test_client, session_id, "It works now, fixed")
    send_message(test_client, session_id, "Confirmed, everything works now")

    response = send_message(test_client, session_id, "Actually one more thing")

    assert response.status_code == 409
    assert response.json()["success"] is False


def test_security_issue_escalates_on_first_message(tmp_path):
    provider = FakeProvider(responses=["security_issue"])
    app = build_app(tmp_path, make_settings(tmp_path), provider)
    with TestClient(app) as test_client:
        session_id = create_session(test_client).json()["data"]["session_id"]

        response = send_message(test_client, session_id, "My account was hacked")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] == "security_issue"
    assert data["escalation_needed"] is True
    assert data["ticket"]["priority"] == "High"
    assert data["ticket"]["assigned_team"] == "Security Operations"
    assert "Escalated to IT Support Team" in data["response"]


# ---------------------------------------------------------------
# User-data isolation
# ---------------------------------------------------------------


def test_other_user_cannot_read_session(client):
    test_client, _ = client
    session_id = create_session(test_client, user_id=USER_A).json()["data"]["session_id"]

    response = test_client.get(
        f"/api/v1/support/sessions/{session_id}", headers=auth_headers(USER_B)
    )

    assert response.status_code == 404


def test_other_user_cannot_send_message(client):
    test_client, _ = client
    session_id = create_session(test_client, user_id=USER_A).json()["data"]["session_id"]

    response = send_message(test_client, session_id, "hi", user_id=USER_B)

    assert response.status_code == 404


def test_ticket_listing_is_user_scoped(client):
    test_client, _ = client
    session_id = create_session(test_client, user_id=USER_A).json()["data"]["session_id"]
    send_message(test_client, session_id, "Cannot connect to the VPN", user_id=USER_A)

    response_b = test_client.get(
        "/api/v1/support/tickets", headers=auth_headers(USER_B)
    )
    response_a = test_client.get(
        "/api/v1/support/tickets", headers=auth_headers(USER_A)
    )

    assert response_b.status_code == 200
    assert response_b.json()["data"]["tickets"] == []
    assert len(response_a.json()["data"]["tickets"]) == 1


def test_malformed_session_id_returns_404(client):
    test_client, _ = client
    response = send_message(test_client, "not-a-uuid", "hello")

    assert response.status_code == 404


# ---------------------------------------------------------------
# Provider availability
# ---------------------------------------------------------------


def test_message_without_provider_returns_503(tmp_path):
    app = build_app(tmp_path, make_settings(tmp_path, openai_api_key=""), None)
    with TestClient(app) as test_client:
        session_id = create_session(test_client).json()["data"]["session_id"]
        response = send_message(test_client, session_id, "VPN broken")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["message"]


def test_provider_failure_returns_502_and_persists_nothing(tmp_path):
    provider = FakeProvider(error=ProviderError("HTTP 500", status=500))
    app = build_app(tmp_path, make_settings(tmp_path), provider)
    with TestClient(app) as test_client:
        session_id = create_session(test_client).json()["data"]["session_id"]
        response = send_message(test_client, session_id, "VPN broken")

    assert response.status_code == 502
    assert response.json()["success"] is False

    with app.state.session_factory() as session:
        row = session.get(SupportSession, session_id)
        assert row.messages == []
        assert row.issue_type is None
        assert session.query(SupportTicket).count() == 0


def test_provider_failure_persists_error_run_record(tmp_path):
    from app.ai_core.run_records import RunStatus

    provider = FakeProvider(error=ProviderError("HTTP 500", status=500))
    app = build_app(tmp_path, make_settings(tmp_path), provider)
    with TestClient(app) as test_client:
        session_id = create_session(test_client).json()["data"]["session_id"]
        send_message(test_client, session_id, "VPN broken")

    records = app.state.ai_core.run_records.list_for_user(USER_A)
    assert len(records) == 1
    assert records[0].status is RunStatus.ERROR


# ---------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------


def test_blank_message_returns_422(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]

    response = send_message(test_client, session_id, "   ")

    assert response.status_code == 422


def test_oversized_message_returns_422(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]

    response = send_message(test_client, session_id, "x" * 4001)

    assert response.status_code == 422
