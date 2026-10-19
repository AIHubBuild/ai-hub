"""Workflow runner.

Runs registered state→state workflows headlessly and persists a run
record for every invocation (`docs/09_Migration_Analysis.md` §3.3, §3.4.2).
The ``Workflow`` contract matches LangGraph's ``invoke(state)`` shape, so
graphs attach here directly when the resume_ats domain lands in Phase 2;
a PostgreSQL checkpointer (thread/conversation ids) is added with the
database baseline.
"""

import logging
import time
from typing import Any, Callable

from pydantic import BaseModel

from app.ai_core.llm import DomainNotConfiguredError, LLMClientFactory
from app.ai_core.run_records import RunRecord, RunRecordStore, RunStatus

Workflow = Callable[[dict[str, Any]], dict[str, Any]]

logger = logging.getLogger(__name__)


class WorkflowNotFoundError(KeyError):
    """No workflow is registered under the requested id."""


class RunResult(BaseModel):
    """Outcome of one workflow invocation."""

    run_id: str
    output_state: dict[str, Any]


class WorkflowRunner:
    """Registry + runner for domain workflows, with run-record capture."""

    def __init__(
        self,
        llm_factory: LLMClientFactory,
        run_store: RunRecordStore,
        clock: Callable[[], float] = time.perf_counter,
    ):
        self._llm_factory = llm_factory
        self._run_store = run_store
        self._clock = clock
        self._workflows: dict[str, Workflow] = {}

    def register(self, workflow_id: str, workflow: Workflow) -> None:
        self._workflows[workflow_id] = workflow

    def run(
        self,
        workflow_id: str,
        state: dict[str, Any],
        *,
        user_id: str,
        domain: str,
        thread_id: str | None = None,
        prompt_id: str | None = None,
        prompt_version: int | None = None,
    ) -> RunResult:
        try:
            workflow = self._workflows[workflow_id]
        except KeyError:
            raise WorkflowNotFoundError(
                f"No workflow registered for workflow id '{workflow_id}'."
            ) from None

        record = RunRecord(
            user_id=user_id,
            domain=domain,
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            model=self._model_for(domain),
            thread_id=thread_id,
            input_state=dict(state),
        )

        started = self._clock()
        try:
            output_state = workflow(dict(state))
        except Exception as exc:
            record.status = RunStatus.ERROR
            record.error = f"{type(exc).__name__}: {exc}"
            record.error_category = type(exc).__name__
            record.latency_ms = self._elapsed_ms(started)
            # Metadata only: never log input/output state or exception
            # messages, which may contain user content or credentials.
            logger.error(
                "ai_workflow_failed workflow_id=%s domain=%s run_id=%s "
                "error_type=%s latency_ms=%d",
                workflow_id,
                domain,
                record.run_id,
                type(exc).__name__,
                record.latency_ms,
            )
            self._run_store.save(record)
            raise

        record.output_state = output_state
        record.latency_ms = self._elapsed_ms(started)
        saved = self._run_store.save(record)
        return RunResult(run_id=saved.run_id, output_state=output_state)

    def _model_for(self, domain: str) -> str | None:
        try:
            return self._llm_factory.get_config(domain).model
        except DomainNotConfiguredError:
            return None

    def _elapsed_ms(self, started: float) -> int:
        return int((self._clock() - started) * 1000)
