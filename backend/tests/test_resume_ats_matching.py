"""Tests for the evidence-based resume-to-job analyzer (matching.py)."""

from app.domains.resume_ats.matching import (
    MATCHED,
    MISSING,
    PARTIAL,
    SCORE_LABEL,
    UNVERIFIED,
    analyze_job_match,
)

REFERENCE_YEAR = 2026

RESUME = (
    "Jane Doe\n"
    "IT Support Engineer at Acme GmbH (2021 - 2024)\n"
    "Administered Active Directory and Microsoft 365 for 400 users.\n"
    "Supported VPN and network troubleshooting across three sites.\n"
    "Built PowerShell scripts for user provisioning.\n"
)

JD = (
    "Requirements:\n"
    "- Active Directory administration\n"
    "- Microsoft 365 administration\n"
    "- PowerShell scripting\n"
    "- Intune experience\n"
    "- Jira for incident tracking\n"
    "\n"
    "Preferred:\n"
    "- ITIL certification\n"
    "- DNS troubleshooting\n"
)


def analyze(resume=RESUME, jd=JD):
    return analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)


def test_score_is_reproducible():
    first = analyze()
    second = analyze()

    assert first == second
    assert first.estimated_score == second.estimated_score


def test_score_is_labeled_an_estimate():
    analysis = analyze()

    assert analysis.score_label == SCORE_LABEL
    assert "estimated" in analysis.score_label.lower()
    assert "resume-to-job" in analysis.score_label.lower()


def test_supported_partial_and_missing_are_distinguished():
    analysis = analyze()

    assert "active directory" in analysis.supported_terms
    assert "microsoft 365" in analysis.supported_terms
    assert "powershell" in analysis.supported_terms
    assert "intune" in analysis.missing_terms
    assert "jira" in analysis.missing_terms
    assert "itil" in analysis.missing_terms
    assert "dns" in analysis.missing_terms


