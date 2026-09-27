"""Tests for the Resume ATS prompt assets and their registration."""

from app.ai_core.prompts import PromptRegistry
from app.domains.resume_ats.prompts import (
    ATS_ANALYSIS_TEMPLATE,
    COVER_LETTER_TEMPLATE,
    PROMPT_TEMPLATES,
    TAILORED_RESUME_TEMPLATE,
    register_prompts,
)
from app.main import create_app

EXPECTED_PROMPT_IDS = {
    "resume_ats/ats_analysis",
    "resume_ats/tailored_resume",
    "resume_ats/cover_letter",
}


def make_registered_registry() -> PromptRegistry:
    registry = PromptRegistry()
    register_prompts(registry)
    return registry


def test_registers_exactly_the_three_workflow_templates():
    registry = make_registered_registry()

    assert {t.prompt_id for t in PROMPT_TEMPLATES} == EXPECTED_PROMPT_IDS
    for prompt_id in EXPECTED_PROMPT_IDS:
        assert registry.get(prompt_id).version == 1


def test_templates_are_versioned_and_retrievable_by_version():
    registry = make_registered_registry()

    template = registry.get("resume_ats/ats_analysis", version=1)

    assert template == ATS_ANALYSIS_TEMPLATE


def test_registering_a_new_version_does_not_replace_the_old():
    registry = make_registered_registry()
    registry.register(
        ATS_ANALYSIS_TEMPLATE.model_copy(update={"version": 2})
    )

    assert registry.get("resume_ats/ats_analysis") == ATS_ANALYSIS_TEMPLATE.model_copy(
        update={"version": 2}
    )
    assert registry.get("resume_ats/ats_analysis", version=1) == ATS_ANALYSIS_TEMPLATE


def test_re_registering_same_version_raises():
    registry = make_registered_registry()

    import pytest

    with pytest.raises(ValueError):
        register_prompts(registry)


def test_analysis_template_renders_all_placeholders():
    rendered = ATS_ANALYSIS_TEMPLATE.user_template.format(
        match_score=50,
        matching_keywords="active directory",
        missing_keywords="powershell",
        resume_text="Resume text",
        job_description="Job text",
    )

    assert "50" in rendered
    assert "active directory" in rendered
    assert "powershell" in rendered
    assert "Resume text" in rendered
    assert "Job text" in rendered
    assert "{" not in rendered


def test_tailored_resume_template_renders_all_placeholders():
    rendered = TAILORED_RESUME_TEMPLATE.user_template.format(
        match_score=50,
        matching_keywords="vpn",
        missing_keywords="dhcp",
        improvement_suggestions="Suggestions",
        resume_text="Resume text",
        job_description="Job text",
    )

    assert "dhcp" in rendered
    assert "Suggestions" in rendered
    assert "Resume text" in rendered
    assert "Job text" in rendered
    assert "{" not in rendered


def test_cover_letter_template_renders_all_placeholders():
    rendered = COVER_LETTER_TEMPLATE.user_template.format(
        tailored_resume="Tailored text", job_description="Job text"
    )

    assert "Tailored text" in rendered
    assert "Job text" in rendered
    assert "{" not in rendered


def test_no_template_uses_legacy_marker_sections():
    for template in PROMPT_TEMPLATES:
        assert "===" not in template.system
        assert "===" not in template.user_template


def test_app_factory_registers_resume_ats_prompts():
    app = create_app()

    registry = app.state.ai_core.prompts

    for prompt_id in EXPECTED_PROMPT_IDS:
        assert registry.get(prompt_id).version == 1
