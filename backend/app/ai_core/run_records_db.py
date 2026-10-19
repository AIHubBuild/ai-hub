"""Database-backed run record store.

Implements the same ``RunRecordStore`` protocol as the in-memory store
(`ai_core/run_records.py`), so the workflow runner persists every AI
interaction to PostgreSQL in staging/production — and to SQLite during
local development — without any change to its public contract.
"""

from datetime import timezone

from sqlalchemy.orm import Session, sessionmaker

from app.ai_core.run_records import RunRecord, RunRecordStore, RunStatus
from app.models.ai_run_record import AIRunRecord


def _to_model(record: RunRecord) -> AIRunRecord:
    return AIRunRecord(
        run_id=record.run_id,
        user_id=record.user_id,
        domain=record.domain,
        workflow_id=record.workflow_id,
        prompt_id=record.prompt_id,
        prompt_version=record.prompt_version,
        model=record.model,
        thread_id=record.thread_id,
        input_state=record.input_state,
        output_state=record.output_state,
        status=record.status.value,
        error=record.error,
        error_category=record.error_category,
        latency_ms=record.latency_ms,
        created_at=record.created_at,
    )


def _from_model(model: AIRunRecord) -> RunRecord:
    created_at = model.created_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return RunRecord(
        run_id=model.run_id,
        user_id=model.user_id,
        domain=model.domain,
        workflow_id=model.workflow_id,
        prompt_id=model.prompt_id,
        prompt_version=model.prompt_version,
        model=model.model,
        thread_id=model.thread_id,
        input_state=model.input_state,
        output_state=model.output_state,
        status=RunStatus(model.status),
        error=model.error,
        error_category=model.error_category,
        latency_ms=model.latency_ms,
        created_at=created_at,
    )


class SQLAlchemyRunRecordStore:
    """Persistent RunRecordStore backed by SQLAlchemy sessions."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def save(self, record: RunRecord) -> RunRecord:
        with self._session_factory() as session:
            session.add(_to_model(record))
            session.commit()
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._session_factory() as session:
            model = session.get(AIRunRecord, run_id)
            return _from_model(model) if model is not None else None

    def list_for_user(self, user_id: str) -> list[RunRecord]:
        with self._session_factory() as session:
            rows = (
                session.query(AIRunRecord)
                .filter(AIRunRecord.user_id == user_id)
                .order_by(AIRunRecord.created_at.desc())
                .all()
            )
            return [_from_model(row) for row in rows]
