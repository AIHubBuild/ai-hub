"""Provider and model configuration tests.

Pins the maintainable provider contract: DeepSeek defaults come from the
official OpenAI-compatible API, the API key is read from the environment
only (never embedded in source), legacy OPENAI_* names still load, and
both assistants follow the configured provider/model without code
changes.
"""

import pytest

from app.ai_core import ProviderNotConfiguredError
from app.core.config import (
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    ProductionProviderConfigError,
    Settings,
)
from app.domains.resume_ats.workflow import ATS_WORKFLOW_ID
from app.domains.support_copilot.workflow import SUPPORT_WORKFLOW_ID
from app.main import create_app

PRODUCTION_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@"
    "db.example.com:5432/postgres"
)

PROVIDER_ENV_NAMES = (
    "AI_PROVIDER",
    "AI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "AI_BASE_URL",
    "DEEPSEEK_BASE_URL",
    "OPENAI_BASE_URL",
    "AI_MODEL",
    "DEEPSEEK_MODEL",
    "OPENAI_MODEL",
    "AI_TIMEOUT_SECONDS",
    "OPENAI_TIMEOUT_SECONDS",
    "AI_THINKING",
    "AI_REASONING_EFFORT",
    "AI_DEPLOYMENT",
    "RESUME_ATS_MODEL",
    "SUPPORT_MODEL",
)


def clean_settings(monkeypatch, **env) -> Settings:
    """Build Settings from a clean environment (no local .env).

    Tests default to an explicit ``test`` environment and deployment
    mode disabled. Pass ``ENVIRONMENT=None`` to simulate a missing
    environment. Provider values must be set explicitly by each test;
    there is no implicit DeepSeek fallback in the application guard.
    """
    for name in PROVIDER_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("AI_DEPLOYMENT", "false")
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_defaults_are_the_official_deepseek_configuration(monkeypatch):
    settings = clean_settings(monkeypatch)

    assert settings.ai_provider_name == DEFAULT_AI_PROVIDER == "deepseek"
    assert settings.ai_base_url == DEFAULT_AI_BASE_URL == "https://api.deepseek.com"
    assert settings.ai_model == DEFAULT_AI_MODEL == "deepseek-flash"
    assert settings.ai_api_key == ""
    assert settings.resume_model == "deepseek-flash"
    assert settings.support_model_name == "deepseek-flash"


def test_deepseek_api_key_loads_from_environment(monkeypatch):
    settings = clean_settings(monkeypatch, DEEPSEEK_API_KEY="test-deepseek-key")

    assert settings.ai_api_key == "test-deepseek-key"


def test_generic_ai_key_takes_precedence_over_provider_specific_names(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        AI_API_KEY="generic-key",
        DEEPSEEK_API_KEY="deepseek-key",
        OPENAI_API_KEY="legacy-openai-key",
    )

    assert settings.ai_api_key == "generic-key"


def test_legacy_openai_names_are_still_accepted(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        OPENAI_API_KEY="legacy-key",
        OPENAI_BASE_URL="https://api.openai.com/v1",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TIMEOUT_SECONDS="45",
    )

    assert settings.ai_api_key == "legacy-key"
    assert settings.ai_base_url == "https://api.openai.com/v1"
    assert settings.ai_model == "gpt-4.1-mini"
    assert settings.ai_timeout_seconds == 45.0


def test_model_can_be_changed_without_code_changes(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        AI_PROVIDER="openai-compatible",
        AI_BASE_URL="https://provider.example.com/v1",
        AI_MODEL="provider-model",
        RESUME_ATS_MODEL="resume-model",
        SUPPORT_MODEL="support-model",
    )

    assert settings.ai_provider_name == "openai-compatible"
    assert settings.resume_model == "resume-model"
    assert settings.support_model_name == "support-model"


def test_thinking_is_auto_disabled_for_deepseek(monkeypatch):
    # DeepSeek enables thinking by default and ignores temperature in
    # that mode. The default resolves to disabled so per-assistant
    # temperatures remain meaningful.
    settings = clean_settings(monkeypatch)

    assert settings.thinking_mode is False
    assert settings.reasoning_effort is None


def test_thinking_is_left_to_non_deepseek_providers(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
    )

    assert settings.thinking_mode is None


def test_thinking_and_reasoning_effort_are_explicitly_configurable(monkeypatch):
    settings = clean_settings(
        monkeypatch,
        AI_THINKING="true",
        AI_REASONING_EFFORT="max",
    )

    assert settings.thinking_mode is True
    assert settings.reasoning_effort == "max"


def test_api_key_is_not_in_settings_repr(monkeypatch):
    settings = clean_settings(monkeypatch, AI_API_KEY="super-secret-value")

    assert "super-secret-value" not in repr(settings)


