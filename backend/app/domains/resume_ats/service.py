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
from app.services import document_templates, documents
from app.services.document_content import (
    parse_cover_letter,
    parse_resume,
)
from app.services.document_validation import (
    validate_generated_documents,
)

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


class DocumentValidationError(ValueError):
    """A generated document failed structural, page, or quality checks."""

    def __init__(self, issues: list[dict]):
        super().__init__("Document validation failed.")
        self.issues = issues


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
    sections through the configured provider. The workflow runs a
    deterministic writing-quality review and a targeted revision pass
    when issues are found; the final review is returned to the caller.
    Both the analysis record and the ai_core run record are persisted,
    scoped to `user_id`.

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
        resume.extracted_text,
        result.tailored_resume,
        result.cover_letter,
        job_description=job_description,
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


def _analysis_and_resume(
    session: Session, analysis_id: str, user_id: str
) -> tuple[AtsAnalysisRecord, Resume]:
    analysis = get_analysis(session, analysis_id, user_id)
    resume = session.get(Resume, analysis.resume_id)
    if resume is None:
        raise AnalysisNotFoundError(analysis_id)
    return analysis, resume


def _assert_download_ready(
    *,
    cv_text: str,
    cover_letter_text: str,
    source_text: str,
    document: str,
) -> None:
    report = validate_generated_documents(
        cv_text=cv_text,
        cover_letter_text=cover_letter_text,
        source_text=source_text,
        include_ai_review=False,
    )
    blocking = report["documents"][document]["blocking_issues"]
    if blocking:
        raise DocumentValidationError(blocking)


def validate_documents(
    ai_core: AICore,
    session: Session,
    analysis_id: str,
    user_id: str,
) -> dict:
    """Return validation and AI review for both generated documents."""
    analysis, resume = _analysis_and_resume(
        session, analysis_id, user_id
    )
    return validate_generated_documents(
        cv_text=analysis.tailored_resume or "",
        cover_letter_text=analysis.cover_letter or "",
        source_text=resume.extracted_text,
        ai_core=ai_core,
        include_ai_review=True,
    )


def tailored_resume_docx(
    session: Session, analysis_id: str, user_id: str
) -> tuple[str, bytes]:
    """Render the tailored resume of an analysis as DOCX bytes."""
    analysis, resume = _analysis_and_resume(
        session, analysis_id, user_id
    )
    if not analysis.tailored_resume:
        raise AnalysisNotReadyError(analysis_id)
    _assert_download_ready(
        cv_text=analysis.tailored_resume,
        cover_letter_text=analysis.cover_letter or "",
        source_text=resume.extracted_text,
        document="cv",
    )
    document = parse_resume(
        analysis.tailored_resume,
        source_text=resume.extracted_text,
    )
    return (
        "tailored-resume.docx",
        document_templates.render_resume_docx(document),
    )


def tailored_resume_pdf(
    session: Session,
    analysis_id: str,
    user_id: str,
    *,
    enforce_validation: bool = True,
) -> tuple[str, bytes]:
    """Render the tailored resume of an analysis as A4 PDF bytes."""
    analysis, resume = _analysis_and_resume(
        session, analysis_id, user_id
    )
    if not analysis.tailored_resume:
        raise AnalysisNotReadyError(analysis_id)
    if enforce_validation:
        _assert_download_ready(
            cv_text=analysis.tailored_resume,
            cover_letter_text=analysis.cover_letter or "",
            source_text=resume.extracted_text,
            document="cv",
        )
    document = parse_resume(
        analysis.tailored_resume,
        source_text=resume.extracted_text,
    )
    return (
        "tailored-resume.pdf",
        document_templates.render_resume_pdf(document),
    )


def cover_letter_docx(
    session: Session, analysis_id: str, user_id: str
) -> tuple[str, bytes]:
    """Render the cover letter of an analysis as DOCX bytes.

    The wording is the letter generated during the analysis — the download
    never regenerates or alters it.
    """
    analysis, resume = _analysis_and_resume(
        session, analysis_id, user_id
    )
    if not analysis.cover_letter:
        raise AnalysisNotReadyError(analysis_id)
    _assert_download_ready(
        cv_text=analysis.tailored_resume or "",
        cover_letter_text=analysis.cover_letter,
        source_text=resume.extracted_text,
        document="cover_letter",
    )
    document = parse_cover_letter(
        analysis.cover_letter,
        source_text=resume.extracted_text,
    )
    return (
        "tailored-cover-letter.docx",
        document_templates.render_cover_letter_docx(document),
    )


def cover_letter_pdf(
    session: Session,
    analysis_id: str,
    user_id: str,
    *,
    enforce_validation: bool = True,
) -> tuple[str, bytes]:
    """Render the cover letter of an analysis as A4 PDF bytes."""
    analysis, resume = _analysis_and_resume(
        session, analysis_id, user_id
    )
    if not analysis.cover_letter:
        raise AnalysisNotReadyError(analysis_id)
    if enforce_validation:
        _assert_download_ready(
            cv_text=analysis.tailored_resume or "",
            cover_letter_text=analysis.cover_letter,
            source_text=resume.extracted_text,
            document="cover_letter",
        )
    document = parse_cover_letter(
        analysis.cover_letter,
        source_text=resume.extracted_text,
    )
    return (
        "tailored-cover-letter.pdf",
        document_templates.render_cover_letter_pdf(document),
    )
