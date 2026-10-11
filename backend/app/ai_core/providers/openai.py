"""OpenAI-compatible chat completions client.

Implements the ``ai_core.LLMClient`` protocol against the OpenAI
Chat Completions REST API (also usable with OpenAI-compatible providers
via ``base_url``). Plain httpx — no SDK dependency, no provider coupling
in domain code.

The API key is injected at construction (from application settings)
and never logged, echoed, or exposed in errors.
"""

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0


class ProviderError(RuntimeError):
    """Raised when the AI provider cannot return a completion.

    ``status`` carries the HTTP status when the failure came from the
    provider API (None for transport/client-side failures).
    """

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class OpenAIProvider:
    """Provider client for OpenAI-compatible chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ):
        self._api_key = api_key
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds
        # Own client by default; tests inject a client with a mock transport.
        self._client = client or httpx.Client(timeout=self._timeout)

    def complete(
        self, *, system: str, user: str, model: str, temperature: float
    ) -> str:
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"AI provider request failed: {type(exc).__name__}."
            ) from exc

        if response.status_code != 200:
            raise ProviderError(
                f"AI provider returned HTTP {response.status_code}.",
                status=response.status_code,
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "AI provider returned an unexpected response shape."
            ) from exc

        if not content or not str(content).strip():
            raise ProviderError("AI provider returned an empty completion.")

        return str(content)
