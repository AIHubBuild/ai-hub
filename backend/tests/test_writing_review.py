"""Tests for the deterministic writing-quality review stage."""

from app.domains.resume_ats.writing_review import (
    repair_unsupported_outcomes,
    review_writing,
)

SOURCE = (
    "Jane Doe\n"
    "IT Support Engineer at Acme GmbH (2021 - 2024)\n"
    "Supported 400 users across Active Directory and Microsoft 365.\n"
)

CLEAN_TAILORED = (
    "Jane Doe\n"
    "Professional Summary:\n"
    "IT support engineer with five years of experience.\n"
    "Skills:\n"
    "- Active Directory administration\n"
)

CLEAN_COVER = (
    "Dear Hiring Manager,\n"
    "I am interested in this support role because it centres on the "
    "systems I work with every day. I have supported 400 users across "
    "Active Directory and Microsoft 365, and I enjoy helping people get "
    "back to work quickly.\n"
    "\n"
    "In my current role I administer user accounts, support Microsoft 365 "
    "services, and troubleshoot access problems. I document recurring "
    "issues so the team can resolve them consistently. Recently I "
    "automated user provisioning with PowerShell, which made onboarding "
    "more consistent and gave me more time to support users directly. I "
    "also keep clear notes on each recurring problem so colleagues can "
    "follow the same steps.\n"
    "\n"
    "I work through problems in a structured way. I check the account, the "
    "device, and the network, then document what solved the issue so the "
    "next person can follow the same steps. I ask clear questions when a "
    "user describes a problem, and I explain the fix in plain language. I "
    "am comfortable working with a ticket queue and with colleagues who "
    "have deeper specialist knowledge. I also make time to learn new tools "
    "through documentation and practice, and I ask for help when a problem "
    "is outside my experience. I keep users updated while I work and "
    "confirm that the fix has actually solved their problem before I close "
    "a ticket. I would bring the same careful approach to this role and to "
    "your users.\n"
    "\n"
    "What I would bring to this position is a practical support mindset. I "
    "ask clear questions, check the account and the device, and explain "
    "the outcome without jargon. I also keep learning: when a tool is new "
    "to me, I read the documentation, test it in a lab, and ask for help "
    "when I need it.\n"
    "\n"
    "I would welcome the opportunity to discuss how my experience with "
    "Active Directory, Microsoft 365, and user support fits the team.\n"
    "\n"
    "Sincerely,\n"
    "Jane Doe\n"
)


def test_clean_documents_pass_review():
    review = review_writing(SOURCE, CLEAN_TAILORED, CLEAN_COVER)

    assert review.passed is True
    assert review.issues == []


def test_generic_phrase_is_flagged():
    review = review_writing(
        SOURCE,
        "Jane Doe\nI am passionate about leveraging my skills.\n",
        CLEAN_COVER,
    )

    codes = [issue.code for issue in review.issues]
    assert "generic_phrase" in codes
    assert any("passionate about leveraging" in i.message for i in review.issues)


def test_em_dash_overuse_is_flagged():
    text = (
        "Jane Doe\n"
        "I rebuilt the VPN gateway \u2014 the old one was failing \u2014 and "
        "then re-tested the tunnels \u2014 all clients reconnected.\n"
    )
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert any(issue.code == "em_dash_overuse" for issue in review.issues)


def test_a_single_em_dash_is_flagged():
    text = (
        "Jane Doe\n"
        "I rebuilt the VPN gateway \u2014 the old one was failing.\n"
    )
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert any(issue.code == "em_dash_overuse" for issue in review.issues)


def test_placeholder_text_is_flagged():
    text = "Jane Doe\n[Company] is hiring for a role that fits my background.\n"
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert any(issue.code == "placeholder_text" for issue in review.issues)


def test_generic_cover_letter_opening_is_flagged():
    review = review_writing(
        SOURCE,
        CLEAN_TAILORED,
        "Dear Hiring Manager,\nI am writing to apply for this role.\nJane Doe\n",
    )

    assert any(
        issue.code == "generic_phrase" and "writing to apply" in issue.message
        for issue in review.issues
    )


def test_required_generic_cover_letter_phrases_are_flagged():
    review = review_writing(
        SOURCE,
        CLEAN_TAILORED,
        (
            "Dear Hiring Manager,\n"
            "I am thrilled to apply. My background aligns closely with my "
            "experience, and I have a solid foundation in IT support.\n"
            "Jane Doe\n"
        ),
    )

    messages = [
        issue.message
        for issue in review.issues
        if issue.code == "generic_phrase"
    ]
    assert any("thrilled to apply" in message for message in messages)
    assert any("aligns closely with my experience" in message for message in messages)
    assert any("solid foundation in" in message for message in messages)


