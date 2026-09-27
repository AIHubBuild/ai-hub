"""Tests for the run-record store (ai_core/run_records.py)."""

from app.ai_core import InMemoryRunRecordStore, RunRecord, RunStatus

USER_A = "550e8400-e29b-41d4-a716-446655440000"
USER_B = "660e8400-e29b-41d4-a716-446655440001"


def make_record(user_id: str = USER_A, **overrides) -> RunRecord:
    defaults = dict(
        user_id=user_id,
        domain="resume_ats",
        workflow_id="resume_ats/ats_pipeline",
        input_state={"resume_text": "x"},
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


def test_save_and_get_round_trip():
    store = InMemoryRunRecordStore()
    record = make_record()

    saved = store.save(record)

    assert saved.run_id == record.run_id
    assert store.get(record.run_id) == record


def test_list_for_user_filters_by_user():
    store = InMemoryRunRecordStore()
    store.save(make_record(user_id=USER_A))
    store.save(make_record(user_id=USER_B))

    assert [r.user_id for r in store.list_for_user(USER_A)] == [USER_A]
    assert [r.user_id for r in store.list_for_user(USER_B)] == [USER_B]


def test_get_unknown_run_returns_none():
    store = InMemoryRunRecordStore()

    assert store.get("missing-run") is None


def test_run_status_values():
    assert RunStatus.SUCCESS.value == "success"
    assert RunStatus.ERROR.value == "error"
