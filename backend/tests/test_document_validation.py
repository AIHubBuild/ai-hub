"""Tests for structural, PDF pagination, and AI copy validation."""

import json

from app.services.document_validation import (
    AIReviewResult,
    clear_review_cache,
    review_document_text,
    validate_generated_documents,
)

SOURCE = "Jane Doe\nBerlin, Germany\njane@example.com\n+49 123 456789\n"

CV = """Jane Doe
IT Support Engineer
Berlin, Germany | jane@example.com | +49 123 456789

PROFILE
IT support engineer with verified experience supporting Windows and
Microsoft 365 users.

CORE SKILLS
Support: Windows, Microsoft 365 and VPN.

EXPERIENCE
IT Support Engineer | Example GmbH, Berlin Jan 2020 - Present
- Supported users with Windows and Microsoft 365 issues.

EDUCATION
BSc IT | Example University, Berlin Sep 2015 - Jun 2019
"""

COVER = """Dear Hiring Team,

I am applying for this role because my verified experience matches the
requirements.

I support Windows users and document resolutions clearly.

Sincerely,
Jane Doe
"""


class _Prompt:
    version = 1
    system = "review"
    user_template = "{cv_text}\n{cover_letter_text}"


class _Prompts:
    def get(self, prompt_id):
        assert prompt_id == "resume_ats/document_quality_review"
        return _Prompt()


class _Client:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def complete(self, *, system, user):
        if self.error is not None:
            raise self.error
        return self.response


class _Factory:
    def __init__(self, client):
        self.client = client

    def get_client(self, domain):
        assert domain == "resume_ats"
        return self.client


class _AICore:
    def __init__(self, client):
        self.prompts = _Prompts()
        self.llm_factory = _Factory(client)


def test_valid_documents_are_ready_without_ai_review():
    report = validate_generated_documents(
        cv_text=CV,
        cover_letter_text=COVER,
        source_text=SOURCE,
        include_ai_review=False,
    )
    assert report["ready"] is True
    assert report["documents"]["cv"]["pages"] <= 2
    assert report["documents"]["cover_letter"]["pages"] <= 2
    assert report["documents"]["cv"]["blocking_issues"] == []


def test_structural_issues_block_download():
    report = validate_generated_documents(
        cv_text="Jane Doe\nUnstructured text.",
        cover_letter_text="Short note.",
        source_text=SOURCE,
        include_ai_review=False,
    )
    assert report["ready"] is False
    codes = {
        issue["code"]
        for issue in report["documents"]["cv"]["blocking_issues"]
    }
    assert "missing_profile" in codes
    assert "missing_skills" in codes
    assert "missing_experience" in codes


def test_pdf_overflow_blocks_download():
    bullets = "\n".join(
        f"- Supported users with Windows, Microsoft 365 and VPN issue {i}."
        for i in range(70)
    )
    long_cv = f"""Jane Doe
IT Support Engineer
Berlin, Germany | jane@example.com | +49 123 456789

PROFILE
IT support engineer with verified experience.

CORE SKILLS
Support: Windows, Microsoft 365 and VPN.

EXPERIENCE
IT Support Engineer | Example GmbH, Berlin Jan 2020 - Present
{bullets}

EDUCATION
BSc IT | Example University, Berlin Sep 2015 - Jun 2019
"""
    report = validate_generated_documents(
        cv_text=long_cv,
        cover_letter_text=COVER,
        source_text=SOURCE,
        include_ai_review=False,
    )
    assert report["ready"] is False
    codes = {
        issue["code"]
        for issue in report["documents"]["cv"]["blocking_issues"]
    }
    assert "too_many_pages" in codes


def test_ai_spelling_grammar_review_is_reported():
    clear_review_cache()
    response = json.dumps(
        {
            "cv_issues": [
                {
                    "code": "spelling",
                    "severity": "error",
                    "message": "Possible spelling mistake.",
                    "excerpt": "Microsft",
                }
            ],
            "cover_letter_issues": [],
        }
    )
    ai_core = _AICore(_Client(response=response))
    result = review_document_text(ai_core, CV, COVER)
    assert result.available is True
    assert result.issues
    assert result.issues[0]["code"] == "spelling"

    report = validate_generated_documents(
        cv_text=CV,
        cover_letter_text=COVER,
        source_text=SOURCE,
        ai_core=ai_core,
    )
    assert report["ai_review_available"] is True
    assert report["documents"]["cv"]["warnings"]
    # AI copy review is advisory; structural issues alone block downloads.
    assert report["ready"] is True


def test_ai_review_provider_failure_is_non_blocking_warning():
    clear_review_cache()
    ai_core = _AICore(_Client(error=RuntimeError("provider down")))
    report = validate_generated_documents(
        cv_text=CV,
        cover_letter_text=COVER,
        source_text=SOURCE,
        ai_core=ai_core,
    )
    assert report["ai_review_available"] is False
    assert report["ready"] is True
    assert any(
        issue["code"] == "ai_review_unavailable"
        for issue in report["documents"]["cv"]["warnings"]
    )


def test_malformed_ai_review_is_non_blocking():
    clear_review_cache()
    ai_core = _AICore(_Client(response="not json"))
    result = review_document_text(ai_core, CV, COVER)
    assert result == AIReviewResult([], False, "malformed_response")
