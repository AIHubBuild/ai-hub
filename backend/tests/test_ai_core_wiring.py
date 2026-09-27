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