def test_app_wires_both_assistants_to_the_configured_provider_and_model(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'provider.db'}",
    )

    app = create_app(settings)
    factory = app.state.ai_core.llm_factory

    resume_config = factory.get_config("resume_ats")
    support_config = factory.get_config("support_copilot")
    assert resume_config.provider == "deepseek"
    assert support_config.provider == "deepseek"
    assert resume_config.model == "deepseek-flash"
    assert support_config.model == "deepseek-flash"
    # Both clients resolve, proving the provider is registered under the
    # configured name (no network call is made).
    factory.get_client("resume_ats")
    factory.get_client("support_copilot")


def test_missing_api_key_disables_workflows_without_embedding_a_key(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        AI_API_KEY="",
        DATABASE_URL=f"sqlite:///{tmp_path / 'no-key.db'}",
    )

    app = create_app(settings)
    factory = app.state.ai_core.llm_factory

    with pytest.raises(ProviderNotConfiguredError):
        factory.get_client("resume_ats")
    with pytest.raises(ProviderNotConfiguredError):
        factory.get_client("support_copilot")
    assert ATS_WORKFLOW_ID not in app.state.ai_core.workflows._workflows
    assert SUPPORT_WORKFLOW_ID not in app.state.ai_core.workflows._workflows


def production_settings(monkeypatch, tmp_path, **overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "AI_DEPLOYMENT": "true",
        "AI_API_KEY": "test-production-key",
        "DATABASE_URL": PRODUCTION_DATABASE_URL,
    }
    values.update(overrides)
    return clean_settings(monkeypatch, **values)


def test_production_missing_provider_config_fails_safely(tmp_path, monkeypatch):
    settings = production_settings(monkeypatch, tmp_path)

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    message = str(exc_info.value)
    assert "OpenAI" in message
    assert "test-production-key" not in message


def test_production_legacy_openai_key_alone_fails_safely(tmp_path, monkeypatch):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="production",
        OPENAI_API_KEY="legacy-production-key",
        DATABASE_URL=f"sqlite:///{tmp_path / 'legacy.db'}",
    )

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    assert "legacy-production-key" not in str(exc_info.value)


@pytest.mark.parametrize(
    "overrides",
    [
        # Missing provider/base URL/model, even with an API key present.
        {"AI_PROVIDER": "openai"},
        {"AI_BASE_URL": "https://api.openai.com/v1", "AI_MODEL": "gpt-4.1-mini"},
        # Explicit DeepSeek provider.
        {
            "AI_PROVIDER": "deepseek",
            "AI_BASE_URL": "https://api.deepseek.com",
            "AI_MODEL": "deepseek-flash",
        },
        # OpenAI provider name but DeepSeek endpoint.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.deepseek.com",
            "AI_MODEL": "gpt-4.1-mini",
        },
        # OpenAI endpoint but DeepSeek model.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com/v1",
            "AI_MODEL": "deepseek-flash",
        },
        # Invalid provider name.
        {
            "AI_PROVIDER": "invalid-provider",
            "AI_BASE_URL": "https://api.openai.com/v1",
            "AI_MODEL": "gpt-4.1-mini",
        },
        # Lookalike host must not pass.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com.evil/v1",
            "AI_MODEL": "gpt-4.1-mini",
        },
        # Non-standard port must not pass.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com:444/v1",
            "AI_MODEL": "gpt-4.1-mini",
        },
        # Malformed port must fail safely.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com:notaport/v1",
            "AI_MODEL": "gpt-4.1-mini",
        },
        # Per-assistant DeepSeek override.
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com/v1",
            "AI_MODEL": "gpt-4.1-mini",
            "RESUME_ATS_MODEL": "deepseek-flash",
        },
        {
            "AI_PROVIDER": "openai",
            "AI_BASE_URL": "https://api.openai.com/v1",
            "AI_MODEL": "gpt-4.1-mini",
            "SUPPORT_MODEL": "deepseek-flash",
        },
    ],
)
def test_production_invalid_provider_config_fails_safely(
    tmp_path, monkeypatch, overrides
):
    settings = production_settings(monkeypatch, tmp_path, **overrides)

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    assert "test-production-key" not in str(exc_info.value)


