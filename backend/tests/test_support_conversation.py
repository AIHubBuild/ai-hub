"""Conversation-closure and diagnostic-accuracy regression tests.

Covers the full blue-screen journey with a scripted AI provider and
asserts the closure policy: fix reports never re-run troubleshooting,
gratitude gets a short acknowledgment before and after resolution,
explicit confirmation resolves the ticket, the ticket id stays stable,
no duplicate tickets are created, and the suspected cause is never
overstated. No network calls are made.
"""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai_core import create_ai_core
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.core.config import Settings
from app.domains.support_copilot.domain import wire_support_copilot
from app.domains.support_copilot.prompts import ROOT_CAUSE_TEMPLATE_V2
from app.main import create_app
from app.models import Base
from app.models.support import SupportTicket

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
USER_A = "550e8400-e29b-41d4-a716-446655440000"


class CountingProvider:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0

    def complete(self, *, system, user, model, temperature):
        self.calls += 1
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


def build_app(tmp_path, provider: CountingProvider) -> FastAPI:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        openai_api_key="test-key",
        supabase_jwt_secret=TEST_SECRET,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    run_store = SQLAlchemyRunRecordStore(app.state.session_factory)
    ai_core = create_ai_core(run_store=run_store)
    ai_core.llm_factory.register_provider("openai", provider)
    wire_support_copilot(ai_core)
    app.state.ai_core = ai_core
    return app


@pytest.fixture
def client(tmp_path):
    provider = CountingProvider(
        responses=[
            # First message: classify + troubleshoot.
            "hardware_issue",
            "Note the stop code and check what changed recently.",
            # Contextual follow-up: troubleshoot only.
            "Check recent Windows update history.",
            # Confirmation: root-cause summary only.
            "Issue: blue screen after Windows update\n"
            "Suspected Cause: driver or update incompatibility\n"
            "Actions Recommended: update history review, Safe Mode\n"
            "Actions Confirmed by the User: restart performed\n"
            "Outcome: system stable\n"
            "Unresolved Uncertainties: exact driver not identified",
        ]
    )
    app = build_app(tmp_path, provider)
    with TestClient(app) as test_client:
        yield test_client, app, provider


def create_session(client: TestClient):
    return client.post("/api/v1/support/sessions", headers=auth_headers())


def send(client: TestClient, session_id: str, message: str):
    return client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message},
        headers=auth_headers(),
    )


def test_initial_blue_screen_report_classifies_and_opens_ticket(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]

    response = send(test_client, session_id, "My laptop is displaying a blue screen.")

    data = response.json()["data"]
    assert data["issue_type"] == "hardware_issue"
    assert data["ticket"]["status"] == "Open"
    assert data["ticket"]["assigned_team"] == "Hardware Support"
    assert "### Issue Classification" in data["response"]


def test_contextual_follow_up_does_not_repeat_classification(client):
    test_client, _, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")

    response = send(
        test_client,
        session_id,
        "The blue screen started after a Windows update. The error code "
        "is CRITICAL_PROCESS_DIED.",
    )

    data = response.json()["data"]
    assert "### Issue Classification" not in data["response"]
    assert "update history" in data["response"]
    assert data["ticket"]["status"] == "In Progress"


def test_fix_report_skips_troubleshooting_and_asks_confirmation(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    send(test_client, session_id, "The error code is CRITICAL_PROCESS_DIED.")
    calls_before = provider.calls

    response = send(
        test_client, session_id, "It's working now, thanks for the help!"
    )

    data = response.json()["data"]
    assert provider.calls == calls_before  # no AI call on a fix report
    assert data["ticket"]["status"] == "Awaiting Confirmation"
    assert "Awaiting Confirmation" in data["response"]
    assert "Troubleshooting Response" not in data["response"]


def test_thanks_before_resolution_gets_acknowledgment(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    send(test_client, session_id, "It's working now, fixed")
    ticket_id = send(test_client, session_id, "It's working now").json()["data"][
        "ticket"
    ]["ticket_id"]
    calls_before = provider.calls

    response = send(test_client, session_id, "Thanks!")

    data = response.json()["data"]
    assert provider.calls == calls_before
    assert data["ticket"]["status"] == "Awaiting Confirmation"
    assert data["ticket"]["ticket_id"] == ticket_id
    assert "You're welcome" in data["response"]


def test_explicit_confirmation_resolves_with_suspected_cause(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    send(test_client, session_id, "The error code is CRITICAL_PROCESS_DIED.")
    send(test_client, session_id, "It's working now, fixed")
    ticket_id = send(test_client, session_id, "It's working now").json()["data"][
        "ticket"
    ]["ticket_id"]

    response = send(test_client, session_id, "Yes, confirmed, it is resolved")

    data = response.json()["data"]
    assert data["ticket"]["status"] == "Resolved"
    assert data["ticket"]["ticket_id"] == ticket_id
    assert data["status"] == "resolved"
    assert "marked as Resolved" in data["response"]
    assert "Suspected Cause: driver or update incompatibility" in data["response"]
    assert "Unresolved Uncertainties" in data["response"]
    assert "Actions Confirmed by the User" in data["response"]
    # The issue category remains the platform classification.
    assert data["issue_type"] == "hardware_issue"


def test_thanks_after_resolution_gets_closure_not_error(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    send(test_client, session_id, "The error code is CRITICAL_PROCESS_DIED.")
    send(test_client, session_id, "It's working now, fixed")
    send(test_client, session_id, "Yes, confirmed, it is resolved")
    calls_before = provider.calls

    response = send(test_client, session_id, "Thank you so much!")

    assert response.status_code == 201
    data = response.json()["data"]
    assert provider.calls == calls_before
    assert data["ticket"]["status"] == "Resolved"
    assert "You're welcome" in data["response"]
    assert "Start a new session" in data["response"]


def test_single_ticket_across_whole_conversation(client):
    test_client, app, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    send(test_client, session_id, "The error code is CRITICAL_PROCESS_DIED.")
    send(test_client, session_id, "It's working now, fixed")
    send(test_client, session_id, "Yes, confirmed, it is resolved")
    send(test_client, session_id, "Thank you!")

    with app.state.session_factory() as session:
        tickets = (
            session.query(SupportTicket)
            .filter(SupportTicket.session_id == session_id)
            .all()
        )
    assert len(tickets) == 1


def test_negated_fix_phrasing_still_troubleshoots(client):
    test_client, _, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    send(test_client, session_id, "My laptop is displaying a blue screen.")
    calls_before = provider.calls

    response = send(
        test_client, session_id, "No thanks, it is still not fixed"
    )

    data = response.json()["data"]
    assert provider.calls > calls_before  # troubleshooting ran
    assert data["ticket"]["status"] != "Awaiting Confirmation"


def test_root_cause_prompt_never_overstates_execution():
    template = ROOT_CAUSE_TEMPLATE_V2.user_template

    assert "Suspected Cause" in template
    assert "Actions Confirmed by the User" in template
    assert "Unresolved Uncertainties" in template
    assert "unless the user said so" in template
    assert "Never claim a root cause is confirmed" in template
