"""Document validation, PDF pagination checks, and AI copy review."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import logging
import re
import threading
from typing import Any

from pypdf import PdfReader

from app.services.document_content import (
    DocumentIssue,
    validate_cover_letter_document,
    validate_resume_document,
    parse_cover_letter,
    parse_resume,
)
from app.services.document_templates import (
    render_cover_letter_pdf,
    render_resume_pdf,
)

logger = logging.getLogger(__name__)

QUALITY_PROMPT_ID = "resume_ats/document_quality_review"
REVIEW_CACHE_SECONDS = 600
_REVIEW_CACHE: dict[tuple[str, str, int], tuple[float, list[dict]]] = {}
_REVIEW_LOCK = threading.Lock()


@dataclass
class AIReviewResult:
    issues: list[dict]
    available: bool
    error_type: str | None = None


def _utcnow() -> float:
    return datetime.now(timezone.utc).timestamp()


def clear_review_cache() -> None:
    with _REVIEW_LOCK:
        _REVIEW_CACHE.clear()


def _parse_ai_review(response: str) -> AIReviewResult:
    start = response.find("{")
    end = response.rfind("}")
    if start < 0 or end <= start:
        return AIReviewResult([], False, "malformed_response")
    try:
        payload = json.loads(response[start : end + 1])
    except (TypeError, ValueError):
        return AIReviewResult([], False, "malformed_response")
    if not isinstance(payload, dict):
        return AIReviewResult([], False, "malformed_response")

    issues: list[dict] = []
    for document, key in (
        ("cv", "cv_issues"),
        ("cover_letter", "cover_letter_issues"),
    ):
        entries = payload.get(key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("code", "grammar")).lower()
            if code not in {"spelling", "grammar"}:
                code = "grammar"
            severity = str(entry.get("severity", "warning")).lower()
            if severity not in {"error", "warning"}:
                severity = "warning"
            message = str(entry.get("message", "")).strip()[:300]
            if not message:
                continue
            excerpt = str(entry.get("excerpt", "")).strip()[:160]
            issues.append(
                {
                    "document": document,
                    "severity": severity,
                    "code": code,
                    "message": message,
                    "excerpt": excerpt,
                    "source": "ai_review",
                }
            )
    return AIReviewResult(issues, True)


def review_document_text(
    ai_core: Any,
    cv_text: str,
    cover_letter_text: str,
) -> AIReviewResult:
    """Run spelling/grammar review through the existing AI provider."""
    prompt = ai_core.prompts.get(QUALITY_PROMPT_ID)
    digest = hashlib.sha256(
        f"{cv_text}\0{cover_letter_text}\0{prompt.version}".encode("utf-8")
    ).hexdigest()
    key = (digest, QUALITY_PROMPT_ID, prompt.version)
    now = _utcnow()
    with _REVIEW_LOCK:
        cached = _REVIEW_CACHE.get(key)
        if cached is not None and now - cached[0] <= REVIEW_CACHE_SECONDS:
            return AIReviewResult(list(cached[1]), True)

    try:
        client = ai_core.llm_factory.get_client("resume_ats")
        response = client.complete(
            system=prompt.system,
            user=prompt.user_template.format(
                cv_text=cv_text,
                cover_letter_text=cover_letter_text,
            ),
        )
        result = _parse_ai_review(response)
    except Exception as exc:
        logger.warning(
            "document_quality_review_failed error_type=%s",
            type(exc).__name__,
        )
        return AIReviewResult([], False, type(exc).__name__)

    if result.available:
        with _REVIEW_LOCK:
            _REVIEW_CACHE[key] = (now, list(result.issues))
    return result


def _issue(
    document: str,
    code: str,
    message: str,
    *,
    severity: str = "error",
) -> dict:
    return {
        "document": document,
        "severity": severity,
        "code": code,
        "message": message,
        "source": "structural",
    }


def _content_issues(
    document_name: str, issues: list[DocumentIssue]
) -> list[dict]:
    return [
        _issue(document_name, issue.code, issue.message)
        for issue in issues
    ]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _pdf_text(content: bytes) -> tuple[int, str]:
    reader = PdfReader(BytesIO(content))
    return (
        len(reader.pages),
        _normalize(
            "\n".join(page.extract_text() or "" for page in reader.pages)
        ),
    )


def _last_content_token(texts: list[str]) -> str | None:
    if not texts:
        return None
    return _normalize(texts[-1])[:80]


def _pdf_issues(
    document: str,
    content: bytes,
    *,
    max_pages: int,
    required_tokens: list[str],
) -> tuple[list[dict], int]:
    pages, text = _pdf_text(content)
    issues: list[dict] = []
    if pages > max_pages:
        issues.append(
            _issue(
                document,
                "too_many_pages",
                f"Rendered document has {pages} pages; maximum is "
                f"{max_pages}.",
            )
        )
    normalized_text = _normalize(text)
    for token in required_tokens:
        token = _normalize(token)
        if token and token not in normalized_text:
            issues.append(
                _issue(
                    document,
                    "content_overflow",
                    "Expected content was not found in the rendered PDF; "
                    "the document may have overflowed or been clipped.",
                )
            )
            break
    return issues, pages


def validate_generated_documents(
    *,
    cv_text: str,
    cover_letter_text: str,
    source_text: str,
    ai_core: Any | None = None,
    include_ai_review: bool = True,
) -> dict:
    """Validate structure, PDF pagination, and AI copy review."""
    resume = parse_resume(cv_text, source_text=source_text)
    cover_letter = parse_cover_letter(
        cover_letter_text, source_text=source_text
    )

    cv_issues = validate_resume_document(resume)
    cv_blocking = _content_issues(
        "cv",
        [issue for issue in cv_issues if issue.code != "missing_education"],
    )
    cv_warnings: list[dict] = [
        _issue(
            "cv",
            issue.code,
            issue.message,
            severity="warning",
        )
        for issue in cv_issues
        if issue.code == "missing_education"
    ]
    cover_blocking = _content_issues(
        "cover_letter", validate_cover_letter_document(cover_letter)
    )

    cv_pdf = render_resume_pdf(resume)
    cover_pdf = render_cover_letter_pdf(cover_letter)

    cv_pdf_issues, cv_pages = _pdf_issues(
        "cv",
        cv_pdf,
        max_pages=2,
        required_tokens=[
            resume.contact.name.upper(),
            _last_content_token(
                resume.languages
                or (
                    [resume.education[-1].credential]
                    if resume.education
                    else []
                )
                or (resume.projects[-1:] if resume.projects else [])
                or (resume.profile[-1:] if resume.profile else [])
            )
            or "",
        ],
    )
    cover_pdf_issues, cover_pages = _pdf_issues(
        "cover_letter",
        cover_pdf,
        max_pages=2,
        required_tokens=[
            cover_letter.closing,
            cover_letter.signature,
        ],
    )
    cv_blocking.extend(cv_pdf_issues)
    cover_blocking.extend(cover_pdf_issues)

    cover_warnings: list[dict] = []
    ai_available = False
    ai_error = None
    if include_ai_review and ai_core is not None:
        review = review_document_text(ai_core, cv_text, cover_letter_text)
        ai_available = review.available
        ai_error = review.error_type
        if review.available:
            for issue in review.issues:
                warning = dict(issue)
                warning["severity"] = "warning"
                if issue.get("document") == "cover_letter":
                    cover_warnings.append(warning)
                else:
                    cv_warnings.append(warning)
        else:
            warning = _issue(
                "both",
                "ai_review_unavailable",
                "AI spelling and grammar review was unavailable; "
                "structural and PDF checks still passed.",
                severity="warning",
            )
            warning["source"] = "ai_review"
            cv_warnings.append(warning)
            cover_warnings.append(dict(warning))

    return {
        "ready": not cv_blocking and not cover_blocking,
        "documents": {
            "cv": {
                "blocking_issues": cv_blocking,
                "warnings": cv_warnings,
                "pages": cv_pages,
            },
            "cover_letter": {
                "blocking_issues": cover_blocking,
                "warnings": cover_warnings,
                "pages": cover_pages,
            },
        },
        "ai_review_available": ai_available,
        "ai_review_error": ai_error,
    }
