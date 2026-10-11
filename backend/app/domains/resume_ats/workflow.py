"""LangGraph workflow for the Resume ATS domain.

Implements the approved multi-step ATS pipeline
(`docs/09_Migration_Analysis.md` §8.1):

    deterministic analysis → AI recommendations → tailored resume → cover letter

Design rules honored here:

- The deterministic engine (`engine.py`) is the ONLY source of the ATS
  score and keyword lists; AI nodes read them, never compute them.
- Prompt templates come from the shared `ai_core` prompt registry; each
  AI node records the exact prompt version it used in the state.
- The workflow is headless: no FastAPI, no Streamlit, no provider
  coupling. LLM access goes through a small `ChatClient` protocol —
  satisfied by the bound clients returned by
  `ai_core.LLMClientFactory.get_client("resume_ats")` in a later slice,
  and by test doubles here.
- The compiled graph's `.invoke(state)` matches the
  `ai_core.WorkflowRunner` `Workflow` contract, so the graph registers
  with the shared runner without changes.
"""

from typing import Any, Callable, Protocol

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.ai_core.prompts import PromptRegistry
from app.domains.resume_ats.job_description import (
    describe_warning,
    strip_boilerplate,
)
from app.domains.resume_ats.matching import analyze_job_match
from app.domains.resume_ats.schemas import AtsAnalysisResult, RequirementEvidence

ATS_WORKFLOW_ID = "resume_ats/ats_pipeline"

PROMPT_IDS = {
    "analysis": "resume_ats/ats_analysis",
    "tailored_resume": "resume_ats/tailored_resume",
    "cover_letter": "resume_ats/cover_letter",
}

# Which state field each AI step writes.
_STEP_OUTPUT_FIELDS = {
    "analysis": "improvement_suggestions",
    "tailored_resume": "tailored_resume",
    "cover_letter": "cover_letter",
}


class AtsWorkflowState(TypedDict, total=False):
    """Typed state threaded through the ATS workflow graph."""

    resume_text: str
    job_description: str
    # Optional applicant-supplied style preferences.
    style_notes: str | None
    # Deterministic outputs (matching engine-owned).
    cleaned_job_description: str
    job_description_warning: str | None
    match_score: int
    score_label: str
    matching_keywords: list[str]
    partial_keywords: list[str]
    missing_keywords: list[str]
    requirement_evidence: dict[str, dict]
    score_breakdown: list[dict]
    # AI node outputs.
    improvement_suggestions: str
    tailored_resume: str
    cover_letter: str
    # Prompt version actually used by each AI step.
    prompt_versions: dict[str, int]


class ChatClient(Protocol):
    """Provider-agnostic completion seam for AI nodes.

    Satisfied by ai_core bound clients and by test doubles.
    """

    def complete(self, *, system: str, user: str) -> str:
        ...


def _deterministic_analysis_node(state: AtsWorkflowState) -> dict:
    """Clean the job description and run the evidence-based matcher.

    The matcher is the ONLY source of the estimated score and keyword
    lists; AI nodes read them, never compute them.
    """
    cleaned = strip_boilerplate(state["job_description"])
    analysis = analyze_job_match(state["resume_text"], cleaned)
    return {
        "cleaned_job_description": cleaned,
        "job_description_warning": describe_warning(
            state["job_description"], cleaned
        ),
        "match_score": analysis.estimated_score,
        "score_label": analysis.score_label,
        "matching_keywords": analysis.supported_terms,
        "partial_keywords": analysis.partial_terms,
        "missing_keywords": analysis.missing_terms,
        "requirement_evidence": analysis.evidence_map,
        "score_breakdown": [
            {
                "category": entry.category,
                "weight": entry.weight,
                "total": entry.total,
                "supported": entry.supported,
                "partial": entry.partial,
                "missing": entry.missing,
                "score": entry.score,
            }
            for entry in analysis.breakdown
        ],
    }


def _merged_prompt_versions(
    state: AtsWorkflowState, step: str, version: int
) -> dict[str, int]:
    versions = dict(state.get("prompt_versions") or {})
    versions[step] = version
    return versions


