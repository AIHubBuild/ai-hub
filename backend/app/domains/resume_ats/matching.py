"""Evidence-based resume-to-job match analysis (deterministic).

The estimate is deliberately labelled an *estimated resume-to-job
match*. It does not claim to reproduce any employer's ATS algorithm.

Methodology
-----------
1. Every meaningful requirement line in the job description is scored,
   not only the fixed technology-keyword list. Lines come from the
   explicit requirement sections when present; unstructured descriptions
   contribute only lines that look like actual requirements.
2. Requirements are grouped into six dimensions: skills, experience,
   responsibilities, qualifications, achievements, and communication.
   A requirement is mandatory unless it came from an explicit
   "preferred" section.
3. Each requirement is classified against the resume:
   - ``matched``: direct evidence satisfies the requirement;
   - ``partial``: only a recognised synonym or transferable evidence;
   - ``unverified``: the term appears, but the resume does not show
     enough context to verify it (for example, a tool listed without
     experience, or an experience requirement with no stated duration);
   - ``missing``: no supporting evidence.
4. Dimension coverage uses fixed, documented weights and per-requirement
   importance (mandatory 1.0, preferred 0.4). Status credit is matched
   1.0, partial 0.5, unverified 0.25, missing 0.0.
5. Requirement coverage alone can be misleading when a sparse description
   lists only a few skills. A separate evidence-confidence score measures
   whether the resume shows dated experience, responsibility evidence,
   qualifications, achievements, and skill evidence. The final estimate
   is ``requirement_coverage * (0.7 + 0.3 * evidence_confidence)``. This
   is a documented evidence adjustment, not a cap or random correction.
6. Scores and explanations are pure functions of the two input texts.
   Date ranges use the current calendar year when a role is marked
   "Present" or "Current".

No candidate qualification or job requirement is invented. If the
description does not contain a recognisable requirement, the score is 0.
"""

from dataclasses import dataclass, field
from datetime import date
import re
from typing import Optional

from app.domains.resume_ats.engine import STOPWORDS, TECH_KEYWORDS
from app.domains.resume_ats.job_description import extract_sections

MATCHED = "matched"
PARTIAL = "partial"
UNVERIFIED = "unverified"
MISSING = "missing"

# Backwards-compatible alias used by older callers/tests.
SUPPORTED = MATCHED

STATUS_WEIGHTS = {
    MATCHED: 1.0,
    PARTIAL: 0.5,
    UNVERIFIED: 0.25,
    MISSING: 0.0,
}

SCORE_LABEL = "Estimated resume-to-job match"

DIMENSIONS = [
    "skills",
    "experience",
    "responsibilities",
    "qualifications",
    "achievements",
    "communication",
]

DIMENSION_WEIGHTS = {
    "skills": 0.30,
    "experience": 0.25,
    "responsibilities": 0.15,
    "qualifications": 0.15,
    "achievements": 0.10,
    "communication": 0.05,
}

MANDATORY_IMPORTANCE = 1.0
PREFERRED_IMPORTANCE = 0.4
EVIDENCE_CONFIDENCE_WEIGHT = 0.30

# Explicit "preferred" requirements are optional; communication is kept
# in the breakdown but has a small weight so missing communication
# requirements do not dominate the result.
SECTION_DIMENSIONS = {
    "technical_skills": "skills",
    "experience": "experience",
    "responsibilities": "responsibilities",
    "qualifications": "qualifications",
    "achievements": "achievements",
    "communication": "communication",
}

# Communication/competency phrases tracked as requirements.
COMMUNICATION_PHRASES = [
    "customer service",
    "customer-facing",
    "stakeholder management",
    "communication skills",
    "interpersonal skills",
    "collaboration",
    "teamwork",
    "documentation",
    "problem-solving",
    "analytical skills",
    "time management",
]

