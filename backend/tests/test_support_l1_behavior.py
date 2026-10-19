"""L1 support behavior: diagnose first, iterate safely, escalate correctly."""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai_core import create_ai_core
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.core.config import Settings
from app.domains.support_copilot.domain import wire_support_copilot
from app.main import create_app
from app.models import Base

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
USER_A = "550e8400-e29b-41d4-a716-446655440000"


class CountingProvider:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0

    def complete(self, *, system, user, model, temperature):
        self.calls += 1
        return self.responses.pop(0)


def make_token() -> str:
    payload = {
        "sub": USER_A,
        "email": "alex@example.com",
        "email_verified": True,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}


def build_client(tmp_path, responses):
    provider = CountingProvider(responses)
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        openai_api_key="test-key",
        supabase_jwt_secret=TEST_SECRET,
    )
    app: FastAPI = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    run_store = SQLAlchemyRunRecordStore(app.state.session_factory)
    ai_core = create_ai_core(run_store=run_store)
    ai_core.llm_factory.register_provider(settings.ai_provider_name, provider)
    wire_support_copilot(ai_core, settings)
    app.state.ai_core = ai_core
    return TestClient(app), provider


def create_session(client: TestClient) -> str:
    return client.post(
        "/api/v1/support/sessions", headers=auth_headers()
    ).json()["data"]["session_id"]


def send(client: TestClient, session_id: str, message: str):
    return client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message},
        headers=auth_headers(),
    )


def test_failed_restart_continues_troubleshooting_and_does_not_escalate(tmp_path):
    client, provider = build_client(
        tmp_path,
        [
            "vpn_issue",
            "Restart the VPN client and report the result.",
            "Check the VPN adapter state and report what you see.",
        ],
    )
    with client:
        session_id = create_session(client)
        first = send(client, session_id, "My VPN will not connect").json()["data"]
        ticket_id = first["ticket"]["ticket_id"]

        second = send(
            client, session_id, "I restarted the client but it is still not working"
        ).json()["data"]

        assert second["ticket"]["ticket_id"] == ticket_id
        assert second["ticket"]["status"] == "In Progress"
        assert second["escalation_needed"] is False
        assert "Restart the VPN client" in second["response"]
        assert "Escalation requested" not in second["response"]

        third = send(
            client, session_id, "The adapter shows disconnected"
        ).json()["data"]

        assert third["ticket"]["ticket_id"] == ticket_id
        assert third["ticket"]["status"] == "In Progress"
        assert "Check the VPN adapter state" in third["response"]
        assert third["ticket"]["troubleshooting_attempts"] == 2
        assert provider.calls == 3  # classify + two troubleshoot turns


def test_repeated_diagnostic_failure_requests_escalation(tmp_path):
    client, provider = build_client(
        tmp_path,
        [
            "vpn_issue",
            "Step one: restart the client.",
            "Step two: check the adapter.",
            "Step three: recreate the VPN profile.",
        ],
    )
    with client:
        session_id = create_session(client)
        send(client, session_id, "My VPN will not connect")
        send(client, session_id, "I restarted, still failing")
        send(client, session_id, "The adapter looks disconnected")
        send(client, session_id, "I recreated the profile and it still fails")

        response = send(client, session_id, "That did not work either")
        data = response.json()["data"]

    assert data["ticket"]["status"] == "Escalation Requested"
    assert data["ticket"]["handoff_status"] == "requested"
    assert data["ticket"]["escalation_reason"] == (
        "Repeated troubleshooting steps have not resolved the issue."
    )
    assert "No human engineer has accepted" in data["response"]
    assert "Escalated to IT Support Team" not in data["response"]
    # The escalation request did not call the model again.
    assert provider.calls == 4  # classify + three troubleshooting turns


