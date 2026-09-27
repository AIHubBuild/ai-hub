"""Pydantic schemas for the Resume ATS domain.

Result models for the deterministic engine, plus the domain-level
contracts that the future ATS workflow and API consume. The API
request/response schemas are added when the ATS endpoints land in a
later slice.
"""

from pydantic import BaseModel


class KeywordMatchResult(BaseModel):
    """Outcome of keyword matching between a resume and a job description."""

    score: int
    matched: list[str]
    missing: list[str]


class AtsAnalysis(BaseModel):
    """Deterministic analysis fields of the six-section ATS baseline."""

    original_ats_score: str
    optimized_ats_score: str
    matching_keywords: list[str]
    missing_keywords: list[str]


class AtsAnalysisRequest(BaseModel):
    """Input contract for the ATS analysis workflow."""

    resume_text: str
    job_description: str


class AtsAnalysisResult(BaseModel):
    """Output contract for the ATS analysis workflow.

    Exactly the six sections of the approved structured analysis
    baseline (docs/09_Migration_Analysis.md §8.1): score, matching
    keywords, missing keywords, improvement suggestions, tailored
    resume, cover letter. The last three are populated by the AI nodes
    in a later slice and remain None until then.
    """

    ats_score: int
    matching_keywords: list[str]
    missing_keywords: list[str]
    improvement_suggestions: str | None = None
    tailored_resume: str | None = None
    cover_letter: str | None = None


def ats_analysis_result(
    analysis: AtsAnalysis,
    *,
    improvement_suggestions: str | None = None,
    tailored_resume: str | None = None,
    cover_letter: str | None = None,
) -> AtsAnalysisResult:
    """Assemble the six-section result from the deterministic analysis.

    The deterministic engine fills the first three sections; the AI
    nodes (later slice) supply the remaining three.
    """
    return AtsAnalysisResult(
        ats_score=int(analysis.original_ats_score),
        matching_keywords=analysis.matching_keywords,
        missing_keywords=analysis.missing_keywords,
        improvement_suggestions=improvement_suggestions,
        tailored_resume=tailored_resume,
        cover_letter=cover_letter,
    )
