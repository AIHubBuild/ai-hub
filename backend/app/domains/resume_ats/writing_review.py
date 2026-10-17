"""Deterministic writing-quality review.

A lightweight, dependency-free review stage that runs after generation
and before results are returned or documents are exported. It flags
issues in the tailored resume and cover letter. The workflow uses these
findings to trigger a targeted revision pass; the review itself never
rewrites text:

- generic AI-style phrases,
- any em dash,
- repetitive sentence openings,
- missing applicant name (consistency with the source resume),
- cross-document inconsistencies it can detect deterministically.

The review never contacts the model: flagged wording is either already
covered by the latest prompt rules or surfaced to the user for review.
"""

import re
from dataclasses import dataclass, field

from app.ai_core.writing_style import contains_em_dash

# Generic AI-style phrases (case-insensitive; examples from the writing
# rules, not an exhaustive blacklist).
GENERIC_PHRASES = [
    "confident in my ability to contribute",
    "passionate about leveraging my skills",
    "excited to embark on this journey",
    "resonates with me",
    "valuable addition to your team",
    "proven track record of success",
    "results-driven professional",
    "self-motivated team player",
    "goes above and beyond",
    "think outside the box",
    "i am writing to apply",
    "i would be a great fit",
    "i believe i would be",
    "hit the ground running",
    "dynamic and results-driven",
    "in today's fast-paced",
    "i am thrilled to apply",
    "i am excited to apply",
    "aligns closely with my experience",
    "solid foundation in",
    "leverage my experience",
    "dynamic professional",
    "i would be an asset",
    "strong background in",
    "passionate about",
]

# Transitions that become repetitive when they open many sentences.
REPEATED_TRANSITIONS = [
    "furthermore",
    "moreover",
    "additionally",
    "in addition",
]

NAME_REGEX = re.compile(r"\b[A-Z][a-z]{2,}\b")


def _count(pattern: str, text: str) -> int:
    return len(re.findall(re.escape(pattern), text, flags=re.IGNORECASE))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _opening_words(sentence: str) -> str:
    words = sentence.split()
    if len(words) < 2:
        return sentence.lower()
    return f"{words[0].lower()} {words[1].lower()}"


_NON_NAME_WORDS = {
    "provided",
    "managed",
    "supported",
    "worked",
    "experienced",
    "responsible",
    "administered",
    "maintained",
    "built",
    "led",
}


def applicant_name(resume_source: str) -> str | None:
    """Return the applicant's full name when the first line looks like one."""
    for line in resume_source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        words = stripped.split()
        if not (2 <= len(words) <= 4):
            return None
        if any(ch in stripped for ch in ".@|:,"):
            return None
        if any(word.lower().strip("()") in _NON_NAME_WORDS for word in words):
            return None
        if not all(
            word[:1].isupper() and word.replace("-", "").replace("'", "").isalpha()
            for word in words
        ):
            return None
        return stripped
    return None


def _applicant_first_word(resume_source: str) -> str | None:
    name = applicant_name(resume_source)
    return name.split()[0] if name else None


def _check_generic_phrases(doc_name: str, text: str, issues: list) -> None:
    for phrase in GENERIC_PHRASES:
        count = _count(phrase, text)
        if count:
            issues.append(
                WritingIssue(
                    code="generic_phrase",
                    message=(
                        f"{doc_name}: generic AI-style phrase "
                        f"'{phrase}' appears {count} time(s)."
                    ),
                )
            )


def _check_em_dashes(doc_name: str, text: str, issues: list) -> None:
    if contains_em_dash(text):
        issues.append(
            WritingIssue(
                code="em_dash_overuse",
                message=(
                    f"{doc_name}: em dash found; use commas, full stops, "
                    f"colons, or parentheses instead."
                ),
            )
        )


METRIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*\+?\s*(?:%|(?:percent|users?|clients?|sites?|"
    r"tickets?|servers?|years?|months?)\b)",
    flags=re.IGNORECASE,
)


def _normalize_metric(value: str) -> str:
    normalized = value.lower().replace("percent", "%")
    return re.sub(r"\s+", "", normalized)


def _metrics(text: str) -> set[str]:
    return {_normalize_metric(match.group(0)) for match in METRIC_PATTERN.finditer(text)}


UNSUPPORTED_CLAIM_TERMS = [
    "sla",
    "service level agreement",
    "incident management",
    "incident resolution",
    "change control",
    "root cause",
    "wireshark",
    "traceroute",
    "ping",
    "nmap",
    "itil",
    "patch management",
    "endpoint security",
    "escalated support tickets",
    "escalated tickets",
    "second-line support",
    "2nd line support",
]

OUTCOME_GROUPS = {
    "reduced": [
        "reduce", "reduced", "reducing", "reduction",
        "cut", "cutting", "lowered", "lowering", "decreased", "decreasing",
    ],
    "improved": [
        "improve", "improved", "improving", "improvement",
        "enhanced", "enhancing", "accelerated", "accelerating",
        "faster", "streamlined", "streamlining",
    ],
    "downtime": ["downtime"],
    "efficiency": ["efficiency", "efficient", "efficiently"],
    "response time": ["response time", "response times"],
    "saved": ["save", "saved", "saving"],
}

RELATIVE_TIME_TERMS = ["this year", "last year"]

_SECTION_SOURCE_PATTERNS = {
    "projects": r"\bproject",
    "certifications": r"\bcertif",
    "education": r"\b(?:education|degree|university|bsc|msc|bachelor|master)\b",
}


def _has_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE) is not None


def _source_supports_claim(term: str, resume_source: str) -> bool:
    if term == "sla" and re.search(
        r"\bservice level agreement\b", resume_source, re.IGNORECASE
    ):
        return True
    if term == "service level agreement" and _has_term(resume_source, "sla"):
        return True
    return _has_term(resume_source, term)


def _check_unsupported_claims(
    doc_name: str,
    text: str,
    resume_source: str,
    issues: list,
) -> None:
    for term in UNSUPPORTED_CLAIM_TERMS:
        if _has_term(text, term) and not _source_supports_claim(term, resume_source):
            issues.append(
                WritingIssue(
                    code="unsupported_claim",
                    message=(
                        f"{doc_name}: claim '{term}' is not supported by the "
                        f"source resume; remove it or replace it with verified "
                        f"evidence."
                    ),
                )
            )


def _check_unsupported_sections(
    doc_name: str,
    text: str,
    resume_source: str,
    issues: list,
) -> None:
    if doc_name != "Tailored resume":
        return
    plain = re.sub(r"[*#]+", "", text)
    for heading, source_pattern in _SECTION_SOURCE_PATTERNS.items():
        section_present = (
            re.search(
                rf"^\s*{heading}\s*:?\s*$",
                plain,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            is not None
        )
        source_supports = (
            re.search(source_pattern, resume_source, flags=re.IGNORECASE)
            is not None
        )
        if section_present and not source_supports:
            issues.append(
                WritingIssue(
                    code="unsupported_section",
                    message=(
                        f"{doc_name}: '{heading}' section is not supported by "
                        f"the source resume; remove it or use only existing "
                        f"content."
                    ),
                )
            )


def _check_unsupported_outcomes(
    doc_name: str,
    text: str,
    resume_source: str,
    issues: list,
) -> None:
    for label, variants in OUTCOME_GROUPS.items():
        generated = any(_has_term(text, variant) for variant in variants)
        supported = any(_has_term(resume_source, variant) for variant in variants)
        if generated and not supported:
            issues.append(
                WritingIssue(
                    code="unsupported_outcome",
                    message=(
                        f"{doc_name}: outcome '{label}' is not supported by "
                        f"the source resume; remove it or use only a verified "
                        f"result."
                    ),
                )
            )


def _check_relative_time_claims(
    doc_name: str,
    text: str,
    resume_source: str,
    issues: list,
) -> None:
    for term in RELATIVE_TIME_TERMS:
        if _has_term(text, term) and not _has_term(resume_source, term):
            issues.append(
                WritingIssue(
                    code="unsupported_time_reference",
                    message=(
                        f"{doc_name}: relative time reference '{term}' is not "
                        f"supported by the source resume; use the actual date "
                        f"or remove it."
                    ),
                )
            )


def _check_unsupported_metrics(
    doc_name: str,
    text: str,
    resume_source: str,
    issues: list,
) -> None:
    supported = _metrics(resume_source)
    for metric in sorted(_metrics(text)):
        if metric not in supported:
            issues.append(
                WritingIssue(
                    code="unsupported_metric",
                    message=(
                        f"{doc_name}: metric '{metric}' does not appear in "
                        f"the source resume; remove it or use only verified "
                        f"evidence."
                    ),
                )
            )


PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:name|email|phone|address|company|linkedin|github)\]|"
    r"\b(?:TBD|TODO|Lorem ipsum)\b",
    flags=re.IGNORECASE,
)


