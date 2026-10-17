"""Resume ATS service layer.

Business logic between the API router and the shared ai_core / document
services: resume upload (validation + text extraction), ATS analysis
execution (deterministic engine + AI workflow, persisted as both an
analysis record and an ai_core run record), and DOCX rendering of the
tailored resume.

Every function is user-scoped: callers pass the authenticated user id
(from `app.core.security.get_current_user`), all reads filter on it,
and ownership violations surface as the same not-found error as missing
records (no existence leak).

Design rules honored (`docs/09_Migration_Analysis.md` §3.3):
- The deterministic engine owns score and keyword lists; AI nodes never
  compute them.
- Every AI invocation goes through ai_core's workflow runner, which
  persists the run record — results returned here are the workflow's
  actual output, never fabricated or mocked.
"""

from sqlalchemy.orm import Session

from app.ai_core import AICore
from app.ai_core.providers.openai import ProviderError
from app.ai_core.workflows import WorkflowNotFoundError
from app.core.config import Settings, get_settings
from app.domains.resume_ats.schemas import (
    AtsAnalysisResult,
    WritingIssue as WritingIssueSchema,
    WritingReview as WritingReviewSchema,
)
from app.domains.resume_ats.workflow import ATS_WORKFLOW_ID, result_from_state
from app.domains.resume_ats.writing_review import review_writing
from app.models.resume import AtsAnalysisRecord, Resume
from app.services import documents

DOMAIN = "resume_ats"


class ResumeNotFoundError(KeyError):
    """No resume exists under the requested id for the requesting user."""


class AnalysisNotFoundError(KeyError):
    """No analysis exists under the requested id for the requesting user."""


class ProviderNotAvailableError(RuntimeError):
    """The AI provider (or the workflow) is not configured."""


class ProviderUnavailableError(RuntimeError):
    """The AI provider failed during a run."""


class AnalysisNotReadyError(ValueError):
    """An analysis exists but has no tailored resume to download."""


def upload_resume(
    session: Session,
    *,
    user_id: str,
    file_name: str,
    data: bytes,
    settings: Settings | None = None,
) -> Resume:
    """Validate `data`, extract its text, and persist a resume row.

    Raises DocumentError subclasses for invalid input.
    """
    settings = settings or get_settings()
    text = documents.extract_text(
        file_name, data, max_size_bytes=settings.max_upload_size_mb * 1024 * 1024
    )
    resume = Resume(
        user_id=user_id,
        file_name=file_name,
        extracted_text=text,
        file_size_bytes=len(data),
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def get_resume(session: Session, resume_id: str, user_id: str) -> Resume:
    """Return the resume owned by `user_id`, or raise ResumeNotFoundError.

    A resume that exists but belongs to another user is indistinguishable
    from a missing one at this layer — no resource-existence leak.
    """
    resume = (
        session.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == user_id)
        .first()
    )
    if resume is None:
        raise ResumeNotFoundError(resume_id)
    return resume


def run_ats_analysis(
    ai_core: AICore,
    session: Session,
    *,
    resume_id: str,
    job_description: str,
    user_id: str,
    style_notes: str | None = None,
) -> tuple[AtsAnalysisRecord, AtsAnalysisResult]:
    """Run the ATS workflow for a user-owned resume against a job description.

    The deterministic matcher computes the estimated score, keyword
    lists, and per-requirement evidence; the AI nodes fill the remaining
    sections through the configured provider. A deterministic
    writing-quality review then flags any stylistic or consistency
    issues. Both the analysis record and the ai_core run record are
    persisted, scoped to `user_id`.

    Returns the persisted record and the full result contract (the
    explainability and review fields are computed per run and are not
    persisted to the analysis table).
    """
    resume = get_resume(session, resume_id, user_id)

    try:
        run = ai_core.workflows.run(
            ATS_WORKFLOW_ID,
            {
                "resume_text": resume.extracted_text,
                "job_description": job_description,
                "style_notes": style_notes,
            },
            user_id=user_id,
            domain=DOMAIN,
        )
    except WorkflowNotFoundError as exc:
        raise ProviderNotAvailableError(
            "The AI provider is not configured. Set AI_API_KEY (or DEEPSEEK_API_KEY) "
            "in the environment or .env file to enable ATS analysis."
        ) from exc
    except ProviderError as exc:
        # ai_core re-raises provider failures after persisting an error
        # run record; surface them as provider-unavailable, not a 500.
        raise ProviderUnavailableError(
            f"The AI provider failed while running the analysis: {exc}"
        ) from exc

    result = result_from_state(run.output_state)
    review = review_writing(
        resume.extracted_text, result.tailored_resume, result.cover_letter
    )
    result.writing_review = WritingReviewSchema(
        passed=review.passed,
        issues=[
            WritingIssueSchema(code=issue.code, message=issue.message)
            for issue in review.issues
        ],
    )
    record = AtsAnalysisRecord(
        resume_id=resume.id,
        run_id=run.run_id,
        job_description=job_description,
        ats_score=result.ats_score,
        matching_keywords=result.matching_keywords,
        missing_keywords=result.missing_keywords,
        improvement_suggestions=result.improvement_suggestions,
        tailored_resume=result.tailored_resume,
        cover_letter=result.cover_letter,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record, result


def get_analysis(
    session: Session, analysis_id: str, user_id: str
) -> AtsAnalysisRecord:
    """Return the analysis owned by `user_id`, or raise AnalysisNotFoundError."""
    analysis = (
        session.query(AtsAnalysisRecord)
        .join(Resume, Resume.id == AtsAnalysisRecord.resume_id)
        .filter(
            AtsAnalysisRecord.id == analysis_id,
            Resume.user_id == user_id,
        )
        .first()
    )
    if analysis is None:
        raise AnalysisNotFoundError(analysis_id)
    return analysis


def latest_analysis(session: Session, resume_id: str) -> AtsAnalysisRecord | None:
    return (
        session.query(AtsAnalysisRecord)
        .filter(AtsAnalysisRecord.resume_id == resume_id)
        .order_by(AtsAnalysisRecord.created_at.desc())
        .first()
    )


def tailored_resume_docx(
    session: Session, analysis_id: str, user_id: str
) -> tuple[str, bytes]:
    """Render the tailored resume of an analysis as DOCX bytes.

    Returns (file_name, bytes). Raises AnalysisNotReadyError when the
    analysis has no tailored resume (e.g. the AI run failed).
    """
    analysis = get_analysis(session, analysis_id, user_id)
    if not analysis.tailored_resume:
        raise AnalysisNotReadyError(analysis_id)
    return (
        "tailored-resume.docx",
        documents.build_tailored_resume_docx(analysis.tailored_resume),
    )


def cover_letter_docx(
    session: Session, analysis_id: str, user_id: str
) -> tuple[str, bytes]:
    """Render the cover letter of an analysis as DOCX bytes.

    Returns (file_name, bytes). The wording is the letter generated
    during the analysis — the download never regenerates or alters it.
    Raises AnalysisNotReadyError when the analysis has no cover letter.
    """
    analysis = get_analysis(session, analysis_id, user_id)
    if not analysis.cover_letter:
        raise AnalysisNotReadyError(analysis_id)
    return (
        "tailored-cover-letter.docx",
        documents.build_cover_letter_docx(analysis.cover_letter),
    )