def _make_llm_node(
    client: ChatClient, prompts: PromptRegistry, step: str
) -> Callable[[AtsWorkflowState], dict]:
    """Build an AI node for `step`, rendering its registry prompt.

    The template is resolved at invocation time (always the latest
    registered version), and the version used is recorded in the state.
    """
    prompt_id = PROMPT_IDS[step]
    output_field = _STEP_OUTPUT_FIELDS[step]

    def node(state: AtsWorkflowState) -> dict:
        template = prompts.get(prompt_id)
        style_notes = (state.get("style_notes") or "").strip()
        style_notes_section = (
            f"\n\nSTYLE PREFERENCES FROM THE APPLICANT:\n{style_notes}\n"
            if style_notes
            else ""
        )
        user = template.user_template.format(
            resume_text=state.get("resume_text", ""),
            job_description=(
                state.get("cleaned_job_description")
                or state.get("job_description", "")
            ),
            match_score=state.get("match_score"),
            matching_keywords=", ".join(state.get("matching_keywords", [])),
            partial_keywords=", ".join(state.get("partial_keywords", [])),
            missing_keywords=", ".join(state.get("missing_keywords", [])),
            requirement_evidence=_format_evidence(state),
            style_notes_section=style_notes_section,
            improvement_suggestions=state.get("improvement_suggestions") or "",
            tailored_resume=state.get("tailored_resume") or "",
        )
        response = client.complete(system=template.system, user=user)
        return {
            output_field: response,
            "prompt_versions": _merged_prompt_versions(
                state, step, template.version
            ),
        }

    return node


def _format_evidence(state: AtsWorkflowState) -> str:
    """Compact requirement-evidence text for AI prompt rendering."""
    evidence = state.get("requirement_evidence") or {}
    lines = []
    for term, entry in evidence.items():
        snippets = "; ".join(entry.get("evidence") or ["no evidence"])
        lines.append(
            f"- {term} ({entry.get('category', 'essential')}, "
            f"{entry.get('status', 'missing')}): {snippets}"
        )
    return "\n".join(lines)


def make_analysis_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[AtsWorkflowState], dict]:
    """AI node producing improvement suggestions (step 2)."""
    return _make_llm_node(client, prompts, "analysis")


def make_tailored_resume_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[AtsWorkflowState], dict]:
    """AI node producing the tailored resume (step 3)."""
    return _make_llm_node(client, prompts, "tailored_resume")


def make_cover_letter_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[AtsWorkflowState], dict]:
    """AI node producing the cover letter (step 4)."""
    return _make_llm_node(client, prompts, "cover_letter")


def build_ats_workflow(client: ChatClient, prompts: PromptRegistry):
    """Assemble and compile the four-step ATS workflow graph."""
    graph = StateGraph(AtsWorkflowState)

    graph.add_node("deterministic_analysis", _deterministic_analysis_node)
    graph.add_node("ai_analysis", make_analysis_node(client, prompts))
    graph.add_node("tailored_resume", make_tailored_resume_node(client, prompts))
    graph.add_node("cover_letter", make_cover_letter_node(client, prompts))

    graph.add_edge(START, "deterministic_analysis")
    graph.add_edge("deterministic_analysis", "ai_analysis")
    graph.add_edge("ai_analysis", "tailored_resume")
    graph.add_edge("tailored_resume", "cover_letter")
    graph.add_edge("cover_letter", END)

    return graph.compile()


def result_from_state(state: AtsWorkflowState) -> AtsAnalysisResult:
    """Map the final workflow state onto the analysis contract."""
    evidence = state.get("requirement_evidence") or {}
    requirement_analysis = [
        RequirementEvidence(
            term=term,
            status=entry.get("status", "missing"),
            category=entry.get("category", "essential"),
            evidence=entry.get("evidence") or [],
        )
        for term, entry in evidence.items()
    ] or None
    return AtsAnalysisResult(
        ats_score=state.get("match_score", 0),
        score_label=state.get("score_label") or "Estimated job-match score",
        matching_keywords=state.get("matching_keywords", []),
        partial_keywords=state.get("partial_keywords", []),
        missing_keywords=state.get("missing_keywords", []),
        requirement_analysis=requirement_analysis,
        score_breakdown=state.get("score_breakdown"),
        job_description_warning=state.get("job_description_warning"),
        improvement_suggestions=state.get("improvement_suggestions"),
        tailored_resume=state.get("tailored_resume"),
        cover_letter=state.get("cover_letter"),
    )
