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
    "collaborate with senior",
    "collaborated with senior",
    "collaborate closely",
    "collaborated closely",
    "joint problem-solving",
    "team meetings",
    "user satisfaction",
    "enhance team knowledge",
]

OUTCOME_GROUPS = {
    "reduced": [
        "reduce", "reduced", "reducing", "reduction",
        "cut", "cutting", "lowered", "lowering", "decreased", "decreasing",
    ],
    "improved": [
        "improve", "improved", "improving", "improvement",
        "enhance", "enhanced", "enhancing", "accelerated",
        "accelerating", "faster", "streamline", "streamlined",
        "streamlining",
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


_PURPOSE_OUTCOME_RE = re.compile(
    r"(?:\s*[,;]\s*|\s+)to\s+(?:improve|reduce|increase|save|cut|"
    r"decrease|boost|optimize|optimise|streamline|enhance|accelerate)\b"
    r"[^.!?\n]*",
    flags=re.IGNORECASE,
)

_OUTCOME_ADVERB_RE = re.compile(
    r"\s+efficiently\b", flags=re.IGNORECASE
)

_TRAILING_COMPARATIVE_RE = re.compile(
    r"\s+(?:more|less|better|most)\b(?=[.!?]|$)", flags=re.IGNORECASE
)

_OUTCOME_RELATIVE_CLAUSE_RE = re.compile(
    r",?\s+(?:which|that)\s+(?:has\s+|have\s+|had\s+)?"
    r"(?:helped|helps|help|supported|supports|support|allowed|allows|"
    r"allow|enabled|enables|enable|reduced|reduces|reduce|improved|"
    r"improves|improve|increased|increases|increase|saved|saves|save|"
    r"cut|cuts|boosted|boosts|boost|streamlined|streamlines|"
    r"streamline|enhanced|enhances|enhance)\b[^.!?\n]*",
    flags=re.IGNORECASE,
)

_OUTCOME_PARTICIPLE_CLAUSE_RE = re.compile(
    r",\s+(?:helping|supporting|enabling|allowing|reducing|improving|"
    r"increasing|saving|cutting|boosting|streamlining|enhancing)\b"
    r"[^.!?\n]*",
    flags=re.IGNORECASE,
)

_DANGLING_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of",
    "on", "or", "that", "the", "to", "which", "with", "more", "less",
    "better", "most",
}


def _looks_incomplete(line: str) -> bool:
    words = re.findall(r"[A-Za-z]+", line)
    return bool(words) and words[-1].lower() in _DANGLING_WORDS


def _line_has_unsupported_outcome(line: str, resume_source: str) -> bool:
    for variants in OUTCOME_GROUPS.values():
        generated = any(_has_term(line, variant) for variant in variants)
        supported = any(_has_term(resume_source, variant) for variant in variants)
        if generated and not supported:
            return True
    return False


def repair_unsupported_outcomes(
    text: str, resume_source: str, *, drop_unrepairable: bool = True
) -> tuple[str, bool]:
    """Remove unsupported outcome clauses that a revision pass left behind.

    This is a conservative deterministic fallback, used only after the
    model has had a chance to revise. A trailing purpose clause such as
    "to improve support efficiency" is removed when the source resume
    does not state that outcome. If the unsupported outcome is the main
    claim of a line, the line is dropped rather than rewritten.
    Returns the repaired text and whether anything changed.
    """
    if not text:
        return text, False

    trailing_newline = text.endswith("\n")
    kept: list[str] = []
    changed = False
    for line in text.splitlines():
        cleaned_line = _TRAILING_COMPARATIVE_RE.sub("", line)
        if cleaned_line != line:
            line = cleaned_line.rstrip(" ,;")
            changed = True
        if not _line_has_unsupported_outcome(line, resume_source):
            kept.append(line)
            continue
        candidate = _OUTCOME_ADVERB_RE.sub("", line).rstrip(" ,;")
        candidate = _TRAILING_COMPARATIVE_RE.sub("", candidate).rstrip(" ,;")
        candidate = _PURPOSE_OUTCOME_RE.sub("", candidate).rstrip(" ,;")
        candidate = _OUTCOME_RELATIVE_CLAUSE_RE.sub("", candidate).rstrip(" ,;")
        candidate = _OUTCOME_PARTICIPLE_CLAUSE_RE.sub("", candidate).rstrip(" ,;")
        if (
            candidate != line
            and not _line_has_unsupported_outcome(candidate, resume_source)
            and not _looks_incomplete(candidate)
        ):
            kept.append(candidate)
            changed = True
        elif drop_unrepairable:
            changed = True
        else:
            # Cover letters read as connected prose. Dropping a line can
            # leave an empty letter, so leave the claim for the model to
            # revise and surface the issue to the user if it remains.
            kept.append(line)
    repaired = "\n".join(kept)
    if trailing_newline and repaired:
        repaired += "\n"
    return repaired, changed


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


MARKDOWN_ARTIFACT_PATTERN = re.compile(
    r"\*\*|__|^#{1,6}\s|^\s*(?:---+|___+)\s*$",
    flags=re.MULTILINE,
)
COVER_LETTER_BULLET_PATTERN = re.compile(
    r"^\s*[-*•]\s+", flags=re.MULTILINE
)

RESUME_SECTION_HEADINGS = {
    "summary",
    "professional summary",
    "profile",
    "skills",
    "technical skills",
    "core competencies",
    "experience",
    "work experience",
    "professional experience",
    "projects",
    "education",
    "certifications",
    "certificates",
    "languages",
}


MIN_COVER_LETTER_WORDS = 280
MAX_COVER_LETTER_WORDS = 650
_GREETING_RE = re.compile(
    r"^\s*(?:Dear\b|Hello\b|Hallo\b|Sehr geehrte)",
    flags=re.IGNORECASE | re.MULTILINE,
)
_CLOSING_RE = re.compile(
    r"^\s*(?:Sincerely|Kind regards|Best regards|Yours sincerely|"
    r"Yours faithfully|Mit freundlichen Gr(?:ü|ue)(?:ß|ss)en|"
    r"Freundliche Gr(?:ü|ue)(?:ß|ss)e)\b",
    flags=re.IGNORECASE | re.MULTILINE,
)
_EMPLOYER_RE = re.compile(
    r"\b(?:[A-Z][\w&.\-]+(?:\s+[A-Z][\w&.\-]+){0,3})\s+"
    r"(?:GmbH|AG|Inc\.?|Ltd\.?|LLC|SE|KG|UG|Corp\.?)\b"
)
_DATE_RANGE_RE = re.compile(
    r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current)\b",
    flags=re.IGNORECASE,
)


