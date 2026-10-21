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
    latest_versions = {
        "resume_ats/ats_analysis": 5,
        "resume_ats/tailored_resume": 6,
        "resume_ats/cover_letter": 6,
    }
    for prompt_id in EXPECTED_PROMPT_IDS:
        assert registry.get(prompt_id).version == latest_versions[prompt_id]


def test_templates_are_versioned_and_retrievable_by_version():
    registry = make_registered_registry()

    template = registry.get("resume_ats/ats_analysis", version=1)

    assert template == ATS_ANALYSIS_TEMPLATE


def test_latest_version_keeps_original_content_and_adds_accuracy_rules():
    registry = make_registered_registry()

    latest = registry.get("resume_ats/ats_analysis")

    assert latest.version == 5
    assert "Your task is to evaluate a candidate resume against a target job" in latest.user_template
    assert "{partial_keywords}" in latest.user_template
    assert "{requirement_evidence}" in latest.user_template
    assert "never inventing or exaggerating experience" in latest.user_template
    assert "MANDATORY HUMAN WRITING STYLE" in latest.user_template


def test_registering_a_new_version_does_not_replace_the_old():
    registry = make_registered_registry()
    registry.register(
        ATS_ANALYSIS_TEMPLATE.model_copy(update={"version": 6})
    )

    assert registry.get("resume_ats/ats_analysis").version == 6
    assert registry.get("resume_ats/ats_analysis", version=5).version == 5
    assert registry.get("resume_ats/ats_analysis", version=4).version == 4
    assert registry.get("resume_ats/ats_analysis", version=3).version == 3
    assert registry.get("resume_ats/ats_analysis", version=2).version == 2
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


def test_tailored_resume_v3_adds_natural_writing_rules():
    from app.domains.resume_ats.prompts import TAILORED_RESUME_TEMPLATE_V3

    template = TAILORED_RESUME_TEMPLATE_V3.user_template

    assert "NATURAL WRITING RULES" in template
    assert "Do not use em dashes as a default style" in template
    assert "second-line support" in template
    assert "Preserve the applicant's professional voice" in template
    assert "{style_notes_section}" in template
    # Version 2 accuracy rules are preserved in version 3.
    assert "Preserve the exact employers, job titles, and dates" in template
    assert "Clearly label lab work, coursework, training" in template


def test_cover_letter_v3_adds_natural_writing_rules():
    from app.domains.resume_ats.prompts import COVER_LETTER_TEMPLATE_V3

    template = COVER_LETTER_TEMPLATE_V3.user_template

    assert "NATURAL WRITING RULES" in template
    assert "contractions" in template
    assert "Furthermore" in template
    assert "resonates with me" in template
    assert "Do not infer personality traits" in template
    assert "{style_notes_section}" in template
    assert (
        "Only reference experience and skills that appear in the optimized "
        "resume" in template
    )


def test_latest_tailored_resume_forbids_inventing_facts_and_metrics():
    template = make_registered_registry().get("resume_ats/tailored_resume")

    assert template.version == 6
    rules = template.user_template
    assert "Preserve the exact employers, job titles, and dates" in rules
    assert "never add experience, metrics, certifications, employers" in rules
    assert "Do NOT invent fake experience" in rules
    assert "invent certifications" in rules
    assert "fake years of experience" in rules
    assert "Naturally integrate missing keywords where appropriate and truthful" in rules
    assert "leave it out instead of inventing or padding it" in rules


def test_latest_cover_letter_forbids_new_claims_and_exaggeration():
    template = make_registered_registry().get("resume_ats/cover_letter")

    assert template.version == 6
    rules = template.user_template
    assert "Do not introduce new claims, achievements, or employers" in rules
    assert "If a job requirement is not supported by the optimized resume" in rules
    assert "Avoid overly enthusiastic or exaggerated tone" in rules
    assert "Do not infer personality traits, motivations, or anecdotes" in rules
    assert "Do not use \"I am writing to apply\"" in rules