def test_unsupported_metric_is_flagged():
    review = review_writing(
        SOURCE,
        "Jane Doe\nReduced downtime by 40%.\n",
        CLEAN_COVER,
    )

    assert any(issue.code == "unsupported_metric" for issue in review.issues)
    assert any("40%" in issue.message for issue in review.issues)


def test_windows_version_is_not_treated_as_device_metric():
    review = review_writing(
        SOURCE,
        "Jane Doe\nSupported Windows 10/11 devices and endpoints.\n",
        CLEAN_COVER,
    )

    assert all(issue.code != "unsupported_metric" for issue in review.issues)


def test_supported_metric_is_not_flagged():
    review = review_writing(
        SOURCE,
        "Jane Doe\nSupported 400 users across Active Directory.\n",
        CLEAN_COVER,
    )

    assert all(issue.code != "unsupported_metric" for issue in review.issues)


def test_unsupported_project_section_is_flagged():
    review = review_writing(
        SOURCE,
        "Jane Doe\nProjects:\n- Built a Wireshark network lab.\n",
        CLEAN_COVER,
    )

    codes = [issue.code for issue in review.issues]
    assert "unsupported_section" in codes
    assert "unsupported_claim" in codes


def test_unsupported_claim_term_is_flagged():
    review = review_writing(
        SOURCE,
        CLEAN_TAILORED,
        (
            "Dear Hiring Manager,\n"
            "I followed ITIL practices and handled incident management and SLA "
            "reporting.\n"
            "Jane Doe\n"
        ),
    )

    codes = [issue.code for issue in review.issues]
    assert "unsupported_claim" in codes
    assert any("incident management" in issue.message for issue in review.issues)


def test_unsupported_outcome_is_flagged():
    review = review_writing(
        SOURCE,
        "Jane Doe\nImproved response times and reduced user downtime.\n",
        CLEAN_COVER,
    )

    assert any(issue.code == "unsupported_outcome" for issue in review.issues)


def test_supported_outcome_is_not_flagged():
    source = (
        "Jane Doe\nAutomated user provisioning with PowerShell, reducing "
        "manual setup time.\n"
    )
    review = review_writing(
        source,
        "Jane Doe\nReduced manual setup time with PowerShell automation.\n",
        None,
    )

    assert all(issue.code != "unsupported_outcome" for issue in review.issues)


def test_relative_time_claim_is_flagged():
    review = review_writing(
        SOURCE,
        CLEAN_TAILORED,
        "Dear Hiring Manager,\nI earned my ITIL Foundation this year.\nJane Doe\n",
    )

    assert any(issue.code == "unsupported_time_reference" for issue in review.issues)


def test_supported_claims_are_not_flagged():
    source = (
        "Jane Doe\n"
        "ITIL Foundation certified. Maintained SLA reporting and incident "
        "management processes.\n"
    )
    review = review_writing(
        source,
        "Jane Doe\nMaintained SLA reporting and incident management.\n",
        "Dear Hiring Manager,\nI maintained SLA reporting and incident management.\nJane Doe\n",
    )

    assert all(issue.code != "unsupported_claim" for issue in review.issues)


def test_repeated_sentence_openers_are_flagged():
    text = (
        "Jane Doe.\n"
        "The team upgraded the domain controllers. "
        "The team migrated mailboxes to Exchange Online. "
        "The team reduced onboarding time for new starters.\n"
    )
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert any(
        issue.code == "repetitive_openings"
        and "the team" in issue.message
        for issue in review.issues
    )


def test_transition_openers_are_not_flagged_as_repetition():
    text = (
        "Jane Doe.\n"
        "I upgraded the domain controllers. Furthermore, I migrated "
        "mailboxes. Furthermore, I automated patching. Furthermore, I "
        "documented the procedures.\n"
    )
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert all(issue.code != "repetitive_openings" for issue in review.issues)


def test_missing_applicant_name_is_flagged():
    tailored_without_name = (
        "Professional Summary:\n"
        "IT support engineer with five years of experience.\n"
    )
    cover_without_name = (
        "Dear Hiring Manager,\n"
        "I have supported 400 users across Active Directory.\n"
        "Sincerely,\n"
    )

    review = review_writing(SOURCE, tailored_without_name, cover_without_name)

    missing = [issue for issue in review.issues if issue.code == "missing_name"]
    assert len(missing) == 2
    assert any("Tailored resume" in issue.message for issue in missing)
    assert any("Cover letter" in issue.message for issue in missing)


def test_empty_documents_produce_no_issues():
    review = review_writing(SOURCE, None, None)

    assert review.passed is True
    assert review.issues == []


def test_markdown_artifacts_are_flagged():
    review = review_writing(
        "Jane Doe",
        "Jane Doe\n**Skills**\n- Active Directory",
        None,
    )

    assert any(issue.code == "markdown_artifact" for issue in review.issues)


