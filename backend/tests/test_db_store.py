"""Tests for the DB-backed run record store and its ai_core integration."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai_core import (
    DomainModelConfig,
    LLMClientFactory,
    RunRecord,
    RunStatus,
    SQLAlchemyRunRecordStore,
    WorkflowRunner,
)

USER_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    from app.models import Base

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def make_record(**overrides) -> RunRecord:
    defaults = dict(
        user_id=USER_ID,
        domain="resume_ats",
        workflow_id="resume_ats/ats_pipeline",
        prompt_id="resume_ats/ats_analysis",
        prompt_version=1,
        model="gpt-4.1-mini",
        input_state={"resume_text": "abc", "job_description": "jd"},
        output_state={"ats_score": 82},
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def test_save_and_get_round_trip(session_factory):
    store = SQLAlchemyRunRecordStore(session_factory)
    record = make_record()

    saved = store.save(record)

    assert saved.run_id == record.run_id
    fetched = store.get(record.run_id)
    assert fetched == record
    assert fetched.input_state == {"resume_text": "abc", "job_description": "jd"}
    assert fetched.output_state == {"ats_score": 82}


def test_get_unknown_run_returns_none(session_factory):
    store = SQLAlchemyRunRecordStore(session_factory)

    assert store.get("missing-run-id") is None


def test_list_for_user_filters_and_orders_descending(session_factory):
    store = SQLAlchemyRunRecordStore(session_factory)
    older = make_record(
        user_id=USER_ID,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = make_record(
        user_id=USER_ID,
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    other_user = make_record(
        user_id="660e8400-e29b-41d4-a716-446655440001",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    store.save(older)
    store.save(newer)
    store.save(other_user)

    records = store.list_for_user(USER_ID)

    assert [r.run_id for r in records] == [newer.run_id, older.run_id]


def test_error_record_round_trip(session_factory):
    store = SQLAlchemyRunRecordStore(session_factory)
    record = make_record(
        output_state=None, status=RunStatus.ERROR, error="ValueError: bad text"
    )

    store.save(record)

    fetched = store.get(record.run_id)
    assert fetched.status is RunStatus.ERROR
    assert fetched.error == "ValueError: bad text"
    assert fetched.output_state is None


def test_records_persist_across_store_instances(tmp_path, session_factory):
    store_a = SQLAlchemyRunRecordStore(session_factory)
    record = make_record()
    store_a.save(record)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    fresh_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store_b = SQLAlchemyRunRecordStore(fresh_factory)

    assert store_b.get(record.run_id) == record


def test_workflow_runner_persists_through_sql_store(session_factory):
    factory = LLMClientFactory()
    factory.register_config(
        DomainModelConfig(domain="resume_ats", model="gpt-4.1-mini", temperature=0.4)
    )
    store = SQLAlchemyRunRecordStore(session_factory)
    runner = WorkflowRunner(factory, store)

    def echo(state: dict) -> dict:
        return {"result": state.get("resume_text")}

    runner.register("resume_ats/ats_pipeline", echo)

    result = runner.run(
        "resume_ats/ats_pipeline",
        {"resume_text": "abc"},
        user_id=USER_ID,
        domain="resume_ats",
        prompt_id="resume_ats/ats_analysis",
        prompt_version=1,
    )

    record = store.get(result.run_id)
    assert record is not None
    assert record.model == "gpt-4.1-mini"
    assert record.output_state == {"result": "abc"}
    assert record.status is RunStatus.SUCCESS