def _normalize_entity(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _check_cover_letter_structure(
    text: str, issues: list
) -> None:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9']+", text)
    if len(words) < MIN_COVER_LETTER_WORDS:
        issues.append(
            WritingIssue(
                code="cover_letter_too_short",
                message=(
                    f"Cover letter: only {len(words)} words; write a "
                    "detailed letter of roughly 350 to 450 words using "
                    "verified evidence."
                ),
            )
        )
    elif len(words) > MAX_COVER_LETTER_WORDS:
        issues.append(
            WritingIssue(
                code="cover_letter_too_long",
                message=(
                    f"Cover letter: {len(words)} words is excessively long; "
                    "select the strongest evidence and tighten the letter."
                ),
            )
        )
    if not _GREETING_RE.search(text):
        issues.append(
            WritingIssue(
                code="missing_greeting",
                message=(
                    "Cover letter: no professional greeting found; address "
                    "the hiring team or recruiter."
                ),
            )
        )
    if not _CLOSING_RE.search(text):
        issues.append(
            WritingIssue(
                code="missing_closing",
                message=(
                    "Cover letter: no professional closing found; end with "
                    "a conventional sign-off and the applicant's name."
                ),
            )
        )


_LEADING_SENTENCE_WORDS_RE = re.compile(
    r"^(?:At|The|This|That|With|For|From|In|On|By|And|But)\s+",
    flags=re.IGNORECASE,
)


def _clean_employer_name(entity: str) -> str:
    return _LEADING_SENTENCE_WORDS_RE.sub("", entity).strip()


def _check_document_consistency(
    text: str,
    *,
    resume_source: str,
    tailored_resume: str,
    job_description: str,
    issues: list,
) -> None:
    source_text = f"{resume_source}\n{tailored_resume}\n{job_description}"
    normalized_source = _normalize_entity(source_text)
    for match in sorted(set(_EMPLOYER_RE.findall(text))):
        entity = _clean_employer_name(match)
        if _normalize_entity(entity) not in normalized_source:
            issues.append(
                WritingIssue(
                    code="invented_employer",
                    message=(
                        f"Cover letter: employer '{entity}' does not appear "
                        "in the source resume, tailored resume, or job "
                        "description; remove or correct it."
                    ),
                )
            )
    source_dates = {
        _normalize_entity(match.group(0))
        for match in _DATE_RANGE_RE.finditer(source_text)
    }
    for match in sorted(set(_DATE_RANGE_RE.findall(text))):
        if _normalize_entity(match) not in source_dates:
            issues.append(
                WritingIssue(
                    code="inconsistent_date",
                    message=(
                        f"Cover letter: date range '{match}' does not match "
                        "the source resume or tailored resume."
                    ),
                )
            )


def _check_formatting_artifacts(
    doc_name: str, text: str, issues: list
) -> None:
    match = MARKDOWN_ARTIFACT_PATTERN.search(text)
    if match:
        issues.append(
            WritingIssue(
                code="markdown_artifact",
                message=(
                    f"{doc_name}: Markdown or decorative formatting "
                    f"'{match.group(0).strip()}' found; use plain professional "
                    "document formatting."
                ),
            )
        )
    if doc_name == "Cover letter" and COVER_LETTER_BULLET_PATTERN.search(text):
        issues.append(
            WritingIssue(
                code="cover_letter_bullets",
                message=(
                    "Cover letter: bullet-list formatting found; use "
                    "professional paragraphs instead."
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


def _is_resume_heading(line: str) -> bool:
    normalized = line.strip().rstrip(":").strip().lower()
    return normalized in RESUME_SECTION_HEADINGS


def _check_empty_resume_sections(
    doc_name: str, text: str, issues: list
) -> None:
    if doc_name != "Tailored resume":
        return
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if not line or not _is_resume_heading(line):
            continue
        following = index + 1
        while following < len(lines) and not lines[following]:
            following += 1
        if following >= len(lines) or _is_resume_heading(lines[following]):
            issues.append(
                WritingIssue(
                    code="empty_section",
                    message=(
                        f"Tailored resume: section '{line.rstrip(':')}' is "
                        "empty; add verified content or remove the heading."
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
    *,
    job_description: str = "",
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
        _check_formatting_artifacts(doc_name, text, issues)
        _check_placeholders(doc_name, text, issues)
        _check_unsupported_claims(doc_name, text, resume_source, issues)
        _check_unsupported_sections(doc_name, text, resume_source, issues)
        _check_unsupported_outcomes(doc_name, text, resume_source, issues)
        _check_relative_time_claims(doc_name, text, resume_source, issues)
        _check_unsupported_metrics(doc_name, text, resume_source, issues)
        _check_repeated_openers(doc_name, text, issues)
        _check_empty_resume_sections(doc_name, text, issues)
        if doc_name == "Cover letter":
            _check_cover_letter_structure(text, issues)
            _check_document_consistency(
                text,
                resume_source=resume_source,
                tailored_resume=tailored_resume or "",
                job_description=job_description,
                issues=issues,
            )

    if tailored_resume or cover_letter:
        _check_name_preserved(
            resume_source, tailored_resume or "", cover_letter or "", issues
        )

    return WritingReview(passed=not issues, issues=issues)