def test_cover_letter_bullets_are_flagged():
    review = review_writing(
        "Jane Doe",
        None,
        "Dear Hiring Manager,\n- Active Directory experience\n- VPN support",
    )

    assert any(issue.code == "cover_letter_bullets" for issue in review.issues)

def test_repair_removes_unsupported_purpose_clause_without_dropping_fact():
    text = (
        "Jane Doe\n"
        "Assisted users with technical problems and documented recurring "
        "issues and solutions to improve support efficiency.\n"
    )

    repaired, changed = repair_unsupported_outcomes(text, SOURCE)

    assert changed is True
    assert "improve support efficiency" not in repaired
    assert "documented recurring issues and solutions" in repaired.lower()
    assert review_writing(SOURCE, repaired, None).passed is True


def test_repair_keeps_outcomes_that_the_source_supports():
    source = (
        "Jane Doe\n"
        "Reduced downtime by 20% and improved response times.\n"
    )
    text = "Jane Doe\nReduced downtime by 20% and improved response times.\n"

    repaired, changed = repair_unsupported_outcomes(text, source)

    assert changed is False
    assert repaired == text

def test_empty_resume_section_is_flagged():
    tailored = (
        "Jane Doe\n"
        "Professional Summary\n"
        "\n"
        "Skills\n"
        "- Active Directory\n"
    )

    review = review_writing(SOURCE, tailored, None)

    assert any(
        issue.code == "empty_section" and "Professional Summary" in issue.message
        for issue in review.issues
    )


def test_invented_collaboration_and_satisfaction_claims_are_flagged():
    text = (
        "Jane Doe\n"
        "Collaborated with senior administrators in joint problem-solving "
        "sessions and team meetings to improve user satisfaction.\n"
    )

    review = review_writing(SOURCE, text, None)
    codes = {issue.code for issue in review.issues}

    assert "unsupported_claim" in codes
    assert any(
        "collaborated with senior" in issue.message
        for issue in review.issues
        if issue.code == "unsupported_claim"
    )

def test_repair_removes_unsupported_relative_clause_without_dropping_fact():
    text = (
        "Jane Doe\n"
        "I use PowerShell and Python scripting to automate routine tasks, "
        "which helps reduce manual effort and supports more efficient "
        "troubleshooting.\n"
    )

    repaired, changed = repair_unsupported_outcomes(text, SOURCE)

    assert changed is True
    assert "which helps reduce" not in repaired
    assert "I use PowerShell and Python scripting to automate routine tasks." in repaired
    assert review_writing(SOURCE, repaired, None).passed is True

def test_repair_does_not_leave_a_dangling_sentence_fragment():
    text = (
        "Jane Doe\n"
        "These projects reflect my interest in improving efficiency.\n"
    )

    repaired, changed = repair_unsupported_outcomes(
        text, SOURCE, drop_unrepairable=False
    )

    # The unsupported outcome remains for the model/user to address, but
    # the repair must not produce a broken sentence such as "interest in."
    assert "interest in." not in repaired
    assert repaired == text
    assert changed is False

def test_repair_removes_which_has_helped_outcome_clause():
    text = (
        "Jane Doe\n"
        "I use PowerShell to automate small tasks, which has helped me "
        "improve efficiency and deepen my technical skills.\n"
    )

    repaired, changed = repair_unsupported_outcomes(
        text, SOURCE, drop_unrepairable=False
    )

    assert changed is True
    assert "improve efficiency" not in repaired
    assert "which has helped" not in repaired
    assert repaired.strip().endswith("I use PowerShell to automate small tasks.")

def test_repair_removes_unsupported_efficiency_adverb():
    text = (
        "Jane Doe\n"
        "I support users by resolving incidents efficiently.\n"
    )

    repaired, changed = repair_unsupported_outcomes(
        text, SOURCE, drop_unrepairable=False
    )

    assert changed is True
    assert "efficiently" not in repaired
    assert "resolving incidents." in repaired
    assert review_writing(SOURCE, repaired, None).passed is True


def test_sentence_start_at_employer_is_not_treated_as_invented():
    source = (
        "Jane Doe\n"
        "IT Support Engineer at Example GmbH (2021 - 2024)\n"
        "Supported Active Directory and Microsoft 365.\n"
    )
    cover = (
        "Dear Hiring Manager,\n"
        "At Example GmbH, I supported Active Directory and Microsoft 365.\n"
        "Sincerely,\nJane Doe\n"
    )

    review = review_writing(source, None, cover)

    assert all(issue.code != "invented_employer" for issue in review.issues)

def test_repair_removes_trailing_comparative_left_by_adverb_removal():
    text = (
        "Jane Doe\n"
        "I maintain documentation to help users resolve issues more efficiently.\n"
    )

    repaired, changed = repair_unsupported_outcomes(
        text, SOURCE, drop_unrepairable=False
    )

    assert changed is True
    assert "more" not in repaired
    assert "resolve issues." in repaired
    assert review_writing(SOURCE, repaired, None).passed is True
