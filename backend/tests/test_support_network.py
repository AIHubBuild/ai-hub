"""Network-troubleshooting scenario regression tests.

Runs the full "laptop cannot connect to the internet" journey with a
scripted, prompt-capturing AI provider — no network calls. Verifies the
classification, targeted diagnostic question, contextual follow-up
(other devices work), ticket stability, and a resolution summary that
never overstates execution or confirms an unverified cause.
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
from app.main import create_app
from app.models import Base

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
USER_A = "550e8400-e29b-41d4-a716-446655440000"


class PromptCapturingProvider:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.user_prompts = []

    def complete(self, *, system, user, model, temperature):
        self.user_prompts.append(user)
        return self.responses.pop(0)


def make_token(user_id: str = USER_A) -> str:
    payload = {
        "sub": user_id,
        "email": "alex@example.com",
        "email_verified": True,
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers(user_id: str = USER_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
def client(tmp_path):
    provider = PromptCapturingProvider(
        responses=[
            # First message: classification only.
            "network_issue",
            # Contextual follow-up: troubleshooting.
            "Since other devices work, check the laptop's Wi-Fi adapter "
            "status and IP configuration with ipconfig /all.",
            # Confirmation: root-cause summary only.
            "Issue: laptop cannot reach the internet while other devices work\n"
            "Suspected Cause: wireless adapter misconfiguration\n"
            "Actions Recommended: adapter restart, ipconfig review\n"
            "Actions Confirmed by the User: reboot performed\n"
            "Outcome: connectivity restored\n"
            "Unresolved Uncertainties: root cause not confirmed",
        ]
    )
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
    with TestClient(app) as test_client:
        yield test_client, provider


def create_session(client: TestClient):
    return client.post("/api/v1/support/sessions", headers=auth_headers())


def send(client: TestClient, session_id: str, message: str):
    return client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message},
        headers=auth_headers(),
    )


def test_network_issue_asks_targeted_question(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]

    response = send(test_client, session_id, "My laptop cannot connect to the internet.")

    data = response.json()["data"]
    assert data["issue_type"] == "network_issue"
    assert data["ticket"]["status"] == "Open"
    assert "connect to Wi-Fi at all" in data["follow_up_question"]
    assert "web pages" in data["follow_up_question"]


def test_other_devices_working_narrows_to_laptop_checks(client):
    test_client, provider = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    first = send(
        test_client, session_id, "My laptop cannot connect to the internet."
    ).json()["data"]
    first_ticket_id = first["ticket"]["ticket_id"]

    response = send(
        test_client,
        session_id,
        "Other devices in the house can connect to the internet fine.",
    )

    data = response.json()["data"]
    assert data["ticket"]["status"] == "In Progress"
    assert data["ticket"]["ticket_id"] == first_ticket_id
    assert data["issue_type"] == "network_issue"
    assert "### Issue Classification" not in data["response"]
    assert "Wi-Fi adapter" in data["response"]

    # The troubleshoot prompt carried the new answer and the laptop-
    # specific knowledge base (contextual follow-up, no repetition).
    follow_up_prompt = provider.user_prompts[-1]
    assert "Other devices in the house" in follow_up_prompt
    assert "LAPTOP-SPECIFIC CHECKS" in follow_up_prompt


def test_network_ticket_resolution_keeps_id_and_never_overstates(client):
    test_client, _ = client
    session_id = create_session(test_client).json()["data"]["session_id"]
    first = send(
        test_client, session_id, "My laptop cannot connect to the internet."
    ).json()["data"]
    first_ticket_id = first["ticket"]["ticket_id"]
    send(test_client, session_id, "Other devices in the house can connect fine.")

    fix = send(test_client, session_id, "It's working now, fixed")
    assert fix.json()["data"]["ticket"]["status"] == "Awaiting Confirmation"

    response = send(test_client, session_id, "Yes, confirmed it is resolved")

    data = response.json()["data"]
    assert data["ticket"]["status"] == "Resolved"
    assert data["ticket"]["ticket_id"] == first_ticket_id
    assert data["issue_type"] == "network_issue"
    assert "Suspected Cause" in data["response"]
    assert "root cause not confirmed" in data["response"]
    assert "marked as Resolved" in data["response"]
