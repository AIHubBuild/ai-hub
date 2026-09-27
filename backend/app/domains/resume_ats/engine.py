"""Deterministic ATS keyword and scoring engine.

Ported from the legacy ATS Resume Assistant (`ats_engine.py`), per
`docs/09_Migration_Analysis.md` §2.1.3 and §3.2 (KEEP): STOPWORDS,
TECH_KEYWORDS, extract_keywords, calculate_keyword_match,
clean_ats_score, generate_ats_analysis.

Deliberately excluded: Streamlit imports, the OpenAI client, LLM
generators, the pipeline orchestrator, and `clean_generated_text`
(LLM-output cleanup, ported with the AI workflow in a later slice).
"""

import re

from app.domains.resume_ats.schemas import AtsAnalysis, KeywordMatchResult

# ==========================================
# ATS STOPWORDS
# ==========================================

STOPWORDS = {
    "and", "the", "for", "with", "this", "that",
    "from", "your", "have", "will", "into",
    "their", "they", "them", "about", "over",
    "under", "more", "less", "very", "using",
    "used", "user", "users", "people", "hours",
    "jobs", "job", "work", "working", "role",
    "team", "within", "across", "ensure",
    "ensuring", "support", "good", "best",
    "including", "maintain", "maintaining",
    "today", "yesterday", "ago", "linkedin",
    "responses", "exclusive", "click", "apply",
    "candidate", "company", "professional",
    "location", "germany", "berlin", "hamburg",
    "mainz", "hybrid", "remote", "onsite",
    "fulltime", "parttime",
}

# ==========================================
# HIGH VALUE TECH KEYWORDS
# ==========================================

TECH_KEYWORDS = {
    "active directory",
    "microsoft 365",
    "entra id",
    "exchange online",
    "teams",
    "sharepoint",
    "onedrive",
    "vpn",
    "dns",
    "dhcp",
    "tcp/ip",
    "jira",
    "intune",
    "windows",
    "powershell",
    "itil",
    "ticketing",
    "incident management",
    "access control",
    "onboarding",
    "offboarding",
    "network troubleshooting",
    "service desk",
    "technical support",
    "endpoint management",
    "user provisioning",
    "identity management",
    "sla",
    "troubleshooting",
}


def extract_keywords(text: str) -> set[str]:
    """Tokenize `text` into a set of significant keywords.

    Behavior preserved from the legacy implementation: lowercasing,
    stripping characters outside ``[a-zA-Z0-9+/#-]``, dropping tokens
    shorter than 3 characters and stopwords.
    """
    text = text.lower()

    text = re.sub(r"[^a-zA-Z0-9+/#\-\s]", " ", text)

    words = text.split()

    cleaned = []

    for word in words:
        if len(word) < 3:
            continue

        if word in STOPWORDS:
            continue

        cleaned.append(word)

    return set(cleaned)


def calculate_keyword_match(
    resume_text: str, job_description: str
) -> KeywordMatchResult:
    """Score resume vs job description against the high-value keyword set.

    Preserved legacy semantics: a keyword is matched when it appears
    (case-insensitive substring) in both texts, missing when it appears
    only in the job description. The base ratio is capped into bands:
    >=75 → 88, >=50 → 72, else 48. Result lists are truncated to 25.

    Note (legacy quirk preserved): matching is substring-based, so
    e.g. "vpn" matches inside "VPNs". The legacy file also computed
    `extract_keywords` here without using the result; that dead
    computation is intentionally not reproduced.
    """
    matched = []
    missing = []

    for keyword in TECH_KEYWORDS:
        keyword_lower = keyword.lower()

        if (
            keyword_lower in resume_text.lower()
            and keyword_lower in job_description.lower()
        ):
            matched.append(keyword)

        elif keyword_lower in job_description.lower():
            missing.append(keyword)

    base_score = int(
        (len(matched) / max(len(matched) + len(missing), 1)) * 100
    )

    if base_score >= 75:
        score = min(base_score, 88)
    elif base_score >= 50:
        score = min(base_score, 72)
    else:
        score = min(base_score, 48)

    return KeywordMatchResult(
        score=score,
        matched=matched[:25],
        missing=missing[:25],
    )


def clean_ats_score(score_text: object) -> int:
    """Extract the digits from a score string into an integer.

    Preserved legacy semantics — including the quirk that multiple
    digit runs are concatenated (e.g. "72/100" -> 72100) and that any
    failure (or digit-free input) yields 0.
    """
    try:
        digits = "".join(filter(str.isdigit, str(score_text)))
        return int(digits)
    except ValueError:
        return 0


def generate_ats_analysis(keyword_results: KeywordMatchResult) -> AtsAnalysis:
    """Build the deterministic analysis fields from keyword results.

    Preserved legacy shape: the score is repeated as the original and
    optimized score (optimization is an AI step in a later slice).
    """
    return AtsAnalysis(
        original_ats_score=str(keyword_results.score),
        optimized_ats_score=str(keyword_results.score),
        matching_keywords=keyword_results.matched,
        missing_keywords=keyword_results.missing,
    )


def run_deterministic_analysis(
    resume_text: str, job_description: str
) -> AtsAnalysis:
    """Run the deterministic half of the ATS analysis.

    Composes keyword matching and analysis shaping — mirroring the
    first step of the legacy pipeline. This is the single entry point
    the future LangGraph workflow calls before the AI nodes run.
    """
    keyword_results = calculate_keyword_match(resume_text, job_description)
    return generate_ats_analysis(keyword_results)
