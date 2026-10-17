from functools import lru_cache
from pathlib import Path

from fastapi import Request
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Official DeepSeek OpenAI-compatible endpoint (api-docs.deepseek.com).
# ``deepseek-flash`` is the documented model id served by
# DeepSeek-V4.1-Flash-1017. Both are defaults only: every value can be
# overridden from the environment without code changes.
DEFAULT_AI_PROVIDER = "deepseek"
DEFAULT_AI_BASE_URL = "https://api.deepseek.com"
DEFAULT_AI_MODEL = "deepseek-flash"


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env.

    Works whether the process runs from `backend/` or the repo root:
    both locations are checked for an `.env` file. Paths are anchored
    to this file so loading is independent of the working directory.
    """

    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_DIR / ".env"), str(_BACKEND_DIR.parent / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "AI Hub API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # Database (docs/05_Database_Design.md: PostgreSQL via Supabase).
    # Local development defaults to a gitignored SQLite file; staging and
    # production set DATABASE_URL to the Supabase PostgreSQL connection.
    database_url: str = "sqlite:///./aihub_dev.db"

    # Supabase (Authentication + PostgreSQL + Storage) — introduced in
    # Phase 1. All fields are optional: local development works without
    # a Supabase project; protected endpoints simply cannot validate
    # tokens until `supabase_jwt_secret` is configured.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    # Optional override for the Supabase JWKS endpoint. Defaults to
    # {supabase_url}/auth/v1/.well-known/jwks.json when unset.
    supabase_jwks_url: str = ""

    # OpenAI-compatible AI provider (shared by every assistant).
    #
    # DeepSeek is the default and the API key is read from the
    # environment only. ``repr=False`` keeps the key out of accidental
    # configuration dumps/logs. Legacy OPENAI_* names remain accepted as
    # fallbacks so existing local `.env` files keep working; the
    # AI_*/DEEPSEEK_* names take precedence.
    ai_provider: str = Field(
        default=DEFAULT_AI_PROVIDER,
        validation_alias=AliasChoices("AI_PROVIDER", "ai_provider"),
    )
    ai_api_key: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices(
            "AI_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ai_api_key",
            "deepseek_api_key",
            "openai_api_key",
        ),
    )
    ai_base_url: str = Field(
        default=DEFAULT_AI_BASE_URL,
        validation_alias=AliasChoices(
            "AI_BASE_URL",
            "DEEPSEEK_BASE_URL",
            "OPENAI_BASE_URL",
            "ai_base_url",
            "deepseek_base_url",
            "openai_base_url",
        ),
    )
    ai_model: str = Field(
        default=DEFAULT_AI_MODEL,
        validation_alias=AliasChoices(
            "AI_MODEL",
            "DEEPSEEK_MODEL",
            "OPENAI_MODEL",
            "ai_model",
            "deepseek_model",
            "openai_model",
        ),
    )
    ai_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "AI_TIMEOUT_SECONDS",
            "OPENAI_TIMEOUT_SECONDS",
            "ai_timeout_seconds",
            "openai_timeout_seconds",
        ),
    )
    # DeepSeek enables thinking mode by default, where ``temperature`` is
    # ignored. ``None`` means "provider default"; an explicit true/false
    # sends ``thinking`` in the request. When unset, thinking is disabled
    # automatically for DeepSeek so per-assistant temperature applies.
    ai_thinking: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("AI_THINKING", "ai_thinking"),
    )
    # Optional DeepSeek reasoning effort (low/high/max); only sent when
    # thinking is enabled.
    ai_reasoning_effort: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AI_REASONING_EFFORT", "ai_reasoning_effort"
        ),
    )

    # Optional per-assistant model overrides. Both fall back to AI_MODEL,
    # so changing the provider model is a single environment change.
    resume_ats_model: str = Field(
        default="",
        validation_alias=AliasChoices("RESUME_ATS_MODEL", "resume_ats_model"),
    )
    support_model: str = Field(
        default="",
        validation_alias=AliasChoices("SUPPORT_MODEL", "support_model"),
    )

    # Upload limits (resume_ats domain).
    max_upload_size_mb: int = 5

    @property
    def ai_provider_name(self) -> str:
        """Registry name for the configured OpenAI-compatible provider."""
        return (self.ai_provider or "").strip() or DEFAULT_AI_PROVIDER

    @property
    def resume_model(self) -> str:
        return (self.resume_ats_model or self.ai_model).strip() or DEFAULT_AI_MODEL

    @property
    def support_model_name(self) -> str:
        return (self.support_model or self.ai_model).strip() or DEFAULT_AI_MODEL

    @property
    def thinking_mode(self) -> bool | None:
        """Resolved thinking toggle for the configured provider.

        DeepSeek thinking mode is on by default server-side and ignores
        temperature. Auto-disabling it keeps the per-assistant
        temperature settings meaningful while leaving other
        OpenAI-compatible providers untouched.
        """
        if self.ai_thinking is not None:
            return self.ai_thinking
        if (
            self.ai_provider_name.lower() == "deepseek"
            or "deepseek" in self.ai_base_url.lower()
        ):
            return False
        return None

    @property
    def reasoning_effort(self) -> str | None:
        effort = (self.ai_reasoning_effort or "").strip().lower()
        return effort or None

    # Backwards-compatible read-only aliases for older call sites.
    @property
    def openai_api_key(self) -> str:
        return self.ai_api_key

    @property
    def openai_model(self) -> str:
        return self.ai_model

    @property
    def openai_base_url(self) -> str:
        return self.ai_base_url

    @property
    def openai_timeout_seconds(self) -> float:
        return self.ai_timeout_seconds


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_app_settings(request: Request) -> Settings:
    """FastAPI dependency: the settings instance bound to the app.

    Returns the exact Settings object the app factory was built with
    (see `app/main.py`), so tests and multi-environment setups get the
    intended configuration instead of a process-wide cached default.
    """
    return request.app.state.settings
