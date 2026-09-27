from functools import lru_cache

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

    # Supabase (Authentication + PostgreSQL + Storage) — introduced in
    # Phase 1. All fields are optional: local development works without
    # a Supabase project; protected endpoints simply cannot validate
    # tokens until `supabase_jwt_secret` is configured.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