def test_explicit_human_request_requests_escalation_without_claiming_handoff(tmp_path):
    client, provider = build_client(tmp_path, ["vpn_issue"])
    with client:
        session_id = create_session(client)
        send(client, session_id, "My VPN will not connect")

        response = send(client, session_id, "I need to speak to a human")
        data = response.json()["data"]

    assert data["ticket"]["status"] == "Escalation Requested"
    assert data["ticket"]["handoff_status"] == "requested"
    assert data["ticket"]["escalation_reason"] == "Human handoff requested."
    assert "No human engineer has accepted" in data["response"]
    assert "live human handoff integration" in data["response"]
    assert provider.calls == 1


def test_missing_admin_rights_requests_escalation(tmp_path):
    client, provider = build_client(tmp_path, ["vpn_issue"])
    with client:
        session_id = create_session(client)
        send(client, session_id, "My VPN will not connect")

        response = send(
            client, session_id, "I do not have admin rights to change the adapter"
        )
        data = response.json()["data"]

    assert data["ticket"]["status"] == "Escalation Requested"
    assert data["ticket"]["escalation_reason"] == (
        "The next steps need permissions or expertise outside the Copilot's access."
    )
    assert "No human engineer has accepted" in data["response"]
    assert provider.calls == 1


def test_ticket_context_tracks_issue_updates_and_attempts(tmp_path):
    client, _ = build_client(
        tmp_path,
        [
            "vpn_issue",
            "Restart the VPN client and report the result.",
        ],
    )
    with client:
        session_id = create_session(client)
        first = send(client, session_id, "My VPN will not connect").json()["data"]
        second = send(
            client, session_id, "I restarted it and the error is 809"
        ).json()["data"]

    ticket = second["ticket"]
    assert ticket["ticket_id"] == first["ticket"]["ticket_id"]
    assert ticket["reported_issue"] == "My VPN will not connect"
    assert ticket["latest_user_update"] == "I restarted it and the error is 809"
    assert ticket["troubleshooting_attempts"] == 1
    assert ticket["current_hypothesis"] == "Not confirmed"
    assert ticket["handoff_status"] == "not_requested"


def test_session_detail_exposes_ticket_context(tmp_path):
    client, _ = build_client(
        tmp_path,
        [
            "vpn_issue",
            "Restart the VPN client and report the result.",
        ],
    )
    with client:
        session_id = create_session(client)
        send(client, session_id, "My VPN will not connect")
        send(client, session_id, "I restarted it and the error is 809")

        response = client.get(
            f"/api/v1/support/sessions/{session_id}", headers=auth_headers()
        )

    assert response.status_code == 200
    ticket = response.json()["data"]["ticket"]
    assert ticket["reported_issue"] == "My VPN will not connect"
    assert ticket["latest_user_update"] == "I restarted it and the error is 809"
    assert ticket["troubleshooting_attempts"] == 1
    assert ticket["handoff_status"] == "not_requested"
    assert ticket["current_hypothesis"] == "Not confirmed"


def test_resolution_requires_user_confirmation_and_uses_root_cause(tmp_path):
    client, _ = build_client(
        tmp_path,
        [
            "vpn_issue",
            "Restart the VPN client and report the result.",
            "Issue: VPN profile corruption\nSuspected Cause: profile corruption\n"
            "Actions Recommended: recreate profile\n"
            "Actions Confirmed by the User: recreated profile\n"
            "Outcome: connectivity restored\n"
            "Unresolved Uncertainties: exact trigger unknown",
        ],
    )
    with client:
        session_id = create_session(client)
        send(client, session_id, "My VPN will not connect")
        send(client, session_id, "I restarted it, still failing")

        fix = send(client, session_id, "It works now")
        assert fix.json()["data"]["ticket"]["status"] == "Awaiting Confirmation"
        assert "Troubleshooting Response" not in fix.json()["data"]["response"]

        resolved = send(client, session_id, "Confirmed, it is resolved")
        data = resolved.json()["data"]

    assert data["ticket"]["status"] == "Resolved"
    assert data["status"] == "resolved"
    assert "Suspected Cause: profile corruption" in data["response"]