def test_synonym_matches_are_partial_with_evidence():
    resume = (
        "Jane Doe\n"
        "Provided help desk support and managed office 365 tenants.\n"
    )
    jd = (
        "Requirements:\n"
        "- Technical support experience\n"
        "- Microsoft 365 administration\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    assert "technical support" in analysis.partial_terms
    assert "microsoft 365" in analysis.partial_terms
    for term in ("technical support", "microsoft 365"):
        entry = analysis.evidence_map[term]
        assert entry["status"] == PARTIAL
        assert entry["evidence"]


def test_evidence_lists_resume_lines_not_keywords_alone():
    analysis = analyze()

    entry = analysis.evidence_map["active directory"]
    assert entry["status"] == MATCHED
    assert any("Administered Active Directory" in line for line in entry["evidence"])


def test_missing_terms_have_no_evidence():
    analysis = analyze()

    entry = analysis.evidence_map["jira"]
    assert entry["status"] == MISSING
    assert entry["evidence"] == []


def test_preferred_terms_are_categorized_separately():
    analysis = analyze()

    itil = next(r for r in analysis.requirements if "ITIL" in r.text)
    active = next(r for r in analysis.requirements if "Active Directory" in r.text)

    assert itil.section == "preferred"
    assert itil.mandatory is False
    assert itil.dimension == "qualifications"
    assert active.mandatory is True
    assert active.dimension == "skills"


def test_essential_and_preferred_weights_apply():
    resume = (
        "Jane Doe\n"
        "Administered Active Directory for 400 users.\n"
    )
    jd = (
        "Requirements:\n"
        "- Active Directory administration\n"
        "- Intune experience\n"
        "\n"
        "Preferred:\n"
        "- ITIL certification\n"
    )
    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    skills = next(e for e in analysis.breakdown if e.category == "skills")
    experience = next(e for e in analysis.breakdown if e.category == "experience")
    qualifications = next(
        e for e in analysis.breakdown if e.category == "qualifications"
    )

    assert skills.score == 100
    assert experience.score == 0
    assert qualifications.score == 0
    assert analysis.estimated_score < 50


def test_keyword_counts_and_breakdown_come_from_the_same_result():
    analysis = analyze()

    term_total = len(analysis.terms)
    assert (
        len(analysis.supported_terms)
        + len(analysis.partial_terms)
        + len(analysis.unverified_terms)
        + len(analysis.missing_terms)
        == term_total
    )
    for row in analysis.breakdown:
        assert (
            row.supported + row.partial + row.unverified + row.missing
            == row.total
        )
    assert len(analysis.requirement_evidence) == len(analysis.requirements)


def test_no_recognizable_requirements_yields_zero_and_no_crash():
    analysis = analyze_job_match(RESUME, "We are hiring a nice person.")

    assert analysis.estimated_score == 0
    assert analysis.requirements == []
    assert analysis.terms == []


def test_breakdown_is_reported_for_all_requested_dimensions():
    analysis = analyze()

    skills = next(e for e in analysis.breakdown if e.category == "skills")
    assert skills.total >= 3
    assert skills.supported + skills.partial + skills.unverified + skills.missing == skills.total
    assert {entry.category for entry in analysis.breakdown} >= {
        "skills",
        "experience",
        "qualifications",
    }


# ---------------------------------------------------------------
# Regression scenarios
# ---------------------------------------------------------------


def test_perfect_keyword_match_with_incomplete_experience_is_not_100():
    resume = (
        "Managed Microsoft 365 tenants, VPN gateways, Microsoft Teams "
        "deployments, and Windows 11 fleets."
    )
    jd = "We need Microsoft 365, VPN, Teams and Windows experience."

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    assert set(analysis.supported_terms) == {
        "microsoft 365",
        "vpn",
        "teams",
        "windows",
    }
    assert analysis.requirement_coverage == 100
    assert analysis.evidence_confidence < 100
    assert analysis.estimated_score < 100


def test_missing_mandatory_qualification_lowers_the_score():
    resume = (
        "Jane Doe\n"
        "IT Support Engineer at Acme (2021 - 2025)\n"
        "Administered Active Directory and Microsoft 365 for 400 users.\n"
        "Reduced ticket backlog by 30%.\n"
    )
    jd = (
        "Requirements:\n"
        "- Active Directory administration\n"
        "- Microsoft 365 administration\n"
        "- ITIL certification\n"
        "Experience:\n"
        "- 3+ years in IT support\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    itil = next(r for r in analysis.requirements if "ITIL" in r.text)
    assert itil.status == MISSING
    assert "itil" in analysis.missing_terms
    qualification_row = next(
        e for e in analysis.breakdown if e.category == "qualifications"
    )
    assert qualification_row.score == 0
    assert analysis.estimated_score < 90


def test_inconsistent_evidence_is_unverified_not_matched():
    resume = (
        "Jane Doe\n"
        "Skills: Active Directory, Microsoft 365, VPN, PowerShell.\n"
    )
    jd = (
        "Responsibilities:\n"
        "- Troubleshoot escalated Active Directory issues\n"
        "- Maintain VPN connectivity for client sites\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    ad = next(r for r in analysis.requirements if "Active Directory" in r.text)
    vpn = next(r for r in analysis.requirements if "VPN" in r.text)
    assert ad.status == UNVERIFIED
    assert vpn.status == UNVERIFIED
    assert "active directory" in analysis.unverified_terms
    assert "vpn" in analysis.unverified_terms
    assert analysis.estimated_score < 50


def test_genuinely_strong_match_scores_high():
    resume = (
        "Jane Doe\n"
        "IT Support Engineer at Acme GmbH (2021 - 2025)\n"
        "Administered Active Directory and Microsoft 365 for 400 users.\n"
        "Maintained VPN connectivity across 12 sites.\n"
        "Built PowerShell scripts that reduced onboarding time by 30%.\n"
        "Earned ITIL Foundation certification.\n"
        "Bachelor of Science in Computer Science.\n"
        "Supported Windows 10 and Windows 11 endpoints with 99.5% SLA compliance.\n"
    )
    jd = (
        "Requirements:\n"
        "- Active Directory administration\n"
        "- Microsoft 365 administration\n"
        "- VPN connectivity\n"
        "- PowerShell scripting\n"
        "- Windows administration\n"
        "- ITIL certification\n"
        "Experience:\n"
        "- 3+ years in an IT support role\n"
        "Qualifications:\n"
        "- Bachelor's degree in Computer Science\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)

    assert analysis.requirement_coverage >= 90
    assert analysis.evidence_confidence >= 90
    assert analysis.estimated_score >= 90
    assert not analysis.missing_terms


def test_empty_inputs_score_zero_without_inventing_requirements():
    empty = analyze_job_match("", "", reference_year=REFERENCE_YEAR)
    no_resume = analyze_job_match(
        "", JD, reference_year=REFERENCE_YEAR
    )

    assert empty.estimated_score == 0
    assert empty.requirements == []
    assert no_resume.estimated_score == 0
    assert all(r.status == MISSING for r in no_resume.requirements)


def test_skill_list_without_work_context_is_unverified():
    resume = "Jane Doe\nSkills: Active Directory, Microsoft 365, VPN.\n"
    jd = (
        "Requirements:\n"
        "- Active Directory administration\n"
        "- Microsoft 365 administration\n"
    )

    analysis = analyze_job_match(resume, jd, reference_year=REFERENCE_YEAR)
    by_term = {term.term: term for term in analysis.terms}

    assert by_term["active directory"].status == UNVERIFIED
    assert by_term["microsoft 365"].status == UNVERIFIED
    assert analysis.estimated_score < 70


def test_language_requirement_compares_explicit_levels():
    jd = "Requirements:\n- German B2\n"

    meets = analyze_job_match(
        "Jane Doe\nGerman B2.\n", jd, reference_year=REFERENCE_YEAR
    )
    below = analyze_job_match(
        "Jane Doe\nGerman B1.\n", jd, reference_year=REFERENCE_YEAR
    )
    unclear = analyze_job_match(
        "Jane Doe\nGerman.\n", jd, reference_year=REFERENCE_YEAR
    )

    assert meets.requirements[0].status == MATCHED
    assert below.requirements[0].status == MISSING
    assert "below" in below.requirements[0].detail.lower()
    assert unclear.requirements[0].status == UNVERIFIED
    assert "not explicitly stated" in unclear.requirements[0].detail.lower()


def test_language_requirement_without_job_level_is_unverified():
    analysis = analyze_job_match(
        "Jane Doe\nEnglish C1.\n",
        "Requirements:\n- English\n",
        reference_year=REFERENCE_YEAR,
    )

    assert analysis.requirements[0].status == UNVERIFIED
    assert "does not state a required level" in analysis.requirements[0].detail.lower()


def test_duplicate_requirement_lines_are_deduplicated():
    jd = (
        "Requirements:\n"
        "- Active Directory administration\n"
        "- Active Directory administration.\n"
    )

    analysis = analyze_job_match(
        "Jane Doe\nAdministered Active Directory.\n",
        jd,
        reference_year=REFERENCE_YEAR,
    )

    assert len(analysis.requirements) == 1
