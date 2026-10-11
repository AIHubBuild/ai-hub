"""Evidence-based job-match analysis (deterministic).

Extends the legacy keyword engine with a transparent, reproducible
scoring methodology. The estimate is deliberately labelled an
*estimated job-match score* — it does not claim to reproduce any
particular employer's ATS algorithm.

Methodology
-----------
1. Requirement terms are the legacy TECH_KEYWORDS plus a small set of
   communication competency phrases found in the cleaned job
   description. A term's category reflects the section it comes from:
   essential, technical_skills, responsibilities, experience,
   preferred, or communication (priority order below).
2. Each term is classified against the resume text:
   - ``supported`` — the exact term appears in the resume;
   - ``partial`` — only a recognized synonym appears (transferable or
     equivalent wording);
   - ``missing`` — no evidence at all.
   A keyword alone is never treated as proof of competence: every
   supported/partial term carries the resume lines that are the
   evidence for the match.
3. Coverage per category: supported = 1.0, partial = 0.5, missing = 0.0.
   ``category_coverage = 100 * sum(weights) / count``.
4. Category weights:
   essential 0.35, technical_skills 0.30, responsibilities 0.15,
   experience 0.10, preferred 0.10, communication 0.00 (informational
   only — listed with evidence but excluded from the score).
5. Estimated score: the weight-normalized weighted average of the
   category coverages —
   ``round(sum(weight * coverage) / sum(weights of non-empty categories))``.
   Only-communication descriptions score 0.

Pure functions only — the same inputs always produce the same output.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.domains.resume_ats.engine import TECH_KEYWORDS
from app.domains.resume_ats.job_description import extract_sections

SUPPORTED = "supported"
PARTIAL = "partial"
MISSING = "missing"

SUPPORTED_WEIGHT = 1.0
PARTIAL_WEIGHT = 0.5
MISSING_WEIGHT = 0.0

SCORE_LABEL = "Estimated job-match score"

# Category weights for the estimated score (see module docstring).
CATEGORY_WEIGHTS = {
    "essential": 0.35,
    "technical_skills": 0.30,
    "responsibilities": 0.15,
    "experience": 0.10,
    "preferred": 0.10,
    "communication": 0.0,
}

# Priority order used when a term appears in several sections.
CATEGORY_PRIORITY = [
    "essential",
    "technical_skills",
    "responsibilities",
    "experience",
    "communication",
]

# Communication/competency phrases tracked informationally (weight 0).
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
# Only variants of four or more characters are used for substring
# matching, to avoid false positives from short tokens.
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
    "technical support": ["help desk", "helpdesk", "it support"],
}

MAX_EVIDENCE_LINES = 3
EVIDENCE_LINE_LENGTH = 200


@dataclass
class RequirementTerm:
    term: str
    category: str
    status: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class CategoryBreakdown:
    category: str
    weight: float
    total: int
    supported: int
    partial: int
    missing: int
    score: int


@dataclass
class JobMatchAnalysis:
    estimated_score: int
    score_label: str = SCORE_LABEL
    terms: list[RequirementTerm] = field(default_factory=list)
    breakdown: list[CategoryBreakdown] = field(default_factory=list)

    @property
    def supported_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == SUPPORTED]

    @property
    def partial_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == PARTIAL]

    @property
    def missing_terms(self) -> list[str]:
        return [t.term for t in self.terms if t.status == MISSING]

    @property
    def evidence_map(self) -> dict[str, dict]:
        return {
            t.term: {
                "status": t.status,
                "category": t.category,
                "evidence": t.evidence,
            }
            for t in self.terms
        }


def _contains_any(text: str, needle: str, variants: list[str]) -> bool:
    lowered = text.lower()
    if needle in lowered:
        return True
    return any(
        len(variant) >= 4 and variant in lowered for variant in variants
    )


def _term_category(term: str, sections: dict[str, list[str]]) -> str:
    """Assign the requirement category a term belongs to.

    A term is preferred only when it appears solely in preferred lines.
    Otherwise the first section containing it wins, in the priority
    order defined by CATEGORY_PRIORITY (qualifications come before
    responsibilities, and so on).
    """
    section_text = {
        key: "\n".join(lines).lower() for key, lines in sections.items()
    }

    preferred_text = section_text.get("preferred", "")
    others = "\n".join(
        text for key, text in section_text.items() if key != "preferred"
    )
    if term in preferred_text and term not in others:
        return "preferred"

    for category in CATEGORY_PRIORITY:
        if term in section_text.get(category, ""):
            return category
    return "essential"


def _find_terms(job_description: str) -> list[tuple[str, bool]]:
    """Return (term, is_tech_keyword) pairs found in the description."""
    lowered = job_description.lower()
    found: list[tuple[str, bool]] = []
    for term in TECH_KEYWORDS:
        if term.lower() in lowered:
            found.append((term.lower(), True))
    for phrase in COMMUNICATION_PHRASES:
        if phrase in lowered:
            found.append((phrase, False))
    return found


def _evidence_lines(resume_text: str, term: str, variants: list[str]) -> list[str]:
    evidence: list[str] = []
    for line in resume_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _contains_any(line, term, variants):
            evidence.append(line[:EVIDENCE_LINE_LENGTH])
            if len(evidence) >= MAX_EVIDENCE_LINES:
                break
    return evidence


def _term_status(resume_text: str, term: str, variants: list[str]) -> str:
    lowered = resume_text.lower()
    if term in lowered:
        return SUPPORTED
    if any(
        len(variant) >= 4 and variant in lowered for variant in variants
    ):
        return PARTIAL
    return MISSING


def _category_score(
    terms: list[RequirementTerm], category: str
) -> CategoryBreakdown:
    weights = {
        SUPPORTED: SUPPORTED_WEIGHT,
        PARTIAL: PARTIAL_WEIGHT,
        MISSING: MISSING_WEIGHT,
    }
    total = len(terms)
    if total == 0:
        return CategoryBreakdown(
            category=category,
            weight=CATEGORY_WEIGHTS[category],
            total=0,
            supported=0,
            partial=0,
            missing=0,
            score=0,
        )
    supported = sum(1 for t in terms if t.status == SUPPORTED)
    partial = sum(1 for t in terms if t.status == PARTIAL)
    missing = total - supported - partial
    score = round(
        100 * sum(weights[t.status] for t in terms) / total
    )
    return CategoryBreakdown(
        category=category,
        weight=CATEGORY_WEIGHTS[category],
        total=total,
        supported=supported,
        partial=partial,
        missing=missing,
        score=score,
    )


def analyze_job_match(
    resume_text: str, cleaned_job_description: str
) -> JobMatchAnalysis:
    """Run the evidence-based match analysis.

    Pure and reproducible: identical inputs produce identical outputs.
    """
    sections = extract_sections(cleaned_job_description)
    found_terms = _find_terms(cleaned_job_description)

    terms: list[RequirementTerm] = []
    for name, _is_tech in found_terms:
        canonical = name.lower()
        variants = SYNONYMS.get(canonical, [])
        terms.append(
            RequirementTerm(
                term=canonical,
                category=_term_category(canonical, sections),
                status=_term_status(resume_text, canonical, variants),
                evidence=_evidence_lines(resume_text, canonical, variants),
            )
        )

    breakdown = [
        _category_score(
            [t for t in terms if t.category == category], category
        )
        for category in CATEGORY_PRIORITY + ["preferred"]
    ]
    non_empty = [entry for entry in breakdown if entry.total > 0]
    scored = [
        entry for entry in non_empty if entry.category != "communication"
    ]

    if scored:
        total_weight = sum(entry.weight for entry in scored)
        estimated = round(
            sum(entry.weight * entry.score for entry in scored) / total_weight
        )
    else:
        estimated = 0

    return JobMatchAnalysis(
        estimated_score=estimated,
        terms=terms,
        breakdown=non_empty,
    )


def evidence_text(analysis: JobMatchAnalysis) -> str:
    """Compact text form of the requirement evidence for AI prompts."""
    lines = []
    for term in analysis.terms:
        status = term.status
        evidence = "; ".join(term.evidence) if term.evidence else "no evidence"
        lines.append(
            f"- {term.term} ({term.category}, {status}): {evidence}"
        )
    return "\n".join(lines)
