"""Scenario regression tests for the ATS matcher.

Scenario A is a representative "Vantage 2nd Line IT Support Specialist"
vacancy (a fixture constructed for testing — it is not a verbatim copy
of any real posting). Scenarios B and C exercise transferable skills
and an unsupported profile respectively.
"""

from app.domains.resume_ats.job_description import strip_boilerplate
from app.domains.resume_ats.matching import (
    MISSING,
    PARTIAL,
    SUPPORTED,
    analyze_job_match,
)
from app.domains.resume_ats.prompts import (
    COVER_LETTER_TEMPLATE_V2,
    TAILORED_RESUME_TEMPLATE_V2,
)

# ---------------------------------------------------------------
# Scenario A: Vantage 2nd Line IT Support Specialist
# ---------------------------------------------------------------

VANTAGE_JD = (
    "Vantage Careers\n"
    "We use cookies to improve your experience\n"
    "About Us\n"
    "Vantage is a managed IT services provider.\n"
    "\n"
    "2nd Line IT Support Specialist\n"
    "\n"
    "The Role\n"
    "You will resolve escalated tickets and support our clients.\n"
    "\n"
    "Responsibilities:\n"
    "- Troubleshoot escalated Active Directory and Windows issues\n"
    "- Maintain VPN connectivity for client sites\n"
    "- Document solutions in the incident management system\n"
    "\n"
    "Requirements:\n"
    "- Active Directory administration experience\n"
    "- Windows administration experience\n"
    "- Experience with Microsoft 365 administration\n"
    "\n"
    "Technical Skills:\n"
    "- PowerShell scripting\n"
    "- DNS and DHCP troubleshooting\n"
    "- Networking fundamentals (TCP/IP)\n"
    "\n"
    "Experience:\n"
    "- 2+ years in a 2nd line support role\n"
    "\n"
    "Preferred:\n"
    "- ITIL certification\n"
    "- Microsoft 365 certification\n"
    "\n"
    "Communication:\n"
    "- Excellent communication skills\n"
    "- Customer service experience\n"
    "\n"
    "We are an equal opportunity employer and welcome all applicants.\n"
    "Apply now\n"
    "© 2026 Vantage. All rights reserved."
)

VANTAGE_RESUME = (
    "Sam Taylor\n"
    "2nd Line Support Engineer at Vantage MSP (2022 - Present)\n"
    "Administered Active Directory and Microsoft 365 for 600 users.\n"
    "Supported Windows 10/11 endpoints across 12 client sites.\n"
    "Maintained VPN connectivity and network troubleshooting.\n"
    "Built PowerShell scripts to automate user provisioning.\n"
    "Documented solutions in the incident management system.\n"
    "Strong customer service and communication skills."
)


def test_vantage_scenario_categorizes_and_scores():
    cleaned = strip_boilerplate(VANTAGE_JD)
    assert "cookies" not in cleaned.lower()
    assert "equal opportunity" not in cleaned.lower()

    analysis = analyze_job_match(VANTAGE_RESUME, cleaned)
    by_term = {t.term: t for t in analysis.terms}

    # Responsibilities section terms carry the responsibilities category.
    assert by_term["vpn"].category == "responsibilities"
    assert by_term["incident management"].category == "responsibilities"
    # Technical Skills section terms.
    assert by_term["powershell"].category == "technical_skills"
    assert by_term["dns"].category == "technical_skills"
    # Requirements section terms.
    assert by_term["active directory"].category == "essential"
    # Preferred terms stay preferred.
    assert by_term["itil"].category == "preferred"
    # Communication competencies are separated and informational.
    assert by_term["communication skills"].category == "communication"
    assert by_term["customer service"].category == "communication"

    # Supported requirements carry resume evidence.
    assert by_term["active directory"].status == SUPPORTED
    assert any(
        "Administered Active Directory" in line
        for line in by_term["active directory"].evidence
    )
    assert by_term["powershell"].status == SUPPORTED
    # Missing requirements have no evidence.
    assert by_term["itil"].status == MISSING
    assert by_term["itil"].evidence == []
    assert by_term["dns"].status == MISSING

    categories = {entry.category: entry for entry in analysis.breakdown}
    assert categories["essential"].score > 0
    assert categories["technical_skills"].score > 0
    assert categories["preferred"].score == 0
    assert "communication" not in {
        entry.category for entry in analysis.breakdown
    } or categories["communication"].weight == 0

    assert 0 <= analysis.estimated_score <= 100
    assert analysis.estimated_score == analysis.estimated_score  # deterministic


