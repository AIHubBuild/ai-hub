"""Tests for the Resume ATS domain contracts (schemas) and the
deterministic → workflow interface."""

from app.domains.resume_ats.engine import run_deterministic_analysis
from app.domains.resume_ats.schemas import (
    AtsAnalysisRequest,
    AtsAnalysisResult,
    ats_analysis_result,
)

RESUME = "Experience with Active Directory and Microsoft 365."
JOB_DESCRIPTION = "Active Directory and PowerShell experience required."


def test_request_contract_holds_resume_and_job_description():
    request = AtsAnalysisRequest(resume_text=RESUME, job_description=JOB_DESCRIPTION)

    assert request.resume_text == RESUME
    assert request.job_description == JOB_DESCRIPTION


def test_result_contract_has_exactly_the_six_sections():
    result = AtsAnalysisResult(
        ats_score=50,
        matching_keywords=["active directory"],
        missing_keywords=["powershell"],
    )

    assert result.ats_score == 50
    assert result.matching_keywords == ["active directory"]
    assert result.missing_keywords == ["powershell"]
    assert result.improvement_suggestions is None
    assert result.tailored_resume is None
    assert result.cover_letter is None


def test_deterministic_analysis_feeds_the_result_contract():
    analysis = run_deterministic_analysis(RESUME, JOB_DESCRIPTION)

    result = ats_analysis_result(analysis)

    # matched: active directory; missing: powershell; base = 50 -> band 50
    assert result.ats_score == 50
    assert set(result.matching_keywords) == {"active directory"}
    assert set(result.missing_keywords) == {"powershell"}
    assert result.improvement_suggestions is None
    assert result.tailored_resume is None
    assert result.cover_letter is None


def test_result_contract_accepts_ai_sections_when_available():
    analysis = run_deterministic_analysis(RESUME, JOB_DESCRIPTION)

    result = ats_analysis_result(
        analysis,
        improvement_suggestions="Add PowerShell projects.",
        tailored_resume="Tailored resume text.",
        cover_letter="Cover letter text.",
    )

    assert result.ats_score == 50
    assert result.improvement_suggestions == "Add PowerShell projects."
    assert result.tailored_resume == "Tailored resume text."
    assert result.cover_letter == "Cover letter text."
