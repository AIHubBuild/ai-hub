"""Deterministic writing-quality review.

A lightweight, dependency-free review stage that runs after generation
and before results are returned or documents are exported. It flags —
never silently rewrites — issues in the tailored resume and cover
letter:

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


def _applicant_first_word(resume_source: str) -> str | None:
    for line in resume_source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        word = stripped.split()[0] if stripped.split() else ""
        # Only use it as a name signal when it looks like a name.
        if len(word) >= 3 and word[0].isupper() and word[1:].isalpha():
            return word
        return None
    return None


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
        _check_repeated_openers(doc_name, text, issues)

    if tailored_resume or cover_letter:
        _check_name_preserved(
            resume_source, tailored_resume or "", cover_letter or "", issues
        )

    return WritingReview(passed=not issues, issues=issues)
