"""Job-description preprocessing.

Removes website boilerplate (navigation, cookie notices, privacy
statements, footer content, apply-CTAs, equal-opportunity paragraphs)
and extracts structured requirement sections deterministically. The
cleaned text feeds both the deterministic matcher and the AI prompt
nodes; the raw text is preserved in the run record.

Deliberately conservative: lines are only removed when they match known
boilerplate patterns — unfamiliar but meaningful wording is kept.
"""

import re

# ---------------------------------------------------------------
# Boilerplate removal
# ---------------------------------------------------------------

# Full-line patterns (case-insensitive). A line is removed when the
# whole line (after stripping punctuation/whitespace) matches one of
# these. Conservative by design: only classic website boilerplate.
_LINE_PATTERNS = [
    r"^(accept all (cookies)?|accept cookies|manage (cookie )?consent|"
    r"cookie preferences|we use cookies.*|cookies settings)",
    r"^privacy (policy|statement|notice)",
    r"^terms (of (service|use))?( &| and)? conditions?",
    r"^apply (now|for this (job|role|position))",
    r"^save (this )?job",
    r"^share (this )?(job|role)",
    r"^report (this )?(job|role)",
    r"^job alerts?",
    r"^get notified",
    r"^(sign up|subscribe)( to| for)?( job)?( alerts| updates)?",
    r"^unsubscribe",
    r"^powered by",
    r"^careers? at",
    r"^about (us|the company|our company)$",
    r"^our (company|story)$",
    r"^©.*$",
    r"^all rights reserved",
    r"^we are an? equal (opportunity|opportunities) employer.*",
    r"^equal (opportunity|opportunities) employer.*",
    r"^we (welcome|celebrate) (diversity|all).*",
    r"^our (diversity|inclusion) (statement|commitment)",
    r"^this (job|role|position) (was|is) (posted|advertised) (by|on)",
    r"^postal code|^location|^employment type|^job type",
    r"^refer(ence)? (id|number)",
    r"^back to (top|jobs|search)",
    r"^(footer|navigation|nav|menu|sitemap|related jobs|similar jobs|"
    r"more jobs|view all jobs)",
    r"^tagged as",
    r"^share:",
]

_MULTILINE_PATTERNS = [
    # Equal-opportunity boilerplate paragraphs.
    re.compile(
        r"we are an equal opportunity employer[\s\S]{0,400}?applicant",
        re.IGNORECASE,
    ),
    # Cookie-consent blocks.
    re.compile(
        r"we use cookies[\s\S]{0,300}?(accept|cookie policy)",
        re.IGNORECASE,
    ),
]

_LINE_REGEXES = [
    re.compile(pattern + r"[.!:]*$", re.IGNORECASE) for pattern in _LINE_PATTERNS
]

MIN_CLEANED_LENGTH = 60
MIN_CONTENT_RATIO = 0.3

_CLOSING_LINE_RE = re.compile(
    r"^(?:we look forward|we are excited|thank you|thanks for|"
    r"only shortlisted|we will be in touch|we will contact|"
    r"if you have any questions|questions about|apply now|"
    r"contact us|best regards|kind regards|sincerely)\b",
    re.IGNORECASE,
)
_REQUIREMENT_CUE_RE = re.compile(
    r"\b(?:ability|requirements?|responsibilities|experience|skills?|"
    r"qualifications?|knowledge|proficient|experience with|years?|"
    r"degree|certification|language|fluent|native|A1|A2|B1|B2|C1|C2)\b",
    re.IGNORECASE,
)


def strip_boilerplate(job_description: str) -> str:
    """Remove website boilerplate lines and blocks from `job_description`."""
    text = job_description
    for pattern in _MULTILINE_PATTERNS:
        text = pattern.sub(" ", text)

    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        stripped = re.sub(r"[\s|•\-*•▸·]+", " ", line).strip()
        if any(regex.match(stripped) for regex in _LINE_REGEXES):
            continue
        kept.append(line)

    cleaned = "\n".join(kept).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def is_suspiciously_thin(job_description: str, cleaned: str) -> bool:
    """True when the cleaned text is too short or mostly boilerplate."""
    if len(cleaned) < MIN_CLEANED_LENGTH:
        return True
    original_len = max(len(job_description.strip()), 1)
    return len(cleaned) / original_len < MIN_CONTENT_RATIO


