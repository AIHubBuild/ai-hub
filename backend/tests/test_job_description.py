"""Tests for job-description preprocessing (boilerplate + sections)."""

from app.domains.resume_ats.job_description import (
    describe_warning,
    extract_sections,
    strip_boilerplate,
)

SAMPLE_JD = (
    "Accept all cookies\n"
    "We use cookies to improve your experience. Cookie policy\n"
    "About Us\n"
    "Our Company\n"
    "Job Alerts\n"
    "Subscribe to job alerts\n"
    "Senior IT Support Engineer\n"
    "\n"
    "Requirements:\n"
    "- Active Directory administration experience\n"
    "- Microsoft 365 administration\n"
    "- PowerShell scripting\n"
    "\n"
    "Preferred:\n"
    "- ITIL certification\n"
    "- Intune experience\n"
    "\n"
    "Responsibilities:\n"
    "- Maintain VPN infrastructure\n"
    "- Handle incident management\n"
    "\n"
    "We are an equal opportunity employer and welcome all applicants.\n"
    "Apply now\n"
    "Share this job\n"
    "© 2026 Example Corp. All rights reserved."
)


def test_boilerplate_lines_are_removed():
    cleaned = strip_boilerplate(SAMPLE_JD)

    assert "cookies" not in cleaned.lower()
    assert "apply now" not in cleaned.lower()
    assert "share this job" not in cleaned.lower()
    assert "equal opportunity" not in cleaned.lower()
    assert "©" not in cleaned
    assert "Job Alerts" not in cleaned
    assert "Subscribe" not in cleaned


def test_genuine_requirements_survive_cleaning():
    cleaned = strip_boilerplate(SAMPLE_JD)

    assert "Active Directory" in cleaned
    assert "Microsoft 365" in cleaned
    assert "PowerShell" in cleaned
    assert "ITIL" in cleaned
    assert "Intune" in cleaned
    assert "VPN infrastructure" in cleaned
    assert "incident management" in cleaned


def test_unfamiliar_wording_is_not_discarded():
    jd = "Looking for someone with mainframe Z/OS experience and COBOL skills."
    cleaned = strip_boilerplate(jd)

    assert "Z/OS" in cleaned
    assert "COBOL" in cleaned


def test_short_or_boilerplate_description_warns():
    boilerplate_only = "Apply now\nWe use cookies\nPrivacy policy"
    cleaned = strip_boilerplate(boilerplate_only)

    assert describe_warning(boilerplate_only, cleaned) is not None


def test_healthy_description_does_not_warn():
    cleaned = strip_boilerplate(SAMPLE_JD)

    assert describe_warning(SAMPLE_JD, cleaned) is None


def test_sections_are_extracted():
    sections = extract_sections(strip_boilerplate(SAMPLE_JD))

    essential = "\n".join(sections["essential"])
    preferred = "\n".join(sections["preferred"])
    responsibilities = "\n".join(sections["responsibilities"])

    assert "Active Directory" in essential
    assert "PowerShell" in essential
    assert "ITIL" in preferred
    assert "Intune" in preferred
    assert "VPN infrastructure" in responsibilities


def test_without_headings_everything_is_essential():
    jd = "We need Docker and Kubernetes experience."
    sections = extract_sections(jd)

    assert "We need Docker and Kubernetes experience." in sections["essential"]
    assert sections["preferred"] == []
