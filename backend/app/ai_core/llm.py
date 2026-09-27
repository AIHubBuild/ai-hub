"""LLM client factory.

The only sanctioned path from AI application domains to model providers
(`docs/09_Migration_Analysis.md` §3.3: no domain may bypass ai_core to
call providers directly). Provider specifics are isolated behind the
``LLMClient`` protocol so an evaluation layer can later swap models or
inject recorded responses (§3.4.3).
"""

from typing import Protocol

from pydantic import BaseModel


class LLMClient(Protocol):
    """Provider-agnostic completion interface.

    Concrete provider clients (an OpenAI client in a later slice, fakes
    in tests) implement this protocol.
    """

    def complete(
        self, *, system: str, user: str, model: str, temperature: float
    ) -> str:
        ...


class DomainNotConfiguredError(KeyError):
    """No model configuration is registered for the requested domain."""


class ProviderNotConfiguredError(RuntimeError):
    """The requested provider has no client implementation registered."""


class DomainModelConfig(BaseModel):
    """Per-domain model defaults (§3.3: per-domain model/temperature config)."""

    domain: str
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    temperature: float = 0.4
    max_retries: int = 2
    timeout_seconds: int = 60


class _BoundClient:
    """Client scoped to one domain.

    Applies the domain's model configuration on every call so domains
    never choose models themselves.
    """

    def __init__(self, provider_client: LLMClient, config: DomainModelConfig):
        self._provider = provider_client
        self.config = config

    def complete(self, *, system: str, user: str) -> str:
        return self._provider.complete(
            system=system,
            user=user,
            model=self.config.model,
            temperature=self.config.temperature,
        )


class LLMClientFactory:
    """Registry of provider clients and per-domain model configurations."""

    def __init__(self, provider_clients: dict[str, LLMClient] | None = None):
        self._providers: dict[str, LLMClient] = dict(provider_clients or {})
        self._configs: dict[str, DomainModelConfig] = {}

    def register_provider(self, name: str, client: LLMClient) -> None:
        self._providers[name] = client

    def register_config(self, config: DomainModelConfig) -> None:
        self._configs[config.domain] = config

    def get_config(self, domain: str) -> DomainModelConfig:
        try:
            return self._configs[domain]
        except KeyError:
            raise DomainNotConfiguredError(
                f"No model configuration registered for domain '{domain}'."
            ) from None

    def get_client(self, domain: str) -> LLMClient:
        config = self.get_config(domain)
        try:
            provider_client = self._providers[config.provider]
        except KeyError:
            raise ProviderNotConfiguredError(
                f"No client registered for provider '{config.provider}'."
            ) from None
        return _BoundClient(provider_client, config)
