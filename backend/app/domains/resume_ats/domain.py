"""Resume ATS domain wiring.

Registers the domain's assets with the shared ai_core layer during
application startup: versioned prompts, the domain model configuration,
the OpenAI provider client (when a key is configured), and the compiled
ATS workflow. Called once from `app/main.py` — the domain never talks
to a provider directly.
"""

from app.ai_core import (
    AICore,
    DomainModelConfig,
    DomainNotConfiguredError,
    ProviderNotConfiguredError,
)
from app.ai_core.providers.openai import OpenAIProvider
from app.core.config import Settings
from app.domains.resume_ats.prompts import register_prompts
from app.domains.resume_ats.workflow import ATS_WORKFLOW_ID, build_ats_workflow

DOMAIN = "resume_ats"
PROVIDER = "openai"


def wire_resume_ats(ai_core: AICore, settings: Settings) -> None:
    """Register prompts, provider, model config, and workflow."""
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

    if settings.openai_api_key:
        ai_core.llm_factory.register_provider(
            PROVIDER,
            OpenAIProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout_seconds=settings.openai_timeout_seconds,
            ),
        )

    try:
        client = ai_core.llm_factory.get_client(DOMAIN)
    except (DomainNotConfiguredError, ProviderNotConfiguredError):
        # No provider configured: the analysis endpoint reports 503.
        client = None

    if client is not None:
        graph = build_ats_workflow(client, ai_core.prompts)
        ai_core.workflows.register(ATS_WORKFLOW_ID, graph.invoke)
