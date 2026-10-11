"""Resume ATS API routes.

Endpoints per `docs/07_API_Design.md` §13, mounted under `/api/v1`:
upload, resume detail, ATS analysis, and tailored-resume DOCX download.
All endpoints are protected: they require a valid Supabase JWT
(`docs/07_API_Design.md` §6) and are scoped to the authenticated user —
cross-user access yields 404, identical to a missing resource.
Synchronous endpoints: file IO and LLM calls run in the FastAPI
threadpool. All responses use the platform envelope
(`docs/07_API_Design.md` §10); errors map to:

- 400 invalid request body / job description
- 401 missing, invalid, or expired authentication token
- 404 unknown resume or analysis (including other users' resources)
- 409 analysis exists but has no tailored resume to download
- 413 file too large (5 MB default)
- 415 unsupported file type
- 422 unreadable/empty file
- 502 AI provider failure during a run
- 503 AI provider not configured (no OPENAI_API_KEY)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.ai_core import AICore, get_ai_core
from app.core.config import Settings, get_app_settings
from app.core.security import AuthUser, get_current_user
from app.db.session import get_db
from app.domains.resume_ats import service
from app.domains.resume_ats.schemas import (
    AnalysisData,
    AnalysisResponse,
    AtsAnalysisApiRequest,
    ResumeDetailData,
    ResumeDetailResponse,
    UploadResumeData,
    UploadResumeResponse,
)
from app.domains.resume_ats.service import (
    AnalysisNotReadyError,
    AnalysisNotFoundError,
    ProviderNotAvailableError,
    ProviderUnavailableError,
    ResumeNotFoundError,
)
from app.services.errors import DocumentError, EmptyDocumentError, InvalidFileTypeError

router = APIRouter(prefix="/resumes", tags=["resumes"])
analyses_router = APIRouter(prefix="/analyses", tags=["resumes"])

_CHUNK_SIZE = 1024 * 1024


def _error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "message": message},
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload in chunks, aborting as soon as the limit is hit."""
    data = bytearray()
    while True:
        chunk = file.file.read(_CHUNK_SIZE)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise _error(
                413,
                f"File exceeds the maximum allowed size of "
                f"{max_bytes // (1024 * 1024)} MB.",
            )
    return bytes(data)


@router.post("", status_code=201, response_model=UploadResumeResponse)
def upload_resume(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    user: AuthUser = Depends(get_current_user),
) -> UploadResumeResponse:
    data = _read_upload(
        file, settings.max_upload_size_mb * 1024 * 1024
    )

    try:
        resume = service.upload_resume(
            session,
            user_id=user.id,
            file_name=file.filename or "resume",
            data=data,
            settings=settings,
        )
    except InvalidFileTypeError as exc:
        raise _error(415, str(exc)) from exc
    except DocumentError as exc:
        if isinstance(exc, EmptyDocumentError):
            raise _error(422, str(exc)) from exc
        if "maximum allowed size" in str(exc):
            raise _error(413, str(exc)) from exc
        raise _error(422, str(exc)) from exc

    return UploadResumeResponse(
        message="Resume uploaded successfully.",
        data=UploadResumeData(
            resume_id=resume.id,
            file_name=resume.file_name,
            extracted_characters=len(resume.extracted_text),
        ),
    )


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
def get_resume(
    resume_id: str,
    session: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> ResumeDetailResponse:
    if not _is_uuid(resume_id):
        raise _error(404, "Resume not found.")
    try:
        resume = service.get_resume(session, resume_id, user.id)
    except ResumeNotFoundError as exc:
        raise _error(404, "Resume not found.") from exc

    latest = service.latest_analysis(session, resume_id)
    return ResumeDetailResponse(
        message="Resume retrieved.",
        data=ResumeDetailData(
            resume_id=resume.id,
            file_name=resume.file_name,
            created_at=resume.created_at,
            latest_analysis=(
                AnalysisSummary(
                    analysis_id=latest.id,
                    ats_score=latest.ats_score,
                    created_at=latest.created_at,
                )
                if latest is not None
                else None
            ),
        ),
    )


@router.post(
    "/{resume_id}/ats-analysis", status_code=201, response_model=AnalysisResponse
)
def analyze_resume(
    resume_id: str,
    body: AtsAnalysisApiRequest,
    session: Session = Depends(get_db),
    ai_core: AICore = Depends(get_ai_core),
    user: AuthUser = Depends(get_current_user),
) -> AnalysisResponse:
    if not _is_uuid(resume_id):
        raise _error(404, "Resume not found.")
    try:
        analysis, result = service.run_ats_analysis(
            ai_core,
            session,
            resume_id=resume_id,
            job_description=body.job_description.strip(),
            user_id=user.id,
            style_notes=body.style_notes,
        )
    except ResumeNotFoundError as exc:
        raise _error(404, "Resume not found.") from exc
    except ProviderNotAvailableError as exc:
        raise _error(503, str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise _error(502, str(exc)) from exc

    return AnalysisResponse(
        message="ATS analysis completed.",
        data=AnalysisData(
            analysis_id=analysis.id,
            resume_id=analysis.resume_id,
            run_id=analysis.run_id,
            ats_score=analysis.ats_score,
            score_label=result.score_label,
            matching_keywords=analysis.matching_keywords,
            partial_keywords=result.partial_keywords,
            missing_keywords=analysis.missing_keywords,
            requirement_analysis=result.requirement_analysis,
            score_breakdown=result.score_breakdown,
            job_description_warning=result.job_description_warning,
            writing_review=result.writing_review,
            improvement_suggestions=analysis.improvement_suggestions,
            tailored_resume=analysis.tailored_resume,
            cover_letter=analysis.cover_letter,
        ),
    )


@analyses_router.get(
    "/{analysis_id}/tailored-cover-letter.docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document": {}
            },
            "description": "Cover letter as a DOCX attachment.",
        }
    },
)
def download_cover_letter(
    analysis_id: str,
    session: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> Response:
    if not _is_uuid(analysis_id):
        raise _error(404, "Analysis not found.")
    try:
        file_name, content = service.cover_letter_docx(
            session, analysis_id, user.id
        )
    except AnalysisNotFoundError as exc:
        raise _error(404, "Analysis not found.") from exc
    except AnalysisNotReadyError as exc:
        raise _error(409, "This analysis has no cover letter to download.") from exc

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@analyses_router.get(
    "/{analysis_id}/tailored-resume.docx",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document": {}
            },
            "description": "Tailored resume as a DOCX attachment.",
        }
    },
)
def download_tailored_resume(
    analysis_id: str,
    session: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> Response:
    if not _is_uuid(analysis_id):
        raise _error(404, "Analysis not found.")
    try:
        file_name, content = service.tailored_resume_docx(
            session, analysis_id, user.id
        )
    except AnalysisNotFoundError as exc:
        raise _error(404, "Analysis not found.") from exc
    except AnalysisNotReadyError as exc:
        raise _error(409, "This analysis has no tailored resume to download.") from exc

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