def test_latest_analysis_prompt_requires_truthful_keyword_guidance():
    template = make_registered_registry().get("resume_ats/ats_analysis")

    assert template.version == 5
    rules = template.user_template
    assert "Do not claim evidence that is not there" in rules
    assert "never inventing or exaggerating experience" in rules
    assert "recommend fake experience" in rules
    assert "suggest mentioning lab exposure" in rules
    assert "MANDATORY HUMAN WRITING STYLE" in rules


def test_latest_tailored_resume_is_job_specific_and_source_grounded():
    template = make_registered_registry().get("resume_ats/tailored_resume")

    rules = template.user_template
    assert "MASTER RESUME" in rules
    assert "JOB DESCRIPTION" in rules
    assert "tailored specifically to the target job description" in rules
    assert "Preserve employers, job titles, dates" in rules


def test_latest_generation_prompts_require_human_style_and_revision():
    registry = make_registered_registry()

    for prompt_id in ("resume_ats/tailored_resume", "resume_ats/cover_letter"):
        rules = registry.get(prompt_id).user_template
        assert "Write like a real human" in rules
        assert "Avoid buzzwords, corporate jargon" in rules
        assert "I am thrilled to apply" in rules
        assert "aligns closely with my experience" in rules
        assert "with a solid foundation in" in rules
        assert "Never invent evidence" in rules
        assert "copying the job description" in rules
        assert "{revision_section}" in rules


def test_latest_generation_prompts_render_revision_context():
    from app.domains.resume_ats.prompts import (
        COVER_LETTER_TEMPLATE_V5,
        TAILORED_RESUME_TEMPLATE_V5,
    )

    tailored = TAILORED_RESUME_TEMPLATE_V5.user_template.format(
        match_score=60,
        matching_keywords="active directory",
        partial_keywords="",
        missing_keywords="powershell",
        requirement_evidence="- active directory: Administered AD",
        improvement_suggestions="Be specific about AD work.",
        style_notes_section="",
        resume_text="Jane Doe\nAdministered Active Directory.",
        job_description="Active Directory required.",
        revision_section="REVISION PASS FOR THE TAILORED RESUME:\n- generic_phrase",
    )
    cover = COVER_LETTER_TEMPLATE_V5.user_template.format(
        tailored_resume="Jane Doe\nAdministered Active Directory.",
        job_description="Active Directory required.",
        resume_text="Jane Doe\nAdministered Active Directory.",
        style_notes_section="",
        revision_section="REVISION PASS FOR THE COVER LETTER:\n- generic_phrase",
    )

    assert "REVISION PASS FOR THE TAILORED RESUME" in tailored
    assert "REVISION PASS FOR THE COVER LETTER" in cover
    assert "{" not in tailored
    assert "{" not in cover


def test_app_factory_registers_resume_ats_prompts():
    app = create_app()

    registry = app.state.ai_core.prompts

    latest_versions = {
        "resume_ats/ats_analysis": 5,
        "resume_ats/tailored_resume": 6,
        "resume_ats/cover_letter": 6,
    }
    for prompt_id in EXPECTED_PROMPT_IDS:
        assert registry.get(prompt_id).version == latest_versions[prompt_id]
        assert registry.get(prompt_id, version=1).version == 1


def test_latest_prompts_remove_unsafe_keyword_injection_and_it_only_rules():
    registry = make_registered_registry()
    for prompt_id in (
        "resume_ats/ats_analysis",
        "resume_ats/tailored_resume",
        "resume_ats/cover_letter",
    ):
        template = registry.get(prompt_id)
        assert "PERMANENT ATS AND DOCUMENT RULES" in template.user_template
        assert "MUST actively apply" not in template.user_template
        assert "IT support, infrastructure" not in template.user_template
        assert "junior-level positioning" not in template.user_template
        assert "Markdown" in template.user_template
        assert "Do not invent" in template.user_template
