"""Tests for the LLM client factory (ai_core/llm.py)."""

import pytest

from app.ai_core.llm import (
    DomainModelConfig,
    DomainNotConfiguredError,
    LLMClientFactory,
    ProviderNotConfiguredError,
)


class FakeProviderClient:
    """Provider fake: records calls, returns canned completions."""

    def __init__(self, response: str = "fake-completion"):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str, model: str, temperature: float) -> str:
        self.calls.append(
            {"system": system, "user": user, "model": model, "temperature": temperature}
        )
        return self.response


def make_factory() -> tuple[LLMClientFactory, FakeProviderClient]:
    provider = FakeProviderClient()
    factory = LLMClientFactory(provider_clients={"openai": provider})
    return factory, provider


def test_get_client_applies_domain_model_configuration():
    factory, provider = make_factory()
    factory.register_config(
        DomainModelConfig(
            domain="resume_ats", model="gpt-4.1-mini", temperature=0.4
        )
    )

    client = factory.get_client("resume_ats")
    result = client.complete(system="sys", user="usr")

    assert result == "fake-completion"
    assert provider.calls == [
        {
            "system": "sys",
            "user": "usr",
            "model": "gpt-4.1-mini",
            "temperature": 0.4,
        }
    ]


def test_get_client_unknown_domain_raises():
    factory, _ = make_factory()

    with pytest.raises(DomainNotConfiguredError):
        factory.get_client("resume_ats")


def test_get_client_unregistered_provider_raises():
    factory, _ = make_factory()
    factory.register_config(DomainModelConfig(domain="resume_ats", provider="openai"))

    factory2 = LLMClientFactory()  # no providers registered
    factory2.register_config(DomainModelConfig(domain="resume_ats"))

    with pytest.raises(ProviderNotConfiguredError):
        factory2.get_client("resume_ats")


def test_domains_are_configured_independently():
    factory, provider = make_factory()
    factory.register_config(
        DomainModelConfig(domain="resume_ats", model="gpt-4.1-mini", temperature=0.4)
    )
    factory.register_config(
        DomainModelConfig(domain="career_coach", model="gpt-4.1", temperature=0.7)
    )

    factory.get_client("resume_ats").complete(system="s", user="u")
    factory.get_client("career_coach").complete(system="s", user="u")

    assert provider.calls[0]["model"] == "gpt-4.1-mini"
    assert provider.calls[0]["temperature"] == 0.4
    assert provider.calls[1]["model"] == "gpt-4.1"
    assert provider.calls[1]["temperature"] == 0.7
