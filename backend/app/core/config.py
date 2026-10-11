from functools import lru_cache

from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables / .env.

    Works whether the process runs from `backend/` or the repo root:
    both locations are checked for an `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
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

    # OpenAI-compatible AI provider (resume_ats domain).
    # No key is required for the catalogue and health endpoints; the
    # ATS analysis endpoints respond 503 until a key is configured.
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = ""
    openai_timeout_seconds: float = 60.0

    # Upload limits (resume_ats domain).
    max_upload_size_mb: int = 5


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
