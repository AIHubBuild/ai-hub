"""Resume ATS domain wiring.

Registers the domain's assets with the shared ai_core layer during
application startup: versioned prompts, the domain model configuration,
and the compiled ATS workflow. The provider client itself is registered
once in `app/main.py`; the domain only consumes it through ai_core.
"""

from app.ai_core import (
    AICore,
    DomainModelConfig,
    DomainNotConfiguredError,
    ProviderNotConfiguredError,
)
from app.core.config import Settings
from app.domains.resume_ats.prompts import register_prompts
from app.domains.resume_ats.workflow import ATS_WORKFLOW_ID, build_ats_workflow

DOMAIN = "resume_ats"
PROVIDER = "openai"


def wire_resume_ats(ai_core: AICore, settings: Settings) -> None:
    """Register prompts, model config, and workflow."""
    register_prompts(ai_core.prompts)

    ai_core.llm_factory.register_config(
        DomainModelConfig(
            domain=DOMAIN,
            provider=PROVIDER,
            model=settings.openai_model,
            temperature=0.4,
            timeout_seconds=int(settings.openai_timeout_seconds),
        )
    )

    try:
        client = ai_core.llm_factory.get_client(DOMAIN)
    except (DomainNotConfiguredError, ProviderNotConfiguredError):
        # No provider configured: the analysis endpoint reports 503.
        client = None

    if client is not None:
        graph = build_ats_workflow(client, ai_core.prompts)
        ai_core.workflows.register(ATS_WORKFLOW_ID, graph.invoke)
