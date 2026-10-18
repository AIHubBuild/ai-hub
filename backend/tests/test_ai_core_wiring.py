"""Tests for AICore wiring into the application factory."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.ai_core import AICore, get_ai_core
from app.main import create_app


def test_app_factory_exposes_ai_core_on_state():
    app = create_app()

    core = app.state.ai_core
    assert isinstance(core, AICore)
    assert core.llm_factory is not None
    assert core.prompts is not None
    assert core.workflows is not None
    assert core.run_records is not None


def test_get_ai_core_dependency_returns_app_instance():
    app = create_app()
    state = app.state.ai_core

    @app.get("/core-check")
    async def core_check(core: AICore = Depends(get_ai_core)):
        return {"same_instance": core is state}

    client = TestClient(app)
    response = client.get("/core-check")

    assert response.status_code == 200
    assert response.json() == {"same_instance": True}


def test_support_model_is_configurable_via_settings():
    from app.ai_core import create_ai_core
    from app.core.config import Settings
    from app.domains.support_copilot.domain import wire_support_copilot

    ai_core = create_ai_core()
    wire_support_copilot(
        ai_core,
        Settings(ai_provider="deepseek", support_model="deepseek-flash"),
    )

    config = ai_core.llm_factory.get_config("support_copilot")
    assert config.model == "deepseek-flash"
    assert config.provider == "deepseek"


def test_resume_model_falls_back_to_shared_ai_model():
    from app.ai_core import create_ai_core
    from app.core.config import Settings
    from app.domains.resume_ats.domain import wire_resume_ats
    from app.domains.support_copilot.domain import wire_support_copilot

    ai_core = create_ai_core()
    settings = Settings(
        _env_file=None,
        ai_provider="deepseek",
        ai_model="deepseek-flash",
        resume_ats_model="",
        support_model="",
    )
    wire_resume_ats(ai_core, settings)
    wire_support_copilot(ai_core, settings)

    assert ai_core.llm_factory.get_config("resume_ats").model == "deepseek-flash"
    assert (
        ai_core.llm_factory.get_config("support_copilot").model
        == "deepseek-flash"
    )


def test_per_assistant_models_override_shared_model():
    from app.core.config import Settings

    settings = Settings(
        ai_model="shared-model",
        resume_ats_model="resume-model",
        support_model="support-model",
    )

    assert settings.resume_model == "resume-model"
    assert settings.support_model_name == "support-model"