def test_production_valid_openai_config_is_accepted(tmp_path, monkeypatch):
    settings = production_settings(
        monkeypatch,
        tmp_path,
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"


def test_missing_environment_with_key_and_deepseek_defaults_fails(
    tmp_path, monkeypatch
):
    settings = production_settings(monkeypatch, tmp_path, ENVIRONMENT=None)

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    assert "test-production-key" not in str(exc_info.value)


@pytest.mark.parametrize(
    "environment", ["prodution", "productionn", "", "unknown"]
)
def test_invalid_environment_with_key_and_deepseek_defaults_fails(
    tmp_path, monkeypatch, environment
):
    settings = production_settings(
        monkeypatch, tmp_path, ENVIRONMENT=environment
    )

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    assert "test-production-key" not in str(exc_info.value)


def test_missing_environment_with_key_and_openai_config_is_accepted(
    tmp_path, monkeypatch
):
    settings = production_settings(
        monkeypatch,
        tmp_path,
        ENVIRONMENT=None,
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"


def test_missing_environment_without_key_and_deployment_mode_starts_without_provider(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT=None,
        AI_DEPLOYMENT="true",
        AI_API_KEY="",
        DATABASE_URL=PRODUCTION_DATABASE_URL,
    )

    app = create_app(settings)

    with pytest.raises(ProviderNotConfiguredError):
        app.state.ai_core.llm_factory.get_client("resume_ats")


def test_missing_environment_without_key_and_deployment_disabled_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT=None,
        AI_DEPLOYMENT=None,
        AI_API_KEY="",
        DATABASE_URL=f"sqlite:///{tmp_path / 'no-key-no-deployment.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


@pytest.mark.parametrize(
    "environment",
    ["development", "dev", "test", "testing"],
)
def test_explicit_local_environments_allow_explicit_deepseek(
    tmp_path, monkeypatch, environment
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT=environment,
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / f'{environment}.db'}",
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "deepseek"
    assert config.model == "deepseek-flash"


def test_local_environment_without_explicit_provider_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_API_KEY="test-key",
        DATABASE_URL=f"sqlite:///{tmp_path / 'local-no-provider.db'}",
    )

    with pytest.raises(ProductionProviderConfigError) as exc_info:
        create_app(settings)

    assert "test-key" not in str(exc_info.value)


def test_local_environment_with_partial_provider_config_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        DATABASE_URL=f"sqlite:///{tmp_path / 'local-partial.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_local_environment_with_empty_provider_value_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_API_KEY="test-key",
        AI_PROVIDER="",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'local-empty-provider.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_local_environment_with_explicit_openai_config_is_accepted(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_API_KEY="test-key",
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
        DATABASE_URL=f"sqlite:///{tmp_path / 'local-openai.db'}",
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"


def test_deployment_mode_rejects_deepseek_even_in_development(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'deployment-deepseek.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_deployment_mode_accepts_openai_even_in_development(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
        DATABASE_URL=PRODUCTION_DATABASE_URL,
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"


def test_deployment_mode_requires_explicit_provider(tmp_path, monkeypatch):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        DATABASE_URL=f"sqlite:///{tmp_path / 'deployment-no-provider.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_deployment_mode_rejects_missing_openai_configuration(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="openai",
        DATABASE_URL=f"sqlite:///{tmp_path / 'deployment-partial-openai.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


@pytest.mark.parametrize(
    "environment", [None, "production", "prod", "staging", "stage", "prodution"]
)
@pytest.mark.parametrize("deployment_value", [None, "false"])
def test_deployment_mode_required_outside_local_environments(
    tmp_path, monkeypatch, environment, deployment_value
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT=environment,
        AI_DEPLOYMENT=deployment_value,
        AI_API_KEY="test-key",
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
        DATABASE_URL=f"sqlite:///{tmp_path / 'deployment-required.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_local_development_without_deployment_mode_allows_explicit_deepseek(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="development",
        AI_DEPLOYMENT=None,
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'local-missing-deployment.db'}",
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "deepseek"
    assert config.model == "deepseek-flash"


def test_missing_environment_with_explicit_deepseek_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT=None,
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'missing-env-deepseek.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_misspelled_environment_with_explicit_deepseek_fails(
    tmp_path, monkeypatch
):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="prodution",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'misspelled-env.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_staging_with_explicit_deepseek_fails(tmp_path, monkeypatch):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="staging",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'staging-deepseek.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_production_with_explicit_deepseek_fails(tmp_path, monkeypatch):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="production",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="deepseek",
        AI_BASE_URL="https://api.deepseek.com",
        AI_MODEL="deepseek-flash",
        DATABASE_URL=f"sqlite:///{tmp_path / 'production-deepseek.db'}",
    )

    with pytest.raises(ProductionProviderConfigError):
        create_app(settings)


def test_staging_with_openai_config_is_accepted(tmp_path, monkeypatch):
    settings = clean_settings(
        monkeypatch,
        ENVIRONMENT="staging",
        AI_DEPLOYMENT="true",
        AI_API_KEY="test-key",
        AI_PROVIDER="openai",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_MODEL="gpt-4.1-mini",
        DATABASE_URL=PRODUCTION_DATABASE_URL,
    )

    app = create_app(settings)
    config = app.state.ai_core.llm_factory.get_config("resume_ats")

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-mini"
