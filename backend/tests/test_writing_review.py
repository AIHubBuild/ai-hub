"""Tests for the deterministic writing-quality review stage."""

from app.domains.resume_ats.writing_review import review_writing

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
    "I have supported 400 users across Active Directory and Microsoft 365.\n"
    "Recently I automated user provisioning with PowerShell.\n"
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