# Conservative synonym groups (canonical term -> recognized variants).
SYNONYMS: dict[str, list[str]] = {
    "microsoft 365": ["office 365", "m365"],
    "active directory": ["active directory services"],
    "entra id": ["azure active directory"],
    "intune": ["microsoft intune", "endpoint manager"],
    "vpn": ["virtual private network"],
    "dns": ["domain name system"],
    "dhcp": ["dynamic host configuration protocol"],
    "tcp/ip": ["tcp ip"],
    "sla": ["service level agreement"],
    "technical support": ["help desk", "helpdesk", "it support", "service desk"],
    "incident management": [
        "incident handling",
        "incident resolution",
        "ticket management",
        "ticket handling",
    ],
    "endpoint management": ["device management", "endpoint administration"],
    "user provisioning": ["account provisioning", "user onboarding"],
}

LANGUAGE_LEVELS = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "basic": 2,
    "conversational": 3,
    "intermediate": 3,
    "business": 4,
    "advanced": 5,
    "proficient": 5,
    "fluent": 5,
    "native": 6,
}
_LANGUAGE_NAMES = (
    "english",
    "german",
    "french",
    "spanish",
    "italian",
    "dutch",
    "portuguese",
    "polish",
    "czech",
    "swedish",
    "danish",
    "norwegian",
    "finnish",
    "turkish",
    "arabic",
    "mandarin",
    "chinese",
)
_LANGUAGE_LEVEL_RE = re.compile(
    r"\b(" + "|".join(_LANGUAGE_NAMES) + r")\b"
    r"[^\n]{0,40}?\b(" + "|".join(LANGUAGE_LEVELS) + r")\b",
    re.IGNORECASE,
)
_LEVEL_LANGUAGE_RE = re.compile(
    r"\b(" + "|".join(LANGUAGE_LEVELS) + r")\b"
    r"[^\n]{0,20}?\b(" + "|".join(_LANGUAGE_NAMES) + r")\b",
    re.IGNORECASE,
)
_LANGUAGE_ONLY_RE = re.compile(
    r"\b(" + "|".join(_LANGUAGE_NAMES) + r")\b", re.IGNORECASE
)

MAX_EVIDENCE_LINES = 3
EVIDENCE_LINE_LENGTH = 220

_SORTED_KEYWORDS = sorted(TECH_KEYWORDS, key=lambda term: (-len(term), term))

_ACTION_RE = re.compile(
    r"\b(?:administered|built|configured|coordinated|created|"
    r"delivered|deployed|designed|developed|documented|ensured|handled|"
    r"implemented|installed|led|maintained|managed|migrated|monitored|"
    r"provided|resolved|secured|supported|trained|troubleshot|upgraded)\b",
    re.IGNORECASE,
)

_OUTCOME_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s?%|\b\d+\s+(?:users|clients|sites|tickets|"
    r"servers|devices|hours|days)\b|\b(?:reduced|reducing|improved|"
    r"improving|increased|increasing|saved|cut|decreased|downtime|sla|"
    r"achieved|delivered|optimized|boosted|revenue|cost)\b)",
    re.IGNORECASE,
)

_QUALIFICATION_RE = re.compile(
    r"\b(?:degree|bachelor|master|bsc|msc|ba|ma|phd|diploma|certification|"
    r"certified|certificate|accredited)\b",
    re.IGNORECASE,
)

_COMMUNICATION_RE = re.compile(
    r"\b(?:communication|collaboration|interpersonal|teamwork|customer "
    r"service|stakeholder|presentation|written|verbal)\b",
    re.IGNORECASE,
)

_EXPERIENCE_CONTEXT_RE = re.compile(
    r"\b(?:experience with|experienced with|experience in|years of experience|hands-on|"
    r"worked with|worked in|background in|professional experience)\b",
    re.IGNORECASE,
)

_REQUIREMENT_CUE_RE = re.compile(
    r"\b(?:ability|able|accredited|background|bachelor|certification|"
    r"certified|collaboration|communication|configure|degree|deliver|"
    r"demonstrated|document|experience|familiar|familiarity|knowledge|"
    r"maintain|manage|master|must|proficiency|proficient|proven|"
    r"qualification|required|requirements?|resolve|responsibilities|"
    r"responsibility|skills?|support|track record|troubleshoot|years?)\b",
    re.IGNORECASE,
)

