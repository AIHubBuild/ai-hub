"""Run records.

Every AI interaction is persisted in structured form — user, domain,
workflow, prompt id/version, model, input/output state, latency — as the
substrate for both product features (history) and the future evaluation
layer (`docs/09_Migration_Analysis.md` §3.3, §3.4.1).

Storage is a protocol: the in-memory implementation here serves tests
and local development; a database-backed store is introduced with the
Alembic baseline in a later slice.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class RunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    domain: str
    workflow_id: str
    prompt_id: str | None = None
    prompt_version: int | None = None
    model: str | None = None
    thread_id: str | None = None
    input_state: dict[str, Any]
    output_state: dict[str, Any] | None = None
    status: RunStatus = RunStatus.SUCCESS
    error: str | None = None
    latency_ms: int = 0
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RunRecordStore(Protocol):
    """Persistence contract for run records (DB-backed later)."""

    def save(self, record: RunRecord) -> RunRecord:
        ...

    def get(self, run_id: str) -> RunRecord | None:
        ...

    def list_for_user(self, user_id: str) -> list[RunRecord]:
        ...


class InMemoryRunRecordStore:
    """In-memory store for tests and local development only."""

    def __init__(self):
        self._records: dict[str, RunRecord] = {}

    def save(self, record: RunRecord) -> RunRecord:
        self._records[record.run_id] = record
        return record

    def get(self, run_id: str) -> RunRecord | None:
        return self._records.get(run_id)

    def list_for_user(self, user_id: str) -> list[RunRecord]:
        return sorted(
            (r for r in self._records.values() if r.user_id == user_id),
            key=lambda r: r.created_at,
            reverse=True,
        )
