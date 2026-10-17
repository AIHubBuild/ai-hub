"""LangGraph workflow for the Resume ATS domain.

Implements the approved multi-step ATS pipeline
(`docs/09_Migration_Analysis.md` §8.1):

    deterministic analysis → AI recommendations → tailored resume → cover letter
    → deterministic review → targeted revision when needed

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
from app.ai_core.writing_style import normalize_writing
from app.domains.resume_ats.job_description import (
    describe_warning,
    strip_boilerplate,
)
from app.domains.resume_ats.matching import analyze_job_match
from app.domains.resume_ats.schemas import AtsAnalysisResult, RequirementEvidence
from app.domains.resume_ats.writing_review import applicant_name, review_writing

ATS_WORKFLOW_ID = "resume_ats/ats_pipeline"
MAX_REVISION_PASSES = 2

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
    requirement_coverage: int
    evidence_confidence: int
    matching_keywords: list[str]
    partial_keywords: list[str]
    unverified_keywords: list[str]
    missing_keywords: list[str]
    requirement_evidence: list[dict]
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
        "requirement_coverage": analysis.requirement_coverage,
        "evidence_confidence": analysis.evidence_confidence,
        "matching_keywords": analysis.supported_terms,
        "partial_keywords": analysis.partial_terms,
        "unverified_keywords": analysis.unverified_terms,
        "missing_keywords": analysis.missing_terms,
        "requirement_evidence": analysis.requirement_evidence,
        "score_breakdown": [
            {
                "category": entry.category,
                "weight": entry.weight,
                "total": entry.total,
                "supported": entry.supported,
                "partial": entry.partial,
                "unverified": entry.unverified,
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


def _render_prompt(
    template: Any,
    state: AtsWorkflowState,
    *,
    revision_section: str = "",
) -> str:
    style_notes = (state.get("style_notes") or "").strip()
    style_notes_section = (
        f"\n\nSTYLE PREFERENCES FROM THE APPLICANT:\n{style_notes}\n"
        if style_notes
        else ""
    )
    revision_text = revision_section.strip() or (
        "No revision pass is needed. Generate the first draft."
    )
    return template.user_template.format(
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
        revision_section=revision_text,
    )


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
        user = _render_prompt(template, state)
        response = normalize_writing(client.complete(system=template.system, user=user))
        return {
            output_field: response,
            "prompt_versions": _merged_prompt_versions(
                state, step, template.version
            ),
        }

    return node


def _revision_instructions(
    document_name: str,
    current_draft: str,
    issues: list[Any],
    source_resume: str,
) -> str:
    lines = [
        f"REVISION PASS FOR THE {document_name.upper()}:",
        "The current draft has these specific problems:",
    ]
    for issue in issues:
        lines.append(f"- {issue.code}: {issue.message}")
    lines.extend(
        [
            "",
            "Current draft:",
            current_draft.strip(),
            "",
            "Verified source resume (use this to check every claim):",
            source_resume.strip(),
            "",
            "Rewrite the draft so it fixes every problem above. Keep the same "
            "verified facts, employers, dates, qualifications, and achievements. "
            "Do not add anything the source material does not support. Remove "
            "generic wording instead of replacing it with another cliche. "
            "If an issue is unsupported_claim, unsupported_section, "
            "unsupported_outcome, unsupported_metric, or "
            "unsupported_time_reference, remove the unsupported statement "
            "entirely instead of rephrasing it into another unsupported claim. "
            "Return only the revised document.",
        ]
    )
    return "\n".join(lines)


def _ensure_applicant_name(
    document_name: str, text: str, resume_source: str
) -> str:
    name = applicant_name(resume_source)
    if not name:
        return text
    first_name = name.split()[0]
    if first_name.lower() in text.lower():
        return text
    if document_name == "cover letter":
        return text.rstrip() + "\n\n" + name
    return name + "\n\n" + text.lstrip()


def make_review_and_revise_node(
    client: ChatClient, prompts: PromptRegistry
) -> Callable[[AtsWorkflowState], dict]:
    """Run the deterministic review and revise any document with issues."""

    def node(state: AtsWorkflowState) -> dict:
        updates: dict[str, str] = {}
        resume_source = state.get("resume_text", "")
        tailored_resume = state.get("tailored_resume", "")
        cover_letter = state.get("cover_letter", "")

        if tailored_resume:
            for _ in range(MAX_REVISION_PASSES):
                resume_review = review_writing(
                    resume_source, tailored_resume, None
                )
                if resume_review.passed:
                    break
                template = prompts.get(PROMPT_IDS["tailored_resume"])
                revision = _revision_instructions(
                    "tailored resume",
                    tailored_resume,
                    resume_review.issues,
                    resume_source,
                )
                user = _render_prompt(
                    template, state, revision_section=revision
                )
                tailored_resume = normalize_writing(
                    client.complete(system=template.system, user=user)
                )
                tailored_resume = _ensure_applicant_name(
                    "tailored resume", tailored_resume, resume_source
                )
            updates["tailored_resume"] = tailored_resume

        if cover_letter:
            for _ in range(MAX_REVISION_PASSES):
                cover_review = review_writing(
                    resume_source, None, cover_letter
                )
                if cover_review.passed:
                    break
                template = prompts.get(PROMPT_IDS["cover_letter"])
                revision = _revision_instructions(
                    "cover letter",
                    cover_letter,
                    cover_review.issues,
                    resume_source,
                )
                cover_state = dict(state)
                cover_state["tailored_resume"] = tailored_resume
                user = _render_prompt(
                    template, cover_state, revision_section=revision
                )
                cover_letter = normalize_writing(
                    client.complete(system=template.system, user=user)
                )
                cover_letter = _ensure_applicant_name(
                    "cover letter", cover_letter, resume_source
                )
            updates["cover_letter"] = cover_letter

        return updates

    return node


def _format_evidence(state: AtsWorkflowState) -> str:
    """Compact requirement-evidence text for AI prompt rendering."""
    evidence = state.get("requirement_evidence") or []
    lines = []
    if isinstance(evidence, dict):
        entries = [
            (term, entry) for term, entry in evidence.items()
        ]
    else:
        entries = [
            (entry.get("term", "requirement"), entry) for entry in evidence
        ]
    for term, entry in entries:
        snippets = "; ".join(entry.get("evidence") or ["no evidence"])
        lines.append(
            f"- {term} ({entry.get('category', 'skills')}, "
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
    graph.add_node(
        "review_and_revise", make_review_and_revise_node(client, prompts)
    )

    graph.add_edge(START, "deterministic_analysis")
    graph.add_edge("deterministic_analysis", "ai_analysis")
    graph.add_edge("ai_analysis", "tailored_resume")
    graph.add_edge("tailored_resume", "cover_letter")
    graph.add_edge("cover_letter", "review_and_revise")
    graph.add_edge("review_and_revise", END)

    return graph.compile()


def result_from_state(state: AtsWorkflowState) -> AtsAnalysisResult:
    """Map the final workflow state onto the analysis contract."""
    evidence = state.get("requirement_evidence") or []
    if isinstance(evidence, dict):
        entries = [
            (term, entry) for term, entry in evidence.items()
        ]
    else:
        entries = [
            (entry.get("term", "requirement"), entry) for entry in evidence
        ]
    requirement_analysis = [
        RequirementEvidence(
            term=term,
            status=entry.get("status", "missing"),
            category=entry.get("category", "skills"),
            evidence=entry.get("evidence") or [],
            section=entry.get("section"),
            detail=entry.get("detail", ""),
            mandatory=entry.get("mandatory", True),
        )
        for term, entry in entries
    ] or None
    return AtsAnalysisResult(
        ats_score=state.get("match_score", 0),
        score_label=state.get("score_label") or "Estimated resume-to-job match",
        requirement_coverage=state.get("requirement_coverage"),
        evidence_confidence=state.get("evidence_confidence"),
        matching_keywords=state.get("matching_keywords", []),
        partial_keywords=state.get("partial_keywords", []),
        unverified_keywords=state.get("unverified_keywords", []),
        missing_keywords=state.get("missing_keywords", []),
        requirement_analysis=requirement_analysis,
        score_breakdown=state.get("score_breakdown"),
        job_description_warning=state.get("job_description_warning"),
        improvement_suggestions=state.get("improvement_suggestions"),
        tailored_resume=state.get("tailored_resume"),
        cover_letter=state.get("cover_letter"),
    )
