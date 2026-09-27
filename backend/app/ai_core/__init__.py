"""Shared AI service layer (ai_core).

Used by every AI application domain; never by the frontend
(`docs/09_Migration_Analysis.md` §3.3). Provides:

- ``LLMClientFactory`` — provider-agnostic, per-domain model config.
- ``PromptRegistry`` — versioned prompt assets.
- ``WorkflowRunner`` — state→state workflow execution + run records.
- ``RunRecordStore`` — structured persistence of every AI interaction.

A single ``AICore`` aggregate is created by the app factory and exposed
to domains via the ``get_ai_core`` FastAPI dependency.
"""

from dataclasses import dataclass

from fastapi import Request

from app.ai_core.llm import (
    DomainModelConfig,
    DomainNotConfiguredError,
    LLMClient,
    LLMClientFactory,
    ProviderNotConfiguredError,
)
from app.ai_core.prompts import PromptNotFoundError, PromptRegistry, PromptTemplate
from app.ai_core.run_records import (
    InMemoryRunRecordStore,
    RunRecord,
    RunRecordStore,
    RunStatus,
)
from app.ai_core.workflows import (
    RunResult,
    Workflow,
    WorkflowNotFoundError,
    WorkflowRunner,
)

__all__ = [
    "AICore",
    "DomainModelConfig",
    "DomainNotConfiguredError",
    "InMemoryRunRecordStore",
    "LLMClient",
    "LLMClientFactory",
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptTemplate",
    "ProviderNotConfiguredError",
    "RunRecord",
    "RunRecordStore",
    "RunResult",
    "RunStatus",
    "Workflow",
    "WorkflowNotFoundError",
    "WorkflowRunner",
    "create_ai_core",
    "get_ai_core",
]


@dataclass
class AICore:
    """Aggregate of the shared AI services, injected per-application."""

    llm_factory: LLMClientFactory
    prompts: PromptRegistry
    workflows: WorkflowRunner
    run_records: RunRecordStore


def create_ai_core(
    provider_clients: dict[str, LLMClient] | None = None,
    run_store: RunRecordStore | None = None,
) -> AICore:
    """Build an AICore instance (empty registries; wired by domains)."""
    llm_factory = LLMClientFactory(provider_clients)
    store = run_store or InMemoryRunRecordStore()
    return AICore(
        llm_factory=llm_factory,
        prompts=PromptRegistry(),
        workflows=WorkflowRunner(llm_factory, store),
        run_records=store,
    )


def get_ai_core(request: Request) -> AICore:
    """FastAPI dependency returning the application's AICore aggregate."""
    return request.app.state.ai_core
