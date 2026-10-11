"""Support Copilot domain wiring.

Registers the domain's assets with the shared ai_core layer during
application startup: versioned prompts, the domain model configuration,
and the compiled workflows (full graph + follow-up steps). The provider
client itself is registered once in `app/main.py`; the domain only
consumes it through ai_core.
"""

from app.ai_core import (
    AICore,
    DomainModelConfig,
    DomainNotConfiguredError,
    ProviderNotConfiguredError,
)
from app.domains.support_copilot.prompts import register_prompts
from app.domains.support_copilot.workflow import (
    ROOT_CAUSE_STEP_ID,
    SUPPORT_WORKFLOW_ID,
    TROUBLESHOOT_STEP_ID,
    build_support_workflow,
    make_root_cause_step,
    make_troubleshoot_step,
)

DOMAIN = "support_copilot"
PROVIDER = "openai"


def wire_support_copilot(ai_core: AICore) -> None:
    """Register prompts, model config, and workflows."""
    register_prompts(ai_core.prompts)

    ai_core.llm_factory.register_config(
        DomainModelConfig(
            domain=DOMAIN,
            provider=PROVIDER,
            model="gpt-4o-mini",
            temperature=0.0,
            timeout_seconds=60,
        )
    )

    try:
        client = ai_core.llm_factory.get_client(DOMAIN)
    except (DomainNotConfiguredError, ProviderNotConfiguredError):
        client = None

    if client is not None:
        graph = build_support_workflow(client, ai_core.prompts)
        ai_core.workflows.register(SUPPORT_WORKFLOW_ID, graph.invoke)
        ai_core.workflows.register(
            TROUBLESHOOT_STEP_ID, make_troubleshoot_step(client, ai_core.prompts)
        )
        ai_core.workflows.register(
            ROOT_CAUSE_STEP_ID, make_root_cause_step(client, ai_core.prompts)
        )
