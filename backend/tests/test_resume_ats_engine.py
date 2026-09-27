"""Tests for the deterministic ATS engine (domains/resume_ats/engine.py).

Expectations are hand-computed from the legacy `ats_engine.py` behavior
described in docs/09_Migration_Analysis.md §2.1.3, so the migrated
engine can be shown to behave consistently with the intended legacy
logic.
"""

import pytest

from app.domains.resume_ats.engine import (
    TECH_KEYWORDS,
    calculate_keyword_match,
    clean_ats_score,
    extract_keywords,
    generate_ats_analysis,
)

RESUME = (
    "IT Support Engineer with hands-on experience in Active Directory, "
    "Microsoft 365 administration, VPN configuration, DNS troubleshooting, "
    "and daily ticket handling."
)

JOB_DESCRIPTION = (
    "We are looking for a Service Desk Engineer with Active Directory, "
    "Microsoft 365, VPN, DNS, DHCP, PowerShell, and Intune experience."
)


def test_extract_keywords_lowercases_and_drops_stopwords():
    keywords = extract_keywords("Active Directory and VPN support")

    assert keywords == {"active", "directory", "vpn"}


def test_extract_keywords_keeps_special_token_characters():
    keywords = extract_keywords("tcp/ip, dns! c++")

    assert keywords == {"tcp/ip", "dns", "c++"}


def test_extract_keywords_drops_short_tokens():
    keywords = extract_keywords("go to the IT job")

    assert keywords == set()  # "go", "to", "it" < 3 chars; "the", "job" stopwords


def test_keyword_match_scores_matched_and_missing():
    result = calculate_keyword_match(RESUME, JOB_DESCRIPTION)

    # In JD: active directory, microsoft 365, vpn, dns, dhcp, powershell,
    # intune, service desk (8). In resume too: the first four.
    assert set(result.matched) == {
        "active directory",
        "microsoft 365",
        "vpn",
        "dns",
    }
    assert set(result.missing) == {"dhcp", "powershell", "intune", "service desk"}
    # base = int(4 / 8 * 100) = 50 -> >=50 band -> min(50, 72) = 50
    assert result.score == 50


def test_keyword_match_ignores_keywords_present_only_in_resume():
    resume = "Every day I do Windows administration and PowerShell scripting."
    job_description = "Looking for helpdesk staff."

    result = calculate_keyword_match(resume, job_description)

    assert result.matched == []
    assert result.missing == []
    assert result.score == 0


def test_keyword_match_high_score_is_capped_at_88():
    resume = " ".join(TECH_KEYWORDS)
    job_description = " ".join(TECH_KEYWORDS) + " extra requirement"

    result = calculate_keyword_match(resume, job_description)

    assert result.score == 88


def test_keyword_match_low_score_is_capped_at_48():
    job_description = " ".join(TECH_KEYWORDS)
    resume = "Active Directory only."

    result = calculate_keyword_match(resume, job_description)

    # base = int(1 / 29 * 100) = 3 -> <50 band -> min(3, 48) = 3
    assert result.score == 3
    assert result.matched == ["active directory"]


def test_keyword_match_empty_job_description_scores_zero():
    result = calculate_keyword_match("anything at all", "")

    assert result.score == 0
    assert result.matched == []
    assert result.missing == []


def test_keyword_match_truncates_lists_at_25():
    job_description = " ".join(TECH_KEYWORDS)
    resume = "no relevant keywords here"

    result = calculate_keyword_match(resume, job_description)

    assert len(result.missing) == 25
    assert len(result.matched) == 0


def test_keyword_match_substring_quirk_is_preserved():
    # Legacy matching is substring-based: "vpn" matches inside "VPNs".
    resume = "I maintain VPNs and DNS records."
    job_description = "VPN and DNS experience required."

    result = calculate_keyword_match(resume, job_description)

    assert "vpn" in result.matched
    assert "dns" in result.matched


def test_keyword_match_is_case_insensitive():
    resume = "POWERSHELL scripting."
    job_description = "powershell required."

    result = calculate_keyword_match(resume, job_description)

    assert "powershell" in result.matched


def test_clean_ats_score_extracts_digits():
    assert clean_ats_score("88") == 88
    assert clean_ats_score("Score: 72") == 72


def test_clean_ats_score_concatenates_digit_runs_legacy_quirk():
    assert clean_ats_score("72/100") == 72100


def test_clean_ats_score_returns_zero_when_no_digits():
    assert clean_ats_score("no digits here") == 0
    assert clean_ats_score(None) == 0


def test_generate_ats_analysis_repeats_score_and_lists_keywords():
    from app.domains.resume_ats.schemas import KeywordMatchResult

    keyword_results = KeywordMatchResult(
        score=57, matched=["vpn"], missing=["dhcp"]
    )

    analysis = generate_ats_analysis(keyword_results)

    assert analysis.original_ats_score == "57"
    assert analysis.optimized_ats_score == "57"
    assert analysis.matching_keywords == ["vpn"]
    assert analysis.missing_keywords == ["dhcp"]


def test_engine_has_no_streamlit_or_openai_imports():
    import ast
    import inspect

    import app.domains.resume_ats.engine as engine_module

    tree = ast.parse(inspect.getsource(engine_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    assert not ({"streamlit", "openai"} & imported_modules)