_ROLE_TITLE_RE = re.compile(
    r"\b(?:engineer|specialist|analyst|manager|consultant|technician|"
    r"administrator|coordinator|assistant|director|architect|lead)\b",
    re.IGNORECASE,
)

_NON_REQUIREMENT_START_RE = re.compile(
    r"^(?:about\b|benefits\b|company\b|join\b|our\b|salary\b|"
    r"we (?:are|offer|provide|use)\b|this (?:role|position)\b|"
    r"you will join\b)",
    re.IGNORECASE,
)

_YEARS_RE = re.compile(r"\b(\d{1,2})\s*(?:\+|plus)?\s*(?:years?|yrs?)\b", re.I)
_DATE_RANGE_RE = re.compile(
    r"\b(19|20)\d{2}\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current)\b",
    re.IGNORECASE,
)

_REQUIREMENT_STOPWORDS = set(STOPWORDS) | {
    "ability", "able", "accredited", "background", "bachelor", "certification",
    "certified", "collaboration", "communication", "configure", "degree",
    "deliver", "demonstrated", "document", "experience", "familiar",
    "familiarity", "knowledge", "maintain", "manage", "master", "must",
    "proficiency", "proficient", "proven", "qualification", "required",
    "requirement", "requirements", "resolve", "responsibilities",
    "responsibility", "skills", "support", "track", "record", "troubleshoot",
    "year", "years",
}


@dataclass
class Requirement:
    """One scored requirement from the job description."""

    text: str
    section: str
    dimension: str
    mandatory: bool
    keywords: list[str] = field(default_factory=list)
    status: str = MISSING
    evidence: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def importance(self) -> float:
        return MANDATORY_IMPORTANCE if self.mandatory else PREFERRED_IMPORTANCE


@dataclass
class RequirementTerm:
    """Keyword-level view of the requirement results.

    Kept separate from the full requirement list so the UI can show a
    concise keyword list while the score is calculated from complete
    requirements.
    """

    term: str
    category: str
    status: str
    evidence: list[str] = field(default_factory=list)
    dimension: str = "skills"
    mandatory: bool = True
    detail: str = ""


@dataclass
class CategoryBreakdown:
    category: str
    weight: float
    total: int
    supported: int
    partial: int
    missing: int
    score: int
    unverified: int = 0


@dataclass
class JobMatchAnalysis:
    estimated_score: int
    score_label: str = SCORE_LABEL
    requirement_coverage: int = 0
    evidence_confidence: int = 0
    terms: list[RequirementTerm] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    breakdown: list[CategoryBreakdown] = field(default_factory=list)

    @property
    def supported_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == MATCHED]

    @property
    def partial_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == PARTIAL]

    @property
    def unverified_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == UNVERIFIED]

    @property
    def missing_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == MISSING]

    @property
    def evidence_map(self) -> dict[str, dict]:
        return {
            t.term: {
                "status": t.status,
                "category": t.category,
                "dimension": t.dimension,
                "evidence": t.evidence,
                "detail": t.detail,
                "mandatory": t.mandatory,
            }
            for t in self.terms
        }

    @property
    def requirement_evidence(self) -> list[dict]:
        return [
            {
                "term": requirement.text,
                "status": requirement.status,
                "category": requirement.dimension,
                "section": requirement.section,
                "evidence": requirement.evidence,
                "detail": requirement.detail,
                "mandatory": requirement.mandatory,
            }
            for requirement in self.requirements
        ]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9+/#]+", lowered)
    return {
        _stem(word)
        for word in words
        if len(word) >= 3 and word not in _REQUIREMENT_STOPWORDS
    }


def _clean_line(line: str) -> str:
    cleaned = re.sub(r"^[\s\-*•▸·]+", "", line).strip()
    cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned).strip()
    return re.sub(r"\s+", " ", cleaned)


