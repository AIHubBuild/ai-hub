"""Tests for the evidence-based job-match analyzer (matching.py)."""

from app.domains.resume_ats.matching import (
    MISSING,
    PARTIAL,
    SUPPORTED,
    SCORE_LABEL,
    analyze_job_match,
)

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
    return analyze_job_match(resume, jd)


def test_score_is_reproducible():
    first = analyze()
    second = analyze()

    assert first == second
    assert first.estimated_score == second.estimated_score


def test_score_is_labeled_an_estimate():
    assert analyze().score_label == SCORE_LABEL
    assert "estimated" in SCORE_LABEL.lower()


def test_supported_partial_and_missing_are_distinguished():
    analysis = analyze()

    assert "active directory" in analysis.supported_terms
    assert "microsoft 365" in analysis.supported_terms
    assert "powershell" in analysis.supported_terms
    assert "intune" in analysis.missing_terms
    assert "jira" in analysis.missing_terms
    # ITIL appears only in the preferred section and is absent from the
    # resume -> missing; DNS is absent too. Partial matches are covered
    # by the synonym test below.


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

    analysis = analyze_job_match(resume, jd)

    assert "technical support" in analysis.partial_terms
    assert "microsoft 365" in analysis.partial_terms
    for term in ("technical support", "microsoft 365"):
        entry = analysis.evidence_map[term]
        assert entry["status"] == PARTIAL
        assert entry["evidence"]


def test_evidence_lists_resume_lines_not_keywords_alone():
    analysis = analyze()

    entry = analysis.evidence_map["active directory"]
    assert entry["status"] == SUPPORTED
    assert any("Administered Active Directory" in line for line in entry["evidence"])


def test_missing_terms_have_no_evidence():
    analysis = analyze()

    entry = analysis.evidence_map["jira"]
    assert entry["status"] == MISSING
    assert entry["evidence"] == []


def test_preferred_terms_are_categorized_separately():
    analysis = analyze()

    assert analysis.evidence_map["itil"]["category"] == "preferred"
    assert analysis.evidence_map["active directory"]["category"] == "essential"


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
    analysis = analyze_job_match(resume, jd)

    # essential: 1 supported, 1 missing -> 50 (weight 0.35)
    # preferred: 1 missing -> 0 (weight 0.10)
    # estimated = (0.35*50 + 0.10*0) / 0.45 = 38.9 -> 39
    assert analysis.estimated_score == 39


def test_no_recognizable_requirements_yields_zero_and_no_crash():
    analysis = analyze_job_match(RESUME, "We are hiring a nice person.")

    assert analysis.estimated_score == 0
    assert analysis.terms == []


def test_breakdown_is_reported():
    analysis = analyze()

    essential = next(e for e in analysis.breakdown if e.category == "essential")
    assert essential.total == 5
    assert essential.supported + essential.partial + essential.missing == 5