def _check_placeholders(doc_name: str, text: str, issues: list) -> None:
    match = PLACEHOLDER_PATTERN.search(text)
    if match:
        issues.append(
            WritingIssue(
                code="placeholder_text",
                message=(
                    f"{doc_name}: placeholder text '{match.group(0)}' found; "
                    f"remove it or use verified information from the source."
                ),
            )
        )


def _check_repeated_openers(doc_name: str, text: str, issues: list) -> None:
    openers = [_opening_words(s) for s in _sentences(text)]
    index = 0
    while index < len(openers):
        end = index
        while end < len(openers) and openers[end] == openers[index]:
            end += 1
        run_length = end - index
        first_word = openers[index].split()[0].strip(",;:")
        if run_length >= 3 and first_word not in REPEATED_TRANSITIONS:
            issues.append(
                WritingIssue(
                    code="repetitive_openings",
                    message=(
                        f"{doc_name}: {run_length} consecutive sentences "
                        f"start with '{openers[index]}'."
                    ),
                )
            )
        index = end


def _check_name_preserved(
    resume_source: str, tailored_resume: str, cover_letter: str, issues: list
) -> None:
    name = _applicant_first_word(resume_source)
    if name is None:
        return
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    if tailored_resume and not pattern.search(tailored_resume):
        issues.append(
            WritingIssue(
                code="missing_name",
                message=(
                    f"Tailored resume does not mention the applicant's "
                    f"name '{name}' from the source resume."
                ),
            )
        )
    if cover_letter and not pattern.search(cover_letter):
        issues.append(
            WritingIssue(
                code="missing_name",
                message=(
                    f"Cover letter does not mention the applicant's name "
                    f"'{name}' from the source resume."
                ),
            )
        )


@dataclass
class WritingIssue:
    code: str
    message: str


@dataclass
class WritingReview:
    passed: bool
    issues: list[WritingIssue] = field(default_factory=list)


def review_writing(
    resume_source: str,
    tailored_resume: str | None,
    cover_letter: str | None,
) -> WritingReview:
    """Run the deterministic writing-quality checks.

    Returns a WritingReview; ``passed`` is True when no issues were
    detected. Unknown content is preserved, never replaced.
    """
    issues: list[WritingIssue] = []

    for doc_name, text in (
        ("Tailored resume", tailored_resume),
        ("Cover letter", cover_letter),
    ):
        if not text:
            continue
        _check_generic_phrases(doc_name, text, issues)
        _check_em_dashes(doc_name, text, issues)
        _check_placeholders(doc_name, text, issues)
        _check_unsupported_claims(doc_name, text, resume_source, issues)
        _check_unsupported_sections(doc_name, text, resume_source, issues)
        _check_unsupported_outcomes(doc_name, text, resume_source, issues)
        _check_relative_time_claims(doc_name, text, resume_source, issues)
        _check_unsupported_metrics(doc_name, text, resume_source, issues)
        _check_repeated_openers(doc_name, text, issues)

    if tailored_resume or cover_letter:
        _check_name_preserved(
            resume_source, tailored_resume or "", cover_letter or "", issues
        )

    return WritingReview(passed=not issues, issues=issues)
