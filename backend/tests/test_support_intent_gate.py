"""Intent-gate and knowledge-grounding regression tests.

Covers the conversational gate added before issue classification:
greetings and unclear messages never create tickets or call the AI
provider; valid issues proceed through the workflow; follow-ups keep
the active issue context; explicitly new issues reclassify and update
the existing ticket without creating a second one; security escalation
is preserved; and troubleshooting prompts ground the model in the
retrieved knowledge base (or ask for clarification when it has no
relevant answer). No network calls are made.
"""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai_core import create_ai_core
from app.ai_core.prompts import PromptRegistry
from app.ai_core.run_records_db import SQLAlchemyRunRecordStore
from app.core.config import Settings
from app.domains.support_copilot.domain import wire_support_copilot
from app.domains.support_copilot.nodes import make_troubleshoot_node
from app.domains.support_copilot.prompts import register_prompts
from app.main import create_app
from app.models import Base
from app.models.support import SupportTicket

from tests.profile_test_helpers import seed_complete_profile

TEST_SECRET = "test-jwt-secret-0123456789abcdef0123456789abcdef0123456789abcdef"
USER_A = "550e8400-e29b-41d4-a716-446655440000"


class CountingProvider:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0

    def complete(self, *, system, user, model, temperature):
        self.calls += 1
        return self.responses.pop(0)


class ScriptedClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def complete(self, *, system, user):
        self.calls.append({"system": system, "user": user})
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
    ai_core.llm_factory.register_provider(settings.ai_provider_name, provider)
    wire_support_copilot(ai_core, settings)
    app.state.ai_core = ai_core
    return app


@pytest.fixture
def client(tmp_path):
    provider = CountingProvider()
    app = build_app(tmp_path, provider)
    seed_complete_profile(app, USER_A)
    with TestClient(app) as test_client:
        yield test_client, app, provider


def create_session(test_client: TestClient) -> str:
    return test_client.post("/api/v1/support/sessions", headers=auth_headers()).json()[
        "data"
    ]["session_id"]


def send(test_client: TestClient, session_id: str, message: str):
    return test_client.post(
        f"/api/v1/support/sessions/{session_id}/messages",
        json={"message": message},
        headers=auth_headers(),
    )


def test_greeting_first_message_welcomes_without_ticket(client):
    test_client, _, provider = client
    session_id = create_session(test_client)

    response = send(test_client, session_id, "Hello")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] is None
    assert data["ticket"] is None
    assert "IT Support Copilot" in data["response"]
    assert provider.calls == 0


def test_unclear_first_message_asks_for_clarification_without_ticket(client):
    test_client, _, provider = client
    session_id = create_session(test_client)

    response = send(test_client, session_id, "hrllj")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] is None
    assert data["ticket"] is None
    assert "couldn't quite understand" in data["response"]
    assert provider.calls == 0


def test_ambiguous_first_message_asks_for_detail_without_ticket(client):
    test_client, _, provider = client
    session_id = create_session(test_client)

    response = send(test_client, session_id, "Help")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] is None
    assert data["ticket"] is None
    assert "need a bit more detail" in data["response"]
    assert provider.calls == 0


def test_vague_symptom_asks_for_detail_without_calling_provider(client):
    test_client, _, provider = client
    session_id = create_session(test_client)

    response = send(test_client, session_id, "Something is wrong")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] is None
    assert data["ticket"] is None
    assert "need a bit more detail" in data["response"]
    assert provider.calls == 0


def test_short_message_with_concrete_issue_is_still_classified(client):
    test_client, _, provider = client
    provider.responses = ["vpn_issue", "Reconnect the VPN client."]
    session_id = create_session(test_client)

    response = send(test_client, session_id, "VPN broken")

    data = response.json()["data"]
    assert data["issue_type"] == "vpn_issue"
    assert data["ticket"] is not None
    assert provider.calls == 1


def test_valid_issue_proceeds_through_workflow_and_opens_ticket(client):
    test_client, _, provider = client
    provider.responses = ["access_issue", "Check your folder permissions."]
    session_id = create_session(test_client)

    response = send(test_client, session_id, "I can't access the shared drive")

    data = response.json()["data"]
    assert data["issue_type"] == "access_issue"
    assert data["ticket"] is not None
    assert data["ticket"]["status"] == "Open"
    assert provider.calls == 1


def test_greeting_follow_up_preserves_active_issue_context(client):
    test_client, app, provider = client
    provider.responses = [
        "vpn_issue",
        "Try reconnecting the VPN client.",
    ]
    session_id = create_session(test_client)
    send(test_client, session_id, "My VPN won't connect")
    ticket_id = send(test_client, session_id, "The VPN error is 809").json()["data"][
        "ticket"
    ]["ticket_id"]
    calls_before = provider.calls

    response = send(test_client, session_id, "Hello")

    data = response.json()["data"]
    assert provider.calls == calls_before
    assert data["issue_type"] == "vpn_issue"
    assert data["ticket"]["ticket_id"] == ticket_id
    assert "vpn_issue" in data["response"]


