"""Representative writing-quality tests shared by both assistants.

These tests exercise the actual workflow and review paths rather than
only checking that a phrase appears in a prompt: scripted model output
containing an em dash and generic wording is pushed through the resume
workflow, normalised, and then reviewed.
"""

from app.ai_core.prompts import PromptRegistry
from app.ai_core.writing_style import normalize_writing
from app.domains.resume_ats.prompts import register_prompts as register_resume_prompts
from app.domains.resume_ats.workflow import build_ats_workflow, result_from_state
from app.domains.resume_ats.writing_review import review_writing
from app.domains.support_copilot.prompts import (
    TROUBLESHOOT_TEMPLATE_V6,
    register_prompts as register_support_prompts,
)

RESUME = (
    "Jane Doe\n"
    "IT Support Engineer at Acme GmbH (2021 - 2024)\n"
    "Supported Active Directory and Microsoft 365 for 400 users.\n"
)
JOB = (
    "We need Active Directory, Microsoft 365, VPN, PowerShell, and "
    "Intune experience."
)


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system, user):
        self.calls.append({"system": system, "user": user})
        return self.responses.pop(0)


def make_resume_registry() -> PromptRegistry:
    registry = PromptRegistry()
    register_resume_prompts(registry)
    return registry


def test_normalize_writing_removes_em_dashes_without_dropping_content():
    cleaned = normalize_writing(
        "Check the adapter status \u2014 then reconnect the VPN client."
    )

    assert "\u2014" not in cleaned
    assert cleaned == "Check the adapter status, then reconnect the VPN client."


def test_latest_prompts_reuse_the_shared_style_guide():
    resume_registry = make_resume_registry()
    support_registry = PromptRegistry()
    register_support_prompts(support_registry)

    resume_templates = [
        resume_registry.get("resume_ats/ats_analysis"),
        resume_registry.get("resume_ats/tailored_resume"),
        resume_registry.get("resume_ats/cover_letter"),
    ]
    support_template = support_registry.get("support_copilot/troubleshoot")

    for template in resume_templates + [support_template]:
        assert "SHARED WRITING STYLE" in template.user_template
        assert "Never use em dashes" in template.user_template

    # The latest support prompt is the consolidated version rather than
    # an ever-growing append-only prompt.
    assert support_template.version == 7
    assert len(support_template.user_template) < 12000


def test_generated_resume_output_is_normalised_then_reviewed():
    client = ScriptedClient(
        [
            "Add a measured PowerShell example \u2014 only if the resume supports it.",
            (
                "Jane Doe\n"
                "Professional Summary:\n"
                "I am passionate about leveraging my skills \u2014 across IT support.\n"
                "Skills:\n"
                "- Active Directory\n"
            ),
            (
                "Dear Hiring Manager,\n"
                "I am writing to apply \u2014 this role matches my support experience.\n"
                "Jane Doe\n"
            ),
        ]
    )
    graph = build_ats_workflow(client, make_resume_registry())

    state = graph.invoke({"resume_text": RESUME, "job_description": JOB})
    result = result_from_state(state)

    for value in (
        result.improvement_suggestions or "",
        result.tailored_resume or "",
        result.cover_letter or "",
    ):
        assert "\u2014" not in value

    review = review_writing(
        RESUME, result.tailored_resume, result.cover_letter
    )
    assert review.passed is False
    assert any(issue.code == "generic_phrase" for issue in review.issues)
    assert all(issue.code != "em_dash_overuse" for issue in review.issues)


def test_resume_prompt_is_job_specific_and_handles_missing_information():
    template = make_resume_registry().get("resume_ats/tailored_resume")

    rendered = template.user_template.format(
        match_score=40,
        matching_keywords="active directory, microsoft 365",
        partial_keywords="",
        missing_keywords="powershell, intune",
        requirement_evidence="- powershell (technical_skills, missing): no evidence",
        improvement_suggestions="Add an honest PowerShell project if one exists.",
        style_notes_section="",
        resume_text=RESUME,
        job_description=JOB,
    )

    assert RESUME in rendered
    assert JOB in rendered
    assert "leave it out instead of inventing or padding it" in rendered
    assert "Preserve employers, job titles, dates" in rendered


def test_support_prompt_renders_its_knowledge_base_and_user_message():
    rendered = TROUBLESHOOT_TEMPLATE_V6.user_template.format(
        knowledge_base="VPN GUIDE: reconnect the client and check the adapter.",
        conversation_history="user: VPN error 809",
        issue_type="vpn_issue",
        user_issue="Still failing after reconnecting.",
    )

    assert "VPN GUIDE: reconnect the client and check the adapter." in rendered
    assert "Still failing after reconnecting." in rendered
    assert "lowest risk first" in rendered
    assert "Only cite section names, document titles, or references" in rendered
    assert "never invent" in rendered.lower()
