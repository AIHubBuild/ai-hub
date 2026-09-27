"""Tests for the prompt registry (ai_core/prompts.py)."""

import pytest

from app.ai_core.prompts import PromptNotFoundError, PromptRegistry, PromptTemplate

ATS_ANALYSIS_V1 = PromptTemplate(
    prompt_id="resume_ats/ats_analysis",
    version=1,
    system="You analyze resumes.",
    user_template="Resume:\n{resume_text}\n\nJob description:\n{job_description}",
)

ATS_ANALYSIS_V2 = PromptTemplate(
    prompt_id="resume_ats/ats_analysis",
    version=2,
    system="You analyze resumes (improved).",
    user_template="{resume_text}",
)


def test_get_returns_latest_version_by_default():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V1)
    registry.register(ATS_ANALYSIS_V2)

    assert registry.get("resume_ats/ats_analysis") == ATS_ANALYSIS_V2


def test_get_returns_requested_version():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V1)
    registry.register(ATS_ANALYSIS_V2)

    assert registry.get("resume_ats/ats_analysis", version=1) == ATS_ANALYSIS_V1


def test_list_versions_is_sorted():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V2)
    registry.register(ATS_ANALYSIS_V1)

    assert registry.list_versions("resume_ats/ats_analysis") == [1, 2]


def test_duplicate_registration_raises():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V1)

    with pytest.raises(ValueError):
        registry.register(ATS_ANALYSIS_V1)


def test_unknown_prompt_id_raises():
    registry = PromptRegistry()

    with pytest.raises(PromptNotFoundError):
        registry.get("resume_ats/ats_analysis")


def test_unknown_prompt_version_raises():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V1)

    with pytest.raises(PromptNotFoundError):
        registry.get("resume_ats/ats_analysis", version=9)


def test_user_template_is_parameterized():
    registry = PromptRegistry()
    registry.register(ATS_ANALYSIS_V1)

    rendered = registry.get("resume_ats/ats_analysis").user_template.format(
        resume_text="Resume content", job_description="JD content"
    )

    assert "Resume content" in rendered
    assert "JD content" in rendered