def test_unclear_follow_up_asks_for_clarification_without_new_calls(client):
    test_client, _, provider = client
    provider.responses = ["vpn_issue", "Try reconnecting the VPN client."]
    session_id = create_session(test_client)
    send(test_client, session_id, "My VPN won't connect")
    calls_before = provider.calls

    response = send(test_client, session_id, "hrllj")

    data = response.json()["data"]
    assert provider.calls == calls_before
    assert data["issue_type"] == "vpn_issue"
    assert "couldn't quite understand" in data["response"]


def test_new_issue_reclassifies_and_updates_existing_ticket(client):
    test_client, app, provider = client
    provider.responses = [
        "access_issue",
        "Check your folder permissions.",
        "vpn_issue",
    ]
    session_id = create_session(test_client)
    send(test_client, session_id, "I can't access the shared drive")
    ticket_id = send(test_client, session_id, "It says access denied").json()["data"][
        "ticket"
    ]["ticket_id"]

    response = send(test_client, session_id, "I have a new issue: my VPN won't connect")

    data = response.json()["data"]
    assert data["issue_type"] == "vpn_issue"
    assert data["ticket"]["ticket_id"] == ticket_id
    assert "### Issue Classification" in data["response"]
    assert "vpn_issue" in data["response"]

    with app.state.session_factory() as session:
        tickets = (
            session.query(SupportTicket)
            .filter(SupportTicket.session_id == session_id)
            .all()
        )
    assert len(tickets) == 1
    assert tickets[0].issue_type == "vpn_issue"


def test_non_it_message_asks_for_clarification_without_ticket(client):
    test_client, app, provider = client
    provider.responses = ["not_an_it_issue"]
    session_id = create_session(test_client)

    response = send(test_client, session_id, "I am not feeling good")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["issue_type"] is None
    assert data["ticket"] is None
    assert "doesn't sound like an IT issue" in data["response"]
    # Classification alone ran — the troubleshoot step must not fire.
    assert provider.calls == 1

    with app.state.session_factory() as session:
        from app.models.support import SupportSession

        stored = session.get(SupportSession, session_id)
    assert stored.issue_type is None


def test_classify_node_accepts_not_an_it_issue_output():
    from app.domains.support_copilot.nodes import make_classify_issue_node

    node = make_classify_issue_node(
        ScriptedClient(["not_an_it_issue"]), make_registry()
    )

    output = node({"user_issue": "I am not feeling good"})

    assert output["issue_type"] == "not_an_it_issue"


def test_workflow_routes_non_it_to_clarification_without_troubleshooting():
    from app.domains.support_copilot.workflow import build_support_workflow

    client = ScriptedClient(["not_an_it_issue"])
    graph = build_support_workflow(client, make_registry())

    output = graph.invoke({"user_issue": "I am not feeling good"})

    assert output["resolution"] == (
        "That doesn't sound like an IT issue. I'm the IT Support Copilot. "
        "I can help with things like VPN problems, password resets, network "
        "connectivity, or device trouble. Is there an IT issue I can help "
        "you with?"
    )
    # Only the classifier invoked the client — no troubleshoot call.
    assert len(client.calls) == 1


def test_security_issue_still_escalates(client):
    test_client, _, provider = client
    provider.responses = ["security_issue", "Escalating."]
    session_id = create_session(test_client)

    response = send(test_client, session_id, "My account was hacked")

    data = response.json()["data"]
    assert data["issue_type"] == "security_issue"
    assert data["escalation_needed"] is True
    assert data["ticket"]["priority"] == "High"
    assert data["ticket"]["assigned_team"] == "Security Operations"


def make_registry():
    registry = PromptRegistry()
    register_prompts(registry)
    return registry


def test_troubleshoot_prompt_grounds_in_knowledge_base_content():
    client = ScriptedClient(["Follow the VPN guide."])
    node = make_troubleshoot_node(client, make_registry())

    node(
        {
            "knowledge_base": "VPN GUIDE: reconnect and reinstall",
            "conversation_history": "user: VPN broken",
            "issue_type": "vpn_issue",
            "user_issue": "VPN error 809",
        }
    )

    prompt = client.calls[0]["user"]
    assert "VPN GUIDE: reconnect and reinstall" in prompt


def test_troubleshoot_prompt_says_when_knowledge_base_has_no_answer():
    client = ScriptedClient(["Please describe the error message."])
    node = make_troubleshoot_node(client, make_registry())

    node(
        {
            "knowledge_base": "",
            "conversation_history": "user: strange access problem",
            "issue_type": "access_issue",
            "user_issue": "my system is broken somehow",
        }
    )

    prompt = client.calls[0]["user"]
    assert "no relevant guidance" in prompt
    assert "Never invent internal procedures" in prompt
    assert "clarifying questions" in prompt
