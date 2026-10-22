"""Regression coverage for the Aptare IT Support Specialist case.

The fixture is a representative master resume and vacancy built from the
reported evidence. It is not a verbatim copy of a live posting. The
tests assert matching rules and evidence classifications rather than a
specific score for this employer.
"""

from app.domains.resume_ats.job_description import (
    extract_sections,
    strip_boilerplate,
)
from app.domains.resume_ats.matching import (
    MATCHED,
    MISSING,
    PARTIAL,
    analyze_job_match,
)
from app.domains.resume_ats.prompts import (
    COVER_LETTER_TEMPLATE_V7,
    TAILORED_RESUME_TEMPLATE_V7,
)
from app.domains.resume_ats.writing_review import review_writing

REFERENCE_YEAR = 2026

MASTER_RESUME = """Jane Doe
IT Support Engineer
Munich, Germany | jane@example.com | +49 123 456789

Professional Summary
IT Support Engineer with experience in first- and second-level support,
Microsoft 365 administration, Windows 10/11, Active Directory, Entra ID,
and networking fundamentals. Known for troubleshooting, incident
diagnosis, ticket management, documentation, and clear user support.

Technical Skills
Microsoft 365, Outlook, Teams, Exchange Online, SharePoint, Active
Directory, Entra ID, Windows 10/11, DNS, DHCP, VPN, TCP/IP, PowerShell,
Python, Jira, ITIL, hardware setup, printer troubleshooting, user
permissions, onboarding, offboarding.

Professional Experience
IT Support Engineer, Example GmbH, Munich (2022 - Present)
- Provide first- and second-level technical support to 250 users in
  German and English.
- Administer Microsoft 365, Outlook, Teams, Exchange Online, Active
  Directory, and Entra ID accounts.
- Troubleshoot Windows 10/11, email, login, printer, permissions, DNS,
  VPN, and TCP/IP issues.
- Diagnose incidents, document resolutions in the ticket system, and
  escalate complex cases to senior administrators.
- Configure and replace hardware and workstations for new employees.
- Maintain the internal knowledge base and user documentation.
- Support onboarding and offboarding, including account provisioning and
  access control.
- Use PowerShell and Python for small automation tasks and lab projects.

IT Support Assistant, Another GmbH, Munich (2020 - 2022)
- Handled ticket intake, prioritisation, and processing.
- Supported users remotely and on site.
- Documented recurring problems and solutions.

Projects
Home Lab: Windows Server, Active Directory, DNS, DHCP, VPN, PowerShell
automation.

Education
BSc Computer Science, Example University (2019)

Certifications
Microsoft 365 Fundamentals, ITIL Foundation

Languages
German B2, English C1
"""

APTARE_JOB = """IT Support Specialist (m/w/d)
Aptare GmbH
Standort: Großhadern und remote

Über uns
Aptare GmbH ist ein IT-Dienstleister mit Kunden in Großhadern und im
Remote-Betrieb.

Deine Aufgaben
- First- and second-level support for our clients
- Ticket intake, prioritization, and processing
- Troubleshooting Microsoft 365, Windows, email, login, printer, and
  permissions issues
- Hardware setup, replacement, and basic workstation configuration
- Networking fundamentals including IP, DNS, and VPN
- Error diagnosis and documentation
- Knowledge-base maintenance
- Clear communication with users
- Escalation and collaboration with senior administrators

Dein Profil
- Completed IT training or comparable qualification
- Experience in IT support and technical support
- Strong knowledge of Microsoft 365 and Windows
- problem-solving and clear communication skills
- PowerShell, automation, and security are an advantage
- Interest in progressing toward system administration

Wir bieten
- Flexible working hours
- 30 days holiday
- Further training opportunities
- A motivated team
"""


def analyze_aptare(resume: str = MASTER_RESUME):
    return analyze_job_match(
        resume,
        strip_boilerplate(APTARE_JOB),
        reference_year=REFERENCE_YEAR,
    )


def terms(analysis) -> dict:
    return {term.term: term for term in analysis.terms}


# ---------------------------------------------------------------
# Extraction and classification
# ---------------------------------------------------------------


def test_german_sections_are_recognized_and_benefits_are_not_requirements():
    cleaned = strip_boilerplate(APTARE_JOB)
    sections = extract_sections(cleaned)

    assert any("First- and second-level" in line for line in sections["responsibilities"])
    assert any("Microsoft 365" in line for line in sections["essential"])
    assert all(
        "30 days holiday" not in line
        for lines in sections.values()
        for line in lines
    )
    assert all(
        "Flexible working hours" not in line
        for lines in sections.values()
        for line in lines
    )

    analysis = analyze_aptare()
    requirement_text = " ".join(r.text for r in analysis.requirements)
    assert "30 days holiday" not in requirement_text
    assert "A motivated team" not in requirement_text


def test_explicitly_supported_requirements_are_recognized():
    analysis = analyze_aptare()

    for term in (
        "microsoft 365",
        "windows",
        "dns",
        "vpn",
        "technical support",
        "troubleshooting",
    ):
        assert term in terms(analysis)
        assert terms(analysis)[term].status == MATCHED, term

    # The resume shows relevant work context, not a bare skills list.
    ad = next(r for r in analysis.requirements if "Microsoft 365, Windows" in r.text)
    assert ad.status == MATCHED
    assert ad.evidence


