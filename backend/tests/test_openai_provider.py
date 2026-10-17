"""Tests for the OpenAI-compatible provider client (httpx, no network)."""

import httpx
import pytest

from app.ai_core.providers.openai import OpenAIProvider, ProviderError


def provider(response_json=None, status_code=200, transport=None, **kwargs):
    if transport is None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                status_code,
                json=response_json
                if response_json is not None
                else {
                    "choices": [{"message": {"content": "Hello from the model."}}]
                },
            )
        )
    return OpenAIProvider(api_key="test-key", client=httpx.Client(transport=transport), **kwargs)


def test_complete_returns_model_content():
    client = provider()
    result = client.complete(
        system="You are helpful.", user="Hi", model="gpt-4.1-mini", temperature=0.4
    )
    assert result == "Hello from the model."


def test_complete_sends_bearer_auth_and_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    client = provider(transport=httpx.MockTransport(handler), base_url="https://api.example.com/v1")
    client.complete(system="sys", user="usr", model="m", temperature=0.0)

    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    assert '"model":"m"' in captured["body"]
    assert '"role":"system"' in captured["body"]


def test_deepseek_thinking_can_be_explicitly_disabled():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    client = provider(
        transport=httpx.MockTransport(handler),
        base_url="https://api.deepseek.com",
        thinking=False,
    )
    client.complete(system="sys", user="usr", model="deepseek-flash", temperature=0.0)

    assert '"thinking":{"type":"disabled"}' in captured["body"]
    assert "reasoning_effort" not in captured["body"]


def test_reasoning_effort_is_sent_only_with_thinking_enabled():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    client = provider(
        transport=httpx.MockTransport(handler),
        base_url="https://api.deepseek.com",
        thinking=True,
        reasoning_effort="high",
    )
    client.complete(system="sys", user="usr", model="deepseek-flash", temperature=0.0)

    assert '"thinking":{"type":"enabled"}' in captured["body"]
    assert '"reasoning_effort":"high"' in captured["body"]


def test_thinking_field_is_omitted_when_not_configured():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    client = provider(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com/v1",
    )
    client.complete(system="sys", user="usr", model="gpt-4.1-mini", temperature=0.4)

    assert "thinking" not in captured["body"]
    assert "reasoning_effort" not in captured["body"]


def test_non_200_raises_provider_error_with_status():
    client = provider(status_code=429, response_json={"error": {"message": "Rate limited"}})
    with pytest.raises(ProviderError, match="HTTP 429") as exc_info:
        client.complete(system="s", user="u", model="m", temperature=0.0)
    assert exc_info.value.status == 429


def test_malformed_payload_raises_provider_error():
    client = provider(response_json={"unexpected": True})
    with pytest.raises(ProviderError, match="unexpected response shape"):
        client.complete(system="s", user="u", model="m", temperature=0.0)


def test_empty_content_raises_provider_error():
    client = provider(response_json={"choices": [{"message": {"content": "  "}}]})
    with pytest.raises(ProviderError, match="empty completion"):
        client.complete(system="s", user="u", model="m", temperature=0.0)


def test_transport_failure_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = provider(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="request failed"):
        client.complete(system="s", user="u", model="m", temperature=0.0)


def test_api_key_never_appears_in_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = provider(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as exc_info:
        client.complete(system="s", user="u", model="m", temperature=0.0)
    assert "test-key" not in str(exc_info.value)
