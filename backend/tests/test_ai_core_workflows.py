"""Tests for the workflow runner (ai_core/workflows.py).

Shaped against the resume_ats domain per the approved Phase 0 decision
(docs/09 §8.1): a registered multi-step pipeline workflow with a
documented prompt id/version, executed headlessly with run records.
"""

import logging

import pytest

from app.ai_core import (
    DomainModelConfig,
    InMemoryRunRecordStore,
    LLMClientFactory,
    RunStatus,
    WorkflowRunner,
)

USER_ID = "550e8400-e29b-41d4-a716-446655440000"
DOMAIN = "resume_ats"
WORKFLOW_ID = "resume_ats/ats_pipeline"
PROMPT_ID = "resume_ats/ats_analysis"


def make_runner() -> tuple[WorkflowRunner, InMemoryRunRecordStore]:
    factory = LLMClientFactory()
    factory.register_config(
        DomainModelConfig(domain=DOMAIN, model="gpt-4.1-mini", temperature=0.4)
    )
    store = InMemoryRunRecordStore()
    runner = WorkflowRunner(factory, store)
    return runner, store


def echo_workflow(state: dict) -> dict:
    return {"result": f"processed: {state.get('resume_text', '')}"}


def test_run_executes_workflow_and_returns_result():
    runner, _ = make_runner()
    runner.register(WORKFLOW_ID, echo_workflow)

    result = runner.run(
        WORKFLOW_ID,
        {"resume_text": "abc"},
        user_id=USER_ID,
        domain=DOMAIN,
        prompt_id=PROMPT_ID,
        prompt_version=1,
    )

    assert result.output_state == {"result": "processed: abc"}
    assert result.run_id


def test_run_persists_structured_record():
    runner, store = make_runner()
    runner.register(WORKFLOW_ID, echo_workflow)

    result = runner.run(
        WORKFLOW_ID,
        {"resume_text": "abc"},
        user_id=USER_ID,
        domain=DOMAIN,
        thread_id="thread-1",
        prompt_id=PROMPT_ID,
        prompt_version=1,
    )

    record = store.get(result.run_id)
    assert record is not None
    assert record.user_id == USER_ID
    assert record.domain == DOMAIN
    assert record.workflow_id == WORKFLOW_ID
    assert record.prompt_id == PROMPT_ID
    assert record.prompt_version == 1
    assert record.thread_id == "thread-1"
    assert record.model == "gpt-4.1-mini"
    assert record.input_state == {"resume_text": "abc"}
    assert record.output_state == {"result": "processed: abc"}
    assert record.status is RunStatus.SUCCESS
    assert record.error is None
    assert record.latency_ms >= 0


def test_run_unknown_workflow_raises():
    runner, _ = make_runner()

    with pytest.raises(KeyError):
        runner.run(WORKFLOW_ID, {}, user_id=USER_ID, domain=DOMAIN)


def test_failing_workflow_records_error_and_reraises():
    runner, store = make_runner()

    def failing(state: dict) -> dict:
        raise ValueError("bad resume text")

    runner.register(WORKFLOW_ID, failing)

    with pytest.raises(ValueError):
        runner.run(WORKFLOW_ID, {}, user_id=USER_ID, domain=DOMAIN)

    records = store.list_for_user(USER_ID)
    assert len(records) == 1
    assert records[0].status is RunStatus.ERROR
    assert "ValueError" in records[0].error
    assert records[0].output_state is None


def test_failing_workflow_logs_safe_metadata_only(caplog):
    runner, _ = make_runner()

    def failing(state: dict) -> dict:
        raise ValueError("api_key=super-secret-value")

    runner.register(WORKFLOW_ID, failing)

    with caplog.at_level(logging.ERROR, logger="app.ai_core.workflows"):
        with pytest.raises(ValueError):
            runner.run(WORKFLOW_ID, {}, user_id=USER_ID, domain=DOMAIN)

    text = caplog.text
    assert "ai_workflow_failed" in text
    assert f"workflow_id={WORKFLOW_ID}" in text
    assert f"domain={DOMAIN}" in text
    assert "run_id=" in text
    assert "error_type=ValueError" in text
    assert "latency_ms=" in text
    assert "super-secret-value" not in text
    assert "api_key=" not in text


def test_run_record_model_is_none_for_unconfigured_domain():
    factory = LLMClientFactory()
    store = InMemoryRunRecordStore()
    runner = WorkflowRunner(factory, store)
    runner.register(WORKFLOW_ID, echo_workflow)

    result = runner.run(WORKFLOW_ID, {}, user_id=USER_ID, domain="career_coach")

    assert store.get(result.run_id).model is None


def test_run_does_not_mutate_caller_state():
    runner, _ = make_runner()
    seen: list = []

    def spy(state: dict) -> dict:
        seen.append(dict(state))  # snapshot of the input the workflow saw
        state["resume_text"] = "mutated"
        return {"done": True}

    runner.register(WORKFLOW_ID, spy)
    caller_state = {"resume_text": "original"}

    runner.run(WORKFLOW_ID, caller_state, user_id=USER_ID, domain=DOMAIN)

    assert caller_state == {"resume_text": "original"}
    assert seen[0] == {"resume_text": "original"}