def _looks_like_closing_only(cleaned: str) -> bool:
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return False
    closing = sum(1 for line in lines if _CLOSING_LINE_RE.search(line))
    return closing / len(lines) >= 0.7


def _has_requirement_content(cleaned: str) -> bool:
    sections = extract_sections(cleaned)
    for lines in sections.values():
        if any(
            _REQUIREMENT_CUE_RE.search(line)
            or line.lstrip().startswith(("-", "*", "•", "▸", "·"))
            for line in lines
        ):
            return True
    return False


def describe_warning(job_description: str, cleaned: str) -> str | None:
    """Human-readable warning when the description is incomplete."""
    if is_suspiciously_thin(job_description, cleaned):
        return (
            "The job description appears to be very short or mostly website "
            "boilerplate. Treat the estimated job-match score as indicative "
            "only, and paste a fuller description for a more reliable result."
        )
    if _looks_like_closing_only(cleaned):
        return (
            "The supplied text looks like a closing paragraph rather than a "
            "complete job advert. The assessment may be unreliable; please "
            "paste the role responsibilities and requirements."
        )
    if not _has_requirement_content(cleaned):
        return (
            "The supplied text does not appear to contain enough role "
            "requirements to produce a reliable assessment. Please paste the "
            "full job advert."
        )
    return None


# ---------------------------------------------------------------
# Structured requirement sections
# ---------------------------------------------------------------

_SECTION_HEADINGS = {
    "essential": [
        "requirements",
        "required",
        "must have",
        "must-have",
        "minimum qualifications",
        "what you need",
        "what we're looking for",
        "what we are looking for",
        "essential",
        "about you",
        "your background",
        "your profile",
    ],
    "preferred": [
        "preferred",
        "nice to have",
        "nice-to-have",
        "bonus",
        "would be a plus",
        "advantageous",
        "ideally",
        "even better",
    ],
    "technical_skills": [
        "skills",
        "technical skills",
        "core skills",
        "technologies",
        "tech stack",
        "tech stack you will use",
        "key skills",
    ],
    "responsibilities": [
        "responsibilities",
        "what you'll do",
        "what you will do",
        "your role",
        "the role",
        "key duties",
        "you will",
        "day to day",
        "day-to-day",
        "duties",
    ],
    "experience": [
        "experience",
        "years of experience",
        "work experience",
        "professional experience",
    ],
    "qualifications": [
        "education",
        "qualifications",
        "certification",
        "certifications",
        "degree",
    ],
    "achievements": [
        "achievements",
        "achievement",
        "impact",
        "outcomes",
        "results",
        "success metrics",
        "track record",
    ],
    "communication": [
        "communication",
        "collaboration",
        "interpersonal",
        "team skills",
        "soft skills",
    ],
}


def _classify_heading(line: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9' -]", " ", line.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip().rstrip(":")
    if len(normalized) > 60:
        return None
    for section, phrases in _SECTION_HEADINGS.items():
        for phrase in phrases:
            if normalized == phrase or normalized.startswith(phrase + " "):
                return section
    return None


def extract_sections(job_description: str) -> dict[str, list[str]]:
    """Bucket lines of the job description into requirement sections.

    Returns {section: [lines]} for the recognized sections. A line is
    treated as a heading when it is short and matches a known phrase;
    following non-empty lines are assigned to that section until the
    next heading. When no headings are recognized at all, every line is
    treated as an essential requirement.
    """
    sections: dict[str, list[str]] = {key: [] for key in _SECTION_HEADINGS}
    current: str | None = None
    saw_heading = False

    for raw_line in job_description.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = _classify_heading(line)
        if heading is not None:
            current = heading
            saw_heading = True
            continue
        if current is None:
            sections["essential"].append(line)
        else:
            sections[current].append(line)

    if not saw_heading:
        # No structure found: treat everything as essential.
        sections["essential"] = [
            line.strip()
            for line in job_description.splitlines()
            if line.strip()
        ]

    return sections
