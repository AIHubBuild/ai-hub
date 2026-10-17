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
    "Automated user provisioning with PowerShell during onboarding.\n"
    "Maintained VPN connectivity and resolved endpoint issues.\n"
)
JOB = (
    "Requirements:\n"
    "- Active Directory administration\n"
    "- Microsoft 365 administration\n"
    "- PowerShell scripting\n"
    "- VPN troubleshooting\n"
    "Experience:\n"
    "- 3+ years in an IT support role\n"
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

    for template in resume_templates:
        assert "MANDATORY HUMAN WRITING STYLE" in template.user_template
        assert "Write like a real human" in template.user_template
        assert "Never use em dashes" in template.user_template

    for prompt_id in ("resume_ats/tailored_resume", "resume_ats/cover_letter"):
        assert "{revision_section}" in resume_registry.get(prompt_id).user_template

    assert "SHARED WRITING STYLE" in support_template.user_template
    assert "Never use em dashes" in support_template.user_template

    # The latest support prompt is the consolidated version rather than
    # an ever-growing append-only prompt.
    assert support_template.version == 7
    assert len(support_template.user_template) < 12000


def test_review_triggers_meaningful_revision_of_both_documents():
    client = ScriptedClient(
        [
            "Add a measured PowerShell example only if the resume supports it.",
            (
                "Jane Doe\n"
                "Professional Summary:\n"
                "I am thrilled to apply \u2014 I have a solid foundation in IT "
                "support and reduced downtime by 40%.\n"
                "Skills:\n"
                "- Active Directory\n"
            ),
            (
                "Dear Hiring Manager,\n"
                "I am writing to apply \u2014 my experience aligns closely with "
                "your needs.\n"
                "Jane Doe\n"
            ),
            (
                "Jane Doe\n"
                "Professional Summary:\n"
                "IT support engineer with three years of experience supporting "
                "Active Directory and Microsoft 365 for 400 users.\n"
                "Automated user provisioning with PowerShell during onboarding.\n"
                "Resolved VPN and endpoint issues for staff at Acme.\n"
            ),
            (
                "Dear Hiring Manager,\n"
                "I supported 400 users across Active Directory and Microsoft 365 "
                "at Acme. I also automated user provisioning with PowerShell, "
                "which reduced manual setup work during onboarding.\n"
                "Jane Doe\n"
            ),
        ]
    )
    graph = build_ats_workflow(client, make_resume_registry())

    state = graph.invoke({"resume_text": RESUME, "job_description": JOB})
    result = result_from_state(state)

    assert len(client.calls) == 5
    assert "I am thrilled to apply" not in (result.tailored_resume or "")
    assert "aligns closely with my experience" not in (result.cover_letter or "")
    assert "40%" not in (result.tailored_resume or "")
    assert "400 users" in (result.tailored_resume or "")
    assert "400 users" in (result.cover_letter or "")

    review = review_writing(
        RESUME, result.tailored_resume, result.cover_letter
    )
    assert review.passed is True, review.issues

    revision_prompts = client.calls[3]["user"] + "\n" + client.calls[4]["user"]
    assert "REVISION PASS FOR THE TAILORED RESUME" in revision_prompts
    assert "REVISION PASS FOR THE COVER LETTER" in revision_prompts
    assert "generic_phrase" in revision_prompts
    assert "unsupported_metric" in revision_prompts
    assert "I am thrilled to apply" in revision_prompts
    assert "Current draft:" in revision_prompts


def test_human_style_and_factual_rules_reach_generation_calls():
    client = ScriptedClient(
        [
            "Add one specific PowerShell example.",
            "Jane Doe\nTailored resume content grounded in Acme work.",
            "Cover letter grounded in Acme work.\nJane Doe",
        ]
    )
    graph = build_ats_workflow(client, make_resume_registry())

    graph.invoke({"resume_text": RESUME, "job_description": JOB})

    assert len(client.calls) == 3
    tailored_prompt = client.calls[1]["user"]
    cover_prompt = client.calls[2]["user"]
    for prompt in (tailored_prompt, cover_prompt):
        assert "MANDATORY HUMAN WRITING STYLE" in prompt
        assert "I am thrilled to apply" in prompt
        assert "aligns closely with my experience" in prompt
        assert "with a solid foundation in" in prompt
        assert "Never invent evidence" in prompt
        assert "copying the job description" in prompt
        assert "No revision pass is needed" in prompt

    assert RESUME in tailored_prompt
    assert JOB in tailored_prompt
    assert JOB in cover_prompt

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
        revision_section="No revision pass is needed.",
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