def _keywords_in(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for canonical in _SORTED_KEYWORDS:
        variants = [canonical] + SYNONYMS.get(canonical, [])
        if any(variant in lowered for variant in variants):
            found.append(canonical)
    for phrase in COMMUNICATION_PHRASES:
        if phrase in lowered:
            found.append(phrase)
    return sorted(set(found), key=lambda term: (-len(term), term))


def _looks_like_job_title(text: str) -> bool:
    if len(text.split()) > 7 or not _ROLE_TITLE_RE.search(text):
        return False
    if _ACTION_RE.search(text) or _YEARS_RE.search(text):
        return False
    return not re.search(
        r"\b(?:ability|experience|knowledge|required|requirements?|"
        r"responsibilities|skills?|degree|certification)\b",
        text,
        re.IGNORECASE,
    )


def _is_requirement_like(raw_line: str, text: str) -> bool:
    if raw_line.lstrip().startswith(("-", "*", "•", "▸", "·")):
        return True
    if _NON_REQUIREMENT_START_RE.search(text):
        return False
    # A bare job title is not a requirement, even when it contains a
    # technology term such as "Technical Support Engineer".
    if _looks_like_job_title(text):
        return False
    if _keywords_in(text):
        return True
    if _LANGUAGE_LEVEL_RE.search(text) or _LEVEL_LANGUAGE_RE.search(text):
        return True
    return _REQUIREMENT_CUE_RE.search(text) is not None


def _infer_dimension(text: str, default: str = "responsibilities") -> str:
    if _QUALIFICATION_RE.search(text):
        return "qualifications"
    if _OUTCOME_RE.search(text) or re.search(
        r"\b(?:achievement|achievements|impact|outcomes?|results?|track record)\b",
        text,
        re.IGNORECASE,
    ):
        return "achievements"
    if _YEARS_RE.search(text) or re.search(
        r"\bexperience\b", text, re.IGNORECASE
    ):
        return "experience"
    if _COMMUNICATION_RE.search(text) or any(
        phrase in text.lower() for phrase in COMMUNICATION_PHRASES
    ):
        return "communication"
    if _ACTION_RE.search(text):
        return "responsibilities"
    if _keywords_in(text):
        return "skills"
    return default


def _requirement_dimension(text: str, section: str) -> str:
    if section in SECTION_DIMENSIONS:
        return SECTION_DIMENSIONS[section]
    if section == "preferred":
        return _infer_dimension(text, default="skills")
    return _infer_dimension(text, default="responsibilities")


def _extract_requirements(job_description: str) -> list[Requirement]:
    sections = extract_sections(job_description)
    requirements: list[Requirement] = []
    seen: set[str] = set()

    order = [
        "technical_skills",
        "experience",
        "responsibilities",
        "qualifications",
        "achievements",
        "communication",
        "preferred",
        "essential",
    ]
    for section in order:
        for raw_line in sections.get(section, []):
            text = _clean_line(raw_line)
            if not text or len(text) < 3:
                continue
            if section == "essential" and not _is_requirement_like(raw_line, text):
                continue
            key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            if key in seen:
                continue
            seen.add(key)
            requirements.append(
                Requirement(
                    text=text,
                    section=section,
                    dimension=_requirement_dimension(text, section),
                    mandatory=section != "preferred",
                    keywords=_keywords_in(text),
                )
            )
    return requirements


def _variants_for(keyword: str) -> list[str]:
    return [keyword] + SYNONYMS.get(keyword, [])


def _line_overlap(requirement_tokens: set[str], line: str) -> float:
    if not requirement_tokens:
        return 0.0
    line_tokens = _tokens(line)
    return len(requirement_tokens & line_tokens) / len(requirement_tokens)


def _evidence_lines(
    resume_text: str, keywords: list[str], requirement_text: str
) -> list[str]:
    requirement_tokens = _tokens(requirement_text)
    evidence: list[str] = []
    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        keyword_hit = any(
            any(variant in lowered for variant in _variants_for(keyword))
            for keyword in keywords
        )
        overlap = _line_overlap(requirement_tokens, line)
        threshold = 0.45 if keywords else 0.5
        if keyword_hit or overlap >= threshold:
            evidence.append(line[:EVIDENCE_LINE_LENGTH])
            if len(evidence) >= MAX_EVIDENCE_LINES:
                break
    return evidence


def _has_action_evidence(lines: list[str]) -> bool:
    return any(_ACTION_RE.search(line) for line in lines)


def _has_outcome_evidence(lines: list[str]) -> bool:
    return any(_OUTCOME_RE.search(line) for line in lines)


def _qualification_signal(text: str) -> bool:
    return _QUALIFICATION_RE.search(text) is not None


def _required_years(text: str) -> Optional[int]:
    match = _YEARS_RE.search(text)
    return int(match.group(1)) if match else None


def _resume_years(resume_text: str, reference_year: int) -> Optional[int]:
    explicit = [int(m) for m in re.findall(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", resume_text, re.I)]
    intervals: list[tuple[int, int]] = []
    for match in _DATE_RANGE_RE.finditer(resume_text):
        start = int(match.group(0)[:4])
        end_text = match.group(2).lower()
        end = reference_year if end_text in {"present", "current"} else int(end_text)
        if end >= start and start >= 1970:
            intervals.append((start, end))

    intervals.sort()
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    dated_years = sum(end - start for start, end in merged)

    candidates = explicit + ([dated_years] if dated_years else [])
    return max(candidates) if candidates else None


def _has_dated_experience(resume_text: str) -> bool:
    return _DATE_RANGE_RE.search(resume_text) is not None


def _has_qualification_evidence(resume_text: str) -> bool:
    return _qualification_signal(resume_text)


def _action_line_count(resume_text: str) -> int:
    return sum(
        1
        for line in resume_text.splitlines()
        if line.strip() and _ACTION_RE.search(line)
    )


def _outcome_line_count(resume_text: str) -> int:
    return sum(
        1
        for line in resume_text.splitlines()
        if line.strip() and _OUTCOME_RE.search(line)
    )


def _communication_signal(resume_text: str) -> float:
    lowered = resume_text.lower()
    if any(phrase in lowered for phrase in COMMUNICATION_PHRASES):
        return 1.0
    if re.search(r"\b(?:customer|client|team|colleague|stakeholder)\b", lowered):
        return 0.5
    return 0.0


def _evidence_confidence(resume_text: str, reference_year: int) -> float:
    skill_signal = 1.0 if any(
        keyword in resume_text.lower() for keyword in TECH_KEYWORDS
    ) else 0.0
    experience_signal = 0.0
    if _resume_years(resume_text, reference_year) is not None:
        experience_signal = 1.0
    elif _action_line_count(resume_text) >= 2:
        experience_signal = 0.5

    action_count = _action_line_count(resume_text)
    responsibility_signal = 1.0 if action_count >= 2 else 0.5 if action_count else 0.0

    qualification_signal = 1.0 if _has_qualification_evidence(resume_text) else 0.0

    outcome_count = _outcome_line_count(resume_text)
    achievement_signal = 1.0 if outcome_count >= 2 else 0.5 if outcome_count else 0.0

    signals = {
        "skills": skill_signal,
        "experience": experience_signal,
        "responsibilities": responsibility_signal,
        "qualifications": qualification_signal,
        "achievements": achievement_signal,
        "communication": _communication_signal(resume_text),
    }
    return sum(
        DIMENSION_WEIGHTS[dimension] * signals[dimension]
        for dimension in DIMENSIONS
    )


def _with_missing(detail: str, missing: list[str]) -> str:
    if not missing:
        return detail
    return f"{detail} Missing terms: {', '.join(missing)}."


def _keyword_coverage(
    keywords: list[str], resume_lower: str
) -> tuple[list[str], list[str], list[str]]:
    exact: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    for keyword in keywords:
        if keyword in resume_lower:
            exact.append(keyword)
        elif any(
            variant in resume_lower
            for variant in SYNONYMS.get(keyword, [])
        ):
            partial.append(keyword)
        else:
            missing.append(keyword)
    return exact, partial, missing


def _language_requirement(text: str) -> tuple[str, int | None] | None:
    """Return (language, required level rank) for a language requirement."""
    match = _LANGUAGE_LEVEL_RE.search(text)
    if match:
        return match.group(1).lower(), LANGUAGE_LEVELS[match.group(2).lower()]
    match = _LEVEL_LANGUAGE_RE.search(text)
    if match:
        return match.group(2).lower(), LANGUAGE_LEVELS[match.group(1).lower()]
    match = _LANGUAGE_ONLY_RE.search(text)
    if match:
        return match.group(1).lower(), None
    return None


def _resume_language_level(resume_text: str, language: str) -> int | None:
    """Return the highest explicitly stated level for a language, if any."""
    levels: list[int] = []
    for match in _LANGUAGE_LEVEL_RE.finditer(resume_text):
        if match.group(1).lower() == language:
            levels.append(LANGUAGE_LEVELS[match.group(2).lower()])
    for match in _LEVEL_LANGUAGE_RE.finditer(resume_text):
        if match.group(2).lower() == language:
            levels.append(LANGUAGE_LEVELS[match.group(1).lower()])
    return max(levels) if levels else None


def _has_skill_context(evidence: list[str]) -> bool:
    return any(
        _EXPERIENCE_CONTEXT_RE.search(line)
        or _OUTCOME_RE.search(line)
        or _ACTION_RE.search(line)
        for line in evidence
    )


def _evaluate_requirement(
    requirement: Requirement,
    resume_text: str,
    reference_year: int,
) -> tuple[str, list[str], str]:
    keywords = requirement.keywords
    evidence = _evidence_lines(resume_text, keywords, requirement.text)
    lowered_resume = resume_text.lower()

    language_requirement = _language_requirement(requirement.text)
    if language_requirement is not None:
        language, required_level = language_requirement
        if required_level is None:
            return (
                UNVERIFIED,
                evidence,
                f"The job mentions {language.title()} but does not state a "
                "required level.",
            )
        candidate_level = _resume_language_level(resume_text, language)
        if candidate_level is None:
            return (
                UNVERIFIED,
                evidence,
                f"The candidate's {language.title()} level is not "
                "explicitly stated.",
            )
        if candidate_level >= required_level:
            return (
                MATCHED,
                evidence,
                f"Stated {language.title()} level meets the requirement.",
            )
        return (
            MISSING,
            evidence,
            f"The candidate's stated {language.title()} level is below the "
            "level requested.",
        )

    exact_terms, partial_terms, missing_keywords = _keyword_coverage(
        keywords, lowered_resume
    )
    exact = bool(exact_terms)
    partial = bool(partial_terms)

    requirement_tokens = _tokens(requirement.text)
    max_overlap = max(
        (_line_overlap(requirement_tokens, line) for line in evidence),
        default=0.0,
    )
    if not keywords:
        exact = max_overlap >= 0.6
        partial = 0.35 <= max_overlap < 0.6
        missing_keywords = []

    if not exact and not partial:
        return MISSING, [], "No supporting evidence found in the resume."

    action = _has_action_evidence(evidence)
    outcome = _has_outcome_evidence(evidence)
    complete_match = (
        (not missing_keywords and not partial_terms)
        if keywords
        else exact
    )

    if requirement.dimension == "skills":
        if missing_keywords or partial_terms:
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Some required skill terms are missing or only related.",
                    missing_keywords + partial_terms,
                ),
            )
        if exact:
            if action or _has_skill_context(evidence):
                return MATCHED, evidence, "All required skills appear with work context."
            return (
                UNVERIFIED,
                evidence,
                "The skill terms appear, but the resume does not show work "
                "context for them.",
            )
        return MISSING, evidence, "No required skill evidence found."

    if requirement.dimension == "experience":
        required_years = _required_years(requirement.text)
        resume_years = _resume_years(resume_text, reference_year)
        context = (
            action
            or _has_dated_experience(resume_text)
            or _EXPERIENCE_CONTEXT_RE.search(resume_text) is not None
        )
        if required_years is not None:
            if resume_years is None:
                return (
                    UNVERIFIED,
                    evidence,
                    _with_missing(
                        f"Requires {required_years}+ years; the resume does not state a total.",
                        missing_keywords,
                    ),
                )
            if resume_years >= required_years:
                if not missing_keywords and context:
                    return (
                        MATCHED,
                        evidence,
                        f"{resume_years} years of dated experience found; {required_years}+ requested.",
                    )
                return (
                    PARTIAL,
                    evidence,
                    _with_missing(
                        f"{resume_years} years found; {required_years}+ requested.",
                        missing_keywords,
                    ),
                )
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    f"{resume_years} years found; {required_years}+ requested.",
                    missing_keywords,
                ),
            )
        if complete_match and context:
            return MATCHED, evidence, "Experience evidence found."
        if exact and context:
            return (
                PARTIAL,
                evidence,
                _with_missing("Experience evidence found.", missing_keywords),
            )
        if partial and context:
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Related experience evidence found.", missing_keywords
                ),
            )
        if exact or partial:
            return (
                UNVERIFIED,
                evidence,
                _with_missing(
                    "The terms appear, but the resume does not show enough experience context.",
                    missing_keywords,
                ),
            )
        return MISSING, evidence, "No experience evidence found."

    if requirement.dimension == "qualifications":
        if complete_match and _qualification_signal(" ".join(evidence)):
            return MATCHED, evidence, "Qualification or certification evidence found."
        if exact and _qualification_signal(" ".join(evidence)):
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Some qualification terms are missing.", missing_keywords
                ),
            )
        if exact or partial:
            return (
                UNVERIFIED,
                evidence,
                _with_missing(
                    "The qualification is mentioned, but certification or degree context is not shown.",
                    missing_keywords,
                ),
            )
        return MISSING, evidence, "No qualification evidence found."

    if requirement.dimension == "responsibilities":
        if complete_match and action:
            return MATCHED, evidence, "Responsibility evidence found in the resume."
        if (exact or partial) and action:
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Some responsibility terms are missing.", missing_keywords
                ),
            )
        if exact or partial:
            return (
                UNVERIFIED,
                evidence,
                _with_missing(
                    "The terms appear, but the resume does not show this responsibility in context.",
                    missing_keywords,
                ),
            )
        return MISSING, evidence, "No responsibility evidence found."

    if requirement.dimension == "achievements":
        if outcome and complete_match:
            return MATCHED, evidence, "Outcome or measurable impact evidence found."
        if outcome:
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Some achievement terms are missing.", missing_keywords
                ),
            )
        if action:
            return (
                PARTIAL,
                evidence,
                _with_missing(
                    "Action evidence found, but no outcome is stated.",
                    missing_keywords,
                ),
            )
        return (
            UNVERIFIED,
            evidence,
            _with_missing(
                "The terms appear, but no measurable outcome is shown.",
                missing_keywords,
            ),
        )

    if requirement.dimension == "communication":
        if complete_match:
            return MATCHED, evidence, "Communication evidence found."
        return (
            PARTIAL,
            evidence,
            _with_missing(
                "Some communication evidence was found.", missing_keywords
            ),
        )

    return MISSING, evidence, "No supporting evidence found in the resume."


