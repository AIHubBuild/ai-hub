"""Tests for the deterministic writing-quality review stage."""

from app.domains.resume_ats.writing_review import review_writing

SOURCE = "Jane Doe\nIT Support Engineer at Acme GmbH (2021 - 2024)\n"

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


def test_two_em_dashes_are_not_flagged():
    text = (
        "Jane Doe\n"
        "I rebuilt the VPN gateway \u2014 the old one was failing \u2014 and "
        "then re-tested the tunnels.\n"
    )
    review = review_writing(SOURCE, text, CLEAN_COVER)

    assert all(issue.code != "em_dash_overuse" for issue in review.issues)


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
