"""Database configuration tests for SQLite and Supabase PostgreSQL."""

import pytest

import app.db.session as session_module
from app.core.config import (
    DEFAULT_DATABASE_URL,
    DatabaseConfigError,
    Settings,
    normalize_database_url,
    validate_database_config,
)
from app.main import create_app

FAKE_POSTGRES_URL = (
    "postgresql+psycopg://test_user:test_password@db.example.com:5432/postgres"
)


def settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "ai_deployment": False,
        "_env_file": None,
        "database_url": DEFAULT_DATABASE_URL,
    }
    values.update(overrides)
    return Settings(**values)


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "ai_deployment": True,
        "ai_api_key": "test-openai-key",
        "ai_provider": "openai",
        "ai_base_url": "https://api.openai.com/v1",
        "ai_model": "gpt-4.1-mini",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_local_sqlite_is_allowed():
    config = settings()

    validate_database_config(config)

    assert config.sqlalchemy_database_url == DEFAULT_DATABASE_URL


def test_deployment_mode_requires_postgres():
    config = settings(ai_deployment=True)

    with pytest.raises(DatabaseConfigError):
        validate_database_config(config)


def test_production_requires_postgres():
    config = production_settings(database_url="sqlite:///./production.db")

    with pytest.raises(DatabaseConfigError):
        validate_database_config(config)


def test_production_accepts_postgres():
    config = production_settings(database_url=FAKE_POSTGRES_URL)

    validate_database_config(config)

    assert config.sqlalchemy_database_url == FAKE_POSTGRES_URL


def test_bare_postgresql_url_is_normalized_to_psycopg_3():
    normalized = normalize_database_url(
        "postgresql://user:password@db.example.com:5432/postgres"
    )

    assert normalized == (
        "postgresql+psycopg://user:password@db.example.com:5432/postgres"
    )


def test_postgres_alias_and_tls_query_are_preserved():
    normalized = normalize_database_url(
        "postgres://user:password@db.example.com:5432/postgres"
        "?sslmode=require"
    )

    assert normalized.startswith("postgresql+psycopg://")
    assert "sslmode=require" in normalized


@pytest.mark.parametrize(
    "url",
    [
        "mysql://user:password@db.example.com/app",
        "postgresql+psycopg2://user:password@db.example.com/app",
        "",
    ],
)
def test_unsupported_database_urls_are_rejected(url):
    with pytest.raises(DatabaseConfigError):
        normalize_database_url(url)


def test_database_and_jwt_secrets_are_not_in_settings_repr():
    config = production_settings(
        database_url=(
            "postgresql+psycopg://user:database-password@db.example.com/app"
        ),
        supabase_jwt_secret="jwt-signing-secret",
    )

    rendered = repr(config)

    assert "database-password" not in rendered
    assert "jwt-signing-secret" not in rendered


def test_engine_uses_normalized_url_and_pre_ping(monkeypatch):
    captured: dict = {}
    sentinel = object()

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(session_module, "create_engine", fake_create_engine)
    config = settings(
        database_url=(
            "postgresql://user:password@db.example.com:5432/postgres"
        )
    )

    engine = session_module.create_engine_from_settings(config)

    assert engine is sentinel
    assert captured["url"] == (
        "postgresql+psycopg://user:password@db.example.com:5432/postgres"
    )
    assert captured["kwargs"]["pool_pre_ping"] is True


def test_create_app_fails_fast_for_production_sqlite():
    config = production_settings(database_url="sqlite:///./production.db")

    with pytest.raises(DatabaseConfigError):
        create_app(config)


def test_create_app_accepts_production_postgres_without_connecting():
    config = production_settings(database_url=FAKE_POSTGRES_URL)

    application = create_app(config)

    assert application.state.settings is config
