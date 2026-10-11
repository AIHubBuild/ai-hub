"""Assistant catalogue registry.

Static seed data for v0.1. Facts verified against the product
repositories (no assumptions):

- None of the products has a verified hosted deployment URL.
  `launch_url` is therefore null for all entries. A launch URL may only
  be added once a real deployment exists.
- `repository_url` is a reference link only, never presented as a
  launch destination.
- The AI Testing Framework is an internal QA/developer tool, not a
  user-facing assistant. It is intentionally excluded from the public
  catalogue and remains available for future internal testing and
  platform validation.
"""

from .schemas import AssistantCatalogueEntry

ASSISTANTS: list[AssistantCatalogueEntry] = [
    AssistantCatalogueEntry(
        id="resume-ats",
        name="ATS Resume Assistant",
        description=(
            "Analyzes a resume against a job description: ATS scoring, "
            "keyword matching, tailored resume and cover letter "
            "generation, with DOCX export. Integrated with AI Hub."
        ),
        status="available",
        capabilities=[
            "ATS resume analysis",
            "Keyword matching",
            "Tailored cover letter",
            "DOCX export",
        ],
        launch_url=None,
        repository_url="https://github.com/akinselureabiola/ATS-Resume-Assistant",
        app_path="/apps/resume-ats",
    ),
    AssistantCatalogueEntry(
        id="it-support-copilot",
        name="AI IT Support Copilot",
        description=(
            "Guided IT helpdesk assistant: classifies issues, retrieves "
            "knowledge-base guidance, troubleshoots, and tracks ticket "
            "lifecycle through resolution or escalation. Integrated with "
            "AI Hub."
        ),
        status="available",
        capabilities=[
            "Issue classification",
            "Knowledge-base troubleshooting",
            "Ticket lifecycle",
            "Escalation handling",
        ],
        launch_url=None,
        repository_url="https://github.com/akinselureabiola/AI-IT-Support-Copilot",
        app_path="/apps/support",
    ),
]


def get_catalogue() -> list[AssistantCatalogueEntry]:
    return ASSISTANTS