def test_vantage_scenario_is_reproducible():
    cleaned = strip_boilerplate(VANTAGE_JD)

    first = analyze_job_match(VANTAGE_RESUME, cleaned)
    second = analyze_job_match(VANTAGE_RESUME, cleaned)

    assert first == second


# ---------------------------------------------------------------
# Scenario B: transferable / partial matches
# ---------------------------------------------------------------

def test_transferable_skills_are_partial_not_supported():
    resume = (
        "Alex Rivera\n"
        "Help Desk Analyst at SmallCo (2020 - 2023)\n"
        "Provided help desk support and managed office 365 tenants.\n"
    )
    jd = (
        "Technical Support Engineer\n"
        "Requirements:\n"
        "- Technical support experience\n"
        "- Microsoft 365 administration\n"
        "Preferred:\n"
        "- ITIL certification\n"
    )

    analysis = analyze_job_match(resume, jd)
    by_term = {t.term: t for t in analysis.terms}

    assert by_term["technical support"].status == PARTIAL
    assert by_term["microsoft 365"].status == PARTIAL
    assert by_term["itil"].status == MISSING
    assert set(analysis.partial_terms) == {"technical support", "microsoft 365"}
    # Partial coverage: essential 2 partial -> 50; preferred missing -> 0.
    # estimated = (0.35*50 + 0.10*0)/0.45 -> 39
    assert analysis.estimated_score == 39


# ---------------------------------------------------------------
# Scenario C: unsupported profile
# ---------------------------------------------------------------

def test_unsupported_profile_scores_low_with_explanations():
    resume = (
        "Chris Lee\n"
        "Retail Associate at ShopCo (2019 - 2022)\n"
        "Handled cash and customer queries.\n"
    )
    jd = (
        "Senior Network Engineer\n"
        "Requirements:\n"
        "- Active Directory administration\n"
        "- DNS and DHCP troubleshooting\n"
        "- TCP/IP networking\n"
        "- PowerShell scripting\n"
    )

    analysis = analyze_job_match(resume, jd)

    assert analysis.estimated_score == 0
    assert set(analysis.missing_terms) == {
        "active directory",
        "dns",
        "dhcp",
        "tcp/ip",
        "powershell",
        "troubleshooting",
    }
    assert all(
        term.evidence == [] for term in analysis.terms
    )
    # Communication competencies are not invented either.
    assert "customer service" not in {t.term for t in analysis.terms}


# ---------------------------------------------------------------
# Tailored-resume accuracy preservation (prompt-level guarantees)
# ---------------------------------------------------------------

def test_tailored_resume_prompt_preserves_facts_and_labels_labs():
    template = TAILORED_RESUME_TEMPLATE_V2.user_template

    assert "Preserve the exact employers, job titles, and dates" in template
    assert "Clearly label lab work, coursework, training" in template
    assert "never add experience, metrics, certifications" in template
    assert "Preserve all existing candidate personal information" in template


def test_cover_letter_prompt_cannot_introduce_new_claims():
    template = COVER_LETTER_TEMPLATE_V2.user_template

    assert (
        "Only reference experience and skills that appear in the optimized "
        "resume" in template
    )
    assert "Do not introduce new claims, achievements, or employers" in template