def test_synonyms_case_and_punctuation_are_normalized():
    resume = (
        "Jane Doe\n"
        "IT-Support Engineer at Acme (2022 - Present)\n"
        "Administered Microsoft-365 and supported TCP/IP, DNS and VPN.\n"
        "Provided problem solving and troubleshooting for users.\n"
    )
    jd = (
        "Requirements:\n"
        "- Technical support experience\n"
        "- Microsoft 365 administration\n"
        "- Problem-solving\n"
        "- TCP/IP networking\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)
    by_term = terms(analysis)

    assert by_term["technical support"].status == PARTIAL
    assert by_term["microsoft 365"].status == MATCHED
    assert by_term["problem-solving"].status == MATCHED
    assert by_term["tcp/ip"].status == MATCHED


def test_unsupported_requirements_are_not_reported_as_matched():
    resume = (
        "Jane Doe\n"
        "IT Support Engineer at Acme (2022 - Present)\n"
        "Administered Microsoft 365 and supported Windows users.\n"
    )
    jd = (
        "Requirements:\n"
        "- Microsoft 365 administration\n"
        "- Intune device management\n"
        "- Kubernetes administration\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)
    by_term = terms(analysis)

    assert by_term["microsoft 365"].status == MATCHED
    assert by_term["intune"].status == MISSING
    assert all(
        requirement.status == MISSING
        for requirement in analysis.requirements
        if "Kubernetes" in requirement.text
    )


def test_evidence_confidence_is_separate_from_requirement_coverage():
    strong_resume = (
        "Jane Doe\n"
        "IT Support Engineer at Acme (2019 - 2026)\n"
        "Administered Active Directory and Microsoft 365 for 400 users.\n"
        "Reduced ticket backlog by 30% and improved response times.\n"
        "Earned ITIL Foundation certification.\n"
        "BSc Computer Science.\n"
    )
    unrelated_jd = (
        "Requirements:\n"
        "- Intune administration\n"
        "- Kubernetes administration\n"
    )

    analysis = analyze_job_match(
        strong_resume, unrelated_jd, reference_year=REFERENCE_YEAR
    )

    assert analysis.requirement_coverage == 0
    assert analysis.evidence_confidence >= 70
    assert analysis.estimated_score == 0


def test_score_breakdown_matches_the_reported_coverage_and_score():
    analysis = analyze_aptare()

    weighted = [
        (row.weight, row.score)
        for row in analysis.breakdown
        if row.weight > 0 and row.total > 0
    ]
    total_weight = sum(weight for weight, _ in weighted)
    coverage = sum(weight * score for weight, score in weighted) / total_weight

    assert abs(coverage - analysis.requirement_coverage) <= 1
    expected = round(
        coverage
        * (0.7 + 0.3 * analysis.evidence_confidence / 100)
    )
    assert abs(expected - analysis.estimated_score) <= 1

    for row in analysis.breakdown:
        assert row.supported + row.partial + row.unverified + row.missing == row.total


def test_strong_aptare_evidence_produces_a_high_but_not_perfect_score():
    analysis = analyze_aptare()

    # This fixture contains explicit support, Microsoft 365, Windows,
    # networking, hardware, documentation, and qualification evidence.
    assert analysis.requirement_coverage >= 85
    assert analysis.estimated_score >= 80
    # Honest gaps remain: collaboration wording and interest in system
    # administration are not demonstrated by the source resume.
    assert analysis.estimated_score < 100


# ---------------------------------------------------------------
# Prompt and document quality safeguards
# ---------------------------------------------------------------


def test_tailored_resume_prompt_prioritizes_relevant_verified_evidence():
    rules = TAILORED_RESUME_TEMPLATE_V7.user_template

    assert "this specific vacancy" in rules
    assert "Reorder and refine" in rules
    assert "Preserve important relevant evidence" in rules
    assert "Distinguish professional employment from personal projects" in rules
    assert "Preserve the exact employers, job titles, and dates" in rules
    assert "MUST actively apply" not in rules
    assert "Do not invent" in rules


def test_cover_letter_prompt_requires_detail_and_consistency():
    rules = COVER_LETTER_TEMPLATE_V7.user_template

    assert "350 to 450 words" in rules
    assert "proper greeting" in rules
    assert "why is this particular candidate a credible fit" in rules
    assert "conventional sign-off" in rules
    assert "No bullet lists, headings" in rules
    assert "must agree with the master resume" in rules
    assert "{requirement_evidence}" in rules


def test_short_or_unstructured_cover_letters_are_flagged():
    review = review_writing(
        MASTER_RESUME,
        None,
        "Dear Hiring Team,\nI can support your users.\nJane Doe",
        job_description=APTARE_JOB,
    )
    codes = {issue.code for issue in review.issues}

    assert "cover_letter_too_short" in codes
    assert "missing_closing" in codes


def test_unsupported_employer_and_metric_claims_are_flagged():
    cover = (
        "Dear Hiring Team,\n"
        + "I have supported users with Microsoft 365 and Windows. " * 40
        + "\nI reduced downtime by 90% at Globex GmbH.\n"
        "Sincerely,\nJane Doe\n"
    )

    review = review_writing(
        MASTER_RESUME,
        MASTER_RESUME,
        cover,
        job_description=APTARE_JOB,
    )
    codes = {issue.code for issue in review.issues}

    assert "unsupported_metric" in codes
    assert "invented_employer" in codes


def test_target_employer_from_job_description_is_not_treated_as_invented():
    cover = (
        "Dear Aptare Hiring Team,\n"
        + "I have supported users with Microsoft 365, Windows, and VPN. " * 40
        + "\nI would welcome the opportunity to discuss the role.\n"
        "Sincerely,\nJane Doe\n"
    )

    review = review_writing(
        MASTER_RESUME,
        MASTER_RESUME,
        cover,
        job_description=APTARE_JOB,
    )

    assert all(issue.code != "invented_employer" for issue in review.issues)