SECTION_PRIORITY = {
    "essential": 0,
    "technical_skills": 1,
    "experience": 2,
    "qualifications": 3,
    "responsibilities": 4,
    "achievements": 5,
    "communication": 6,
    "preferred": 7,
}


def _keyword_term_status(
    requirement: Requirement, keyword: str, resume_lower: str
) -> str:
    if keyword in resume_lower:
        if requirement.status == UNVERIFIED:
            return UNVERIFIED
        if requirement.status == MISSING:
            return MISSING
        return MATCHED
    if any(
        variant in resume_lower
        for variant in SYNONYMS.get(keyword, [])
    ):
        return PARTIAL
    return MISSING


def _keyword_terms(
    requirements: list[Requirement], resume_text: str
) -> list[RequirementTerm]:
    status_rank = {MATCHED: 3, PARTIAL: 2, UNVERIFIED: 1, MISSING: 0}
    lowered_resume = resume_text.lower()
    by_term: dict[str, RequirementTerm] = {}
    for requirement in requirements:
        for keyword in requirement.keywords:
            status = _keyword_term_status(requirement, keyword, lowered_resume)
            existing = by_term.get(keyword)
            if existing is None or (
                status_rank[status],
                -SECTION_PRIORITY.get(requirement.section, 99),
            ) > (
                status_rank[existing.status],
                -SECTION_PRIORITY.get(existing.category, 99),
            ):
                by_term[keyword] = RequirementTerm(
                    term=keyword,
                    category=requirement.section,
                    status=status,
                    evidence=requirement.evidence,
                    dimension=requirement.dimension,
                    mandatory=requirement.mandatory,
                    detail=requirement.detail,
                )
    return sorted(by_term.values(), key=lambda term: term.term)


