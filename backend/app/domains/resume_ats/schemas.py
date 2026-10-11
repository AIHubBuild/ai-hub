"""Pydantic schemas for the Resume ATS domain.

Result models for the deterministic engine, the domain-level workflow
contracts, and the HTTP request/response models for the domain's API
(`docs/07_API_Design.md` §13). Responses follow the platform envelope
(`docs/07_API_Design.md` §3.4).
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class RequirementEvidence(BaseModel):
    """Explainable evidence for one job requirement term."""

    term: str
    status: str  # supported | partial | missing
    category: str  # essential | preferred
    evidence: list[str]


class WritingIssue(BaseModel):
    """One flagged writing-quality issue (deterministic review)."""

    code: str
    message: str


class WritingReview(BaseModel):
    """Outcome of the writing-quality review stage."""

    passed: bool
    issues: list[WritingIssue]


class AtsAnalysisResult(BaseModel):
    """Output contract for the ATS analysis workflow.

    The first six fields are the structured analysis baseline
    (docs/09_Migration_Analysis.md §8.1): score, matching keywords,
    missing keywords, improvement suggestions, tailored resume, cover
    letter. The additional fields carry the transparent scoring
    methodology (evidence per requirement, partial/transferable
    matches, per-category breakdown, and a job-description warning).
    """

    ats_score: int
    score_label: str = "Estimated job-match score"
    matching_keywords: list[str]
    partial_keywords: list[str] = []
    missing_keywords: list[str]
    requirement_analysis: list[RequirementEvidence] | None = None
    score_breakdown: list[dict] | None = None
    job_description_warning: str | None = None
    writing_review: WritingReview | None = None
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


# ---------------------------------------------------------------
# HTTP API schemas (docs/07_API_Design.md §13)
# ---------------------------------------------------------------


class AtsAnalysisApiRequest(BaseModel):
    """Request body for POST /resumes/{resume_id}/ats-analysis."""

    job_description: str = Field(
        min_length=1, max_length=20_000, description="Target job description."
    )
    style_notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional applicant-supplied style preferences.",
    )

    @field_validator("job_description")
    @classmethod
    def job_description_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("job_description must not be blank.")
        return stripped


class UploadResumeData(BaseModel):
    resume_id: str
    file_name: str
    extracted_characters: int


class UploadResumeResponse(BaseModel):
    success: bool = True
    message: str
    data: UploadResumeData


class AnalysisSummary(BaseModel):
    analysis_id: str
    ats_score: int
    created_at: datetime


class ResumeDetailData(BaseModel):
    resume_id: str
    file_name: str
    created_at: datetime
    latest_analysis: AnalysisSummary | None = None


class ResumeDetailResponse(BaseModel):
    success: bool = True
    message: str
    data: ResumeDetailData


class AnalysisData(BaseModel):
    analysis_id: str
    resume_id: str
    run_id: str
    ats_score: int
    score_label: str = "Estimated job-match score"
    matching_keywords: list[str]
    partial_keywords: list[str] = []
    missing_keywords: list[str]
    requirement_analysis: list[RequirementEvidence] | None = None
    score_breakdown: list[dict] | None = None
    job_description_warning: str | None = None
    writing_review: WritingReview | None = None
    improvement_suggestions: str | None = None
    tailored_resume: str | None = None
    cover_letter: str | None = None


class AnalysisResponse(BaseModel):
    success: bool = True
    message: str
    data: AnalysisData