def _dimension_breakdown(
    requirements: list[Requirement], dimension: str
) -> CategoryBreakdown:
    selected = [r for r in requirements if r.dimension == dimension]
    total = len(selected)
    weight = DIMENSION_WEIGHTS[dimension]
    if total == 0:
        return CategoryBreakdown(
            category=dimension,
            weight=weight,
            total=0,
            supported=0,
            partial=0,
            missing=0,
            unverified=0,
            score=0,
        )

    supported = sum(1 for r in selected if r.status == MATCHED)
    partial = sum(1 for r in selected if r.status == PARTIAL)
    unverified = sum(1 for r in selected if r.status == UNVERIFIED)
    missing = sum(1 for r in selected if r.status == MISSING)
    importance_total = sum(r.importance for r in selected)
    weighted_credit = sum(
        r.importance * STATUS_WEIGHTS[r.status] for r in selected
    )
    score = round(100 * weighted_credit / importance_total)
    return CategoryBreakdown(
        category=dimension,
        weight=weight,
        total=total,
        supported=supported,
        partial=partial,
        missing=missing,
        unverified=unverified,
        score=score,
    )


def analyze_job_match(
    resume_text: str,
    cleaned_job_description: str,
    *,
    reference_year: int | None = None,
) -> JobMatchAnalysis:
    """Run the deterministic resume-to-job match analysis.

    The score combines full requirement coverage with resume evidence
    confidence. Identical inputs and reference year produce identical
    outputs.
    """
    reference_year = reference_year or date.today().year
    requirements = _extract_requirements(cleaned_job_description)

    for requirement in requirements:
        requirement.status, requirement.evidence, requirement.detail = (
            _evaluate_requirement(requirement, resume_text, reference_year)
        )

    breakdown = [
        _dimension_breakdown(requirements, dimension)
        for dimension in DIMENSIONS
    ]
    non_empty = [entry for entry in breakdown if entry.total > 0]
    scored = [entry for entry in non_empty if entry.weight > 0]

    if scored:
        total_weight = sum(entry.weight for entry in scored)
        coverage = sum(entry.weight * entry.score for entry in scored) / total_weight
    else:
        coverage = 0.0

    confidence = _evidence_confidence(resume_text, reference_year)
    estimated = round(
        coverage
        * (
            (1 - EVIDENCE_CONFIDENCE_WEIGHT)
            + EVIDENCE_CONFIDENCE_WEIGHT * confidence
        )
    )

    return JobMatchAnalysis(
        estimated_score=estimated,
        score_label=SCORE_LABEL,
        requirement_coverage=round(coverage),
        evidence_confidence=round(confidence * 100),
        terms=_keyword_terms(requirements, resume_text),
        requirements=requirements,
        breakdown=non_empty,
    )


def evidence_text(analysis: JobMatchAnalysis) -> str:
    """Compact text form of the requirement evidence for AI prompts."""
    lines = []
    for requirement in analysis.requirements:
        evidence = (
            "; ".join(requirement.evidence)
            if requirement.evidence
            else "no evidence"
        )
        lines.append(
            f"- {requirement.text} ({requirement.dimension}, "
            f"{requirement.status}): {evidence} [{requirement.detail}]"
        )
    return "\n".join(lines)
