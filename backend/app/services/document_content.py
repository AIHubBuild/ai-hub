"""Structured document content for CV and cover-letter templates.

The AI workflow already produces plain-text documents. This module parses
that text without changing the model, prompts, or generation workflow. The
same structured content feeds both DOCX and PDF renderers.
"""

from dataclasses import dataclass, field
import re
from typing import Iterable


_HEADING_MAP = {
    "profile": "profile",
    "professional profile": "profile",
    "professional summary": "profile",
    "summary": "profile",
    "core skills": "skills",
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "experience": "experience",
    "professional experience": "experience",
    "work experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "projects & labs": "projects",
    "projects and labs": "projects",
    "labs": "projects",
    "education": "education",
    "education & certifications": "education",
    "education and certifications": "education",
    "certifications": "certifications",
    "certificates": "certifications",
    "languages": "languages",
}

_BULLET_RE = re.compile(r"^\s*[\-*•]\s+")
_MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s*")
_MARKDOWN_EMPHASIS_RE = re.compile(r"\*\*|__")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_LINK_RE = re.compile(
    r"(?:linkedin\.com/\S+|github\.com/\S+|https?://\S+)",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+\d{4}|\d{4})\s*[-–—]\s*"
    r"(Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
    r"Nov|Dec)[a-z]*\s+\d{4}|\d{4})",
    re.IGNORECASE,
)
_EDUCATION_TERMS_RE = re.compile(
    r"\b(?:MSc|BSc|BEng|MEng|PhD|Bachelor|Master|University|"
    r"College|School|Institute|Academy)\b",
    re.IGNORECASE,
)
_CLOSING_RE = re.compile(
    r"^(kind regards|best regards|yours sincerely|yours faithfully|"
    r"sincerely|regards)\b",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"\[[^\]]+\]|\b(?:lorem ipsum|tbd|placeholder)\b",
    re.IGNORECASE,
)


@dataclass
class ContactInfo:
    name: str
    title: str | None = None
    lines: list[str] = field(default_factory=list)
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    links: list[str] = field(default_factory=list)


@dataclass
class SkillGroup:
    label: str | None
    text: str


@dataclass
class ExperienceEntry:
    title: str
    organization: str | None = None
    dates: str | None = None
    bullets: list[str] = field(default_factory=list)


@dataclass
class EducationEntry:
    credential: str
    institution: str | None = None
    dates: str | None = None
    details: list[str] = field(default_factory=list)


@dataclass
class ResumeDocument:
    contact: ContactInfo
    profile: list[str] = field(default_factory=list)
    skills: list[SkillGroup] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


@dataclass
class CoverLetterDocument:
    contact: ContactInfo
    greeting: str
    paragraphs: list[str]
    closing: str
    signature: str


@dataclass(frozen=True)
class DocumentIssue:
    code: str
    message: str


def _clean_line(line: str) -> str:
    text = _MARKDOWN_HEADING_RE.sub("", line.strip())
    text = _MARKDOWN_EMPHASIS_RE.sub("", text)
    return text.strip()


def _heading_key(line: str) -> str | None:
    normalized = _clean_line(line).rstrip(":").strip().lower()
    return _HEADING_MAP.get(normalized)


def _is_bullet(line: str) -> bool:
    return _BULLET_RE.match(line) is not None


def _bullet_text(line: str) -> str:
    return _BULLET_RE.sub("", _clean_line(line)).strip()


def _nonempty(lines: Iterable[str]) -> list[str]:
    return [_clean_line(line) for line in lines if _clean_line(line)]


def _split_paragraphs(lines: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        cleaned = _clean_line(line)
        if cleaned:
            current.append(cleaned)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _date_range(text: str) -> tuple[str | None, str]:
    match = _DATE_RANGE_RE.search(text)
    if match is None:
        return None, text.strip()
    before = text[: match.start()].strip(" |,-–—")
    return match.group(0).strip(), before


def _contact_from_lines(
    lines: list[str],
    *,
    fallback: ContactInfo | None = None,
    allow_title: bool = True,
) -> ContactInfo:
    cleaned = _nonempty(lines)
    if not cleaned:
        return fallback or ContactInfo(name="")

    name = cleaned[0]
    title: str | None = None
    contact_start = 1
    if allow_title and len(cleaned) > 1:
        candidate = cleaned[1]
        has_contact = bool(
            _EMAIL_RE.search(candidate)
            or _PHONE_RE.search(candidate)
            or _LINK_RE.search(candidate)
        )
        if not has_contact and len(candidate.split()) <= 14:
            title = candidate
            contact_start = 2

    contact_lines = cleaned[contact_start:]
    combined = " | ".join(contact_lines)
    email_match = _EMAIL_RE.search(combined)
    phone_match = _PHONE_RE.search(
        _EMAIL_RE.sub(" ", combined)
    )
    links = [match.group(0) for match in _LINK_RE.finditer(combined)]

    location = None
    for token in re.split(r"\s*\|\s*|\s{2,}", combined):
        token = token.strip(" ,;")
        if not token:
            continue
        if _EMAIL_RE.search(token) or _LINK_RE.search(token):
            continue
        if _PHONE_RE.fullmatch(token.replace(" ", "")):
            continue
        if title and token.lower() == title.lower():
            continue
        location = token
        break

    if fallback is not None:
        name = name or fallback.name
        title = title or fallback.title
        location = location or fallback.location
        email = email_match.group(0) if email_match else fallback.email
        phone = phone_match.group(0) if phone_match else fallback.phone
        links = links or fallback.links
        if not contact_lines:
            contact_lines = fallback.lines
    else:
        email = email_match.group(0) if email_match else None
        phone = phone_match.group(0) if phone_match else None

    return ContactInfo(
        name=name,
        title=title,
        lines=contact_lines,
        location=location,
        email=email,
        phone=phone,
        links=links,
    )


def parse_source_contact(source_text: str) -> ContactInfo:
    """Extract the verified contact header from the uploaded resume."""
    header: list[str] = []
    for raw in source_text.splitlines():
        line = _clean_line(raw)
        if not line:
            if header:
                break
            continue
        if _heading_key(line) is not None:
            break
        header.append(line)
        if len(header) >= 6:
            break
    return _contact_from_lines(header, allow_title=False)


def _split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = _clean_line(raw)
        heading = _heading_key(line) if line else None
        if heading is not None:
            current = heading
            sections.setdefault(current, [])
            continue
        if current is None:
            if line:
                header.append(line)
        else:
            sections[current].append(line)
    return header, sections


def _parse_skills(lines: list[str]) -> list[SkillGroup]:
    groups: list[SkillGroup] = []
    for raw in lines:
        text = _bullet_text(raw) if _is_bullet(raw) else _clean_line(raw)
        if not text:
            continue
        if ":" in text and text.index(":") <= 70:
            label, value = text.split(":", 1)
            groups.append(
                SkillGroup(label=label.strip(), text=value.strip())
            )
        else:
            groups.append(SkillGroup(label=None, text=text))
    return groups


def _parse_experience_header(header: str) -> ExperienceEntry:
    dates, without_dates = _date_range(header)
    parts = [
        part.strip()
        for part in without_dates.split("|")
        if part.strip()
    ]
    if not parts:
        return ExperienceEntry(title=header, dates=dates)
    title = parts[0]
    organization = " | ".join(parts[1:]) if len(parts) > 1 else None
    return ExperienceEntry(
        title=title,
        organization=organization,
        dates=dates,
    )


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    for raw in lines:
        if not _clean_line(raw):
            continue
        if _is_bullet(raw):
            text = _bullet_text(raw)
            if not text:
                continue
            if not entries:
                entries.append(ExperienceEntry(title=text))
            else:
                entries[-1].bullets.append(text)
            continue

        text = _clean_line(raw)
        looks_like_header = bool(
            _DATE_RANGE_RE.search(text) or "|" in text
        )
        if entries and entries[-1].bullets and not looks_like_header:
            entries[-1].bullets[-1] = (
                f"{entries[-1].bullets[-1]} {text}".strip()
            )
            continue
        entries.append(_parse_experience_header(text))
    return entries


def _parse_education(
    education_lines: list[str],
    certification_lines: list[str],
) -> tuple[list[EducationEntry], list[str]]:
    entries: list[EducationEntry] = []
    certifications: list[str] = []
    for raw in education_lines:
        text = _bullet_text(raw) if _is_bullet(raw) else _clean_line(raw)
        if not text:
            continue
        dates, without_dates = _date_range(text)
        is_education = bool(
            dates or _EDUCATION_TERMS_RE.search(without_dates)
        )
        if is_education:
            parts = [
                part.strip()
                for part in without_dates.split("|")
                if part.strip()
            ]
            entries.append(
                EducationEntry(
                    credential=parts[0] if parts else without_dates,
                    institution=(
                        " | ".join(parts[1:]) if len(parts) > 1 else None
                    ),
                    dates=dates,
                )
            )
        elif entries and _is_bullet(raw):
            entries[-1].details.append(text)
        else:
            certifications.append(text)

    certifications.extend(_nonempty(certification_lines))
    return entries, certifications


def _parse_projects(lines: list[str]) -> list[str]:
    projects: list[str] = []
    for raw in lines:
        if not _clean_line(raw):
            continue
        if _is_bullet(raw):
            text = _bullet_text(raw)
            if text:
                projects.append(text)
        elif projects:
            projects[-1] = f"{projects[-1]} {_clean_line(raw)}".strip()
        else:
            projects.append(_clean_line(raw))
    return projects


def _parse_languages(lines: list[str]) -> list[str]:
    languages: list[str] = []
    for raw in lines:
        text = _bullet_text(raw) if _is_bullet(raw) else _clean_line(raw)
        if text:
            languages.append(text)
    return languages


def parse_resume(
    text: str,
    *,
    source_text: str | None = None,
) -> ResumeDocument:
    """Parse generated resume text into the approved CV structure."""
    header, sections = _split_sections(text)
    source_contact = (
        parse_source_contact(source_text) if source_text else ContactInfo("")
    )
    contact = _contact_from_lines(header, fallback=source_contact)
    # Verified source contact details always take precedence over AI text.
    if source_contact.name:
        contact.name = source_contact.name
    if source_contact.email:
        contact.email = source_contact.email
    if source_contact.phone:
        contact.phone = source_contact.phone
    if source_contact.location:
        contact.location = source_contact.location
    if source_contact.links:
        contact.links = source_contact.links
    if source_contact.lines:
        contact.lines = source_contact.lines

    profile = _split_paragraphs(sections.get("profile", []))
    skills = _parse_skills(sections.get("skills", []))
    experience = _parse_experience(sections.get("experience", []))
    projects = _parse_projects(sections.get("projects", []))
    education, certifications = _parse_education(
        sections.get("education", []),
        sections.get("certifications", []),
    )
    languages = _parse_languages(sections.get("languages", []))
    return ResumeDocument(
        contact=contact,
        profile=profile,
        skills=skills,
        experience=experience,
        projects=projects,
        education=education,
        certifications=certifications,
        languages=languages,
    )


def parse_cover_letter(
    text: str,
    *,
    source_text: str | None = None,
) -> CoverLetterDocument:
    """Parse generated cover-letter text into the approved structure."""
    contact = (
        parse_source_contact(source_text)
        if source_text
        else ContactInfo("")
    )
    lines = [_clean_line(line) for line in text.splitlines()]
    greeting_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^(Dear|To)\b", line, re.IGNORECASE)
        ),
        None,
    )
    if greeting_index is None:
        greeting = "Dear Hiring Team,"
        body_start = 0
    else:
        greeting = lines[greeting_index]
        body_start = greeting_index + 1

    closing_index = None
    for index in range(len(lines) - 1, body_start - 1, -1):
        if _CLOSING_RE.match(lines[index]):
            closing_index = index
            break
    if closing_index is None:
        closing = "Kind regards,"
        body_lines = lines[body_start:]
        signature = contact.name
    else:
        closing = lines[closing_index]
        body_lines = lines[body_start:closing_index]
        signature = " ".join(_nonempty(lines[closing_index + 1 :]))
        if not signature:
            signature = contact.name

    paragraphs = _split_paragraphs(body_lines)
    if paragraphs and paragraphs[-1].strip().lower() == signature.lower():
        paragraphs.pop()
    return CoverLetterDocument(
        contact=contact,
        greeting=greeting,
        paragraphs=paragraphs,
        closing=closing,
        signature=signature,
    )


def validate_resume_document(document: ResumeDocument) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    if not document.contact.name.strip():
        issues.append(DocumentIssue("missing_name", "Candidate name is missing."))
    if not (document.contact.email or document.contact.phone):
        issues.append(
            DocumentIssue(
                "missing_contact",
                "No verified email or phone number was found.",
            )
        )
    if not document.profile:
        issues.append(
            DocumentIssue("missing_profile", "Professional profile is empty.")
        )
    if not document.skills:
        issues.append(
            DocumentIssue("missing_skills", "Core skills section is empty.")
        )
    if not document.experience:
        issues.append(
            DocumentIssue("missing_experience", "Experience section is empty.")
        )
    if not document.education:
        issues.append(
            DocumentIssue("missing_education", "Education section is empty.")
        )
    rendered = " ".join(
        [
            document.contact.name,
            document.contact.title or "",
            *(document.contact.lines or []),
            *document.profile,
            *[group.text for group in document.skills],
            *[
                f"{entry.title} {entry.organization or ''}"
                for entry in document.experience
            ],
            *document.projects,
            *[
                f"{entry.credential} {entry.institution or ''}"
                for entry in document.education
            ],
            *document.certifications,
            *document.languages,
        ]
    )
    if _PLACEHOLDER_RE.search(rendered):
        issues.append(
            DocumentIssue(
                "placeholder_text",
                "Placeholder text was found in the generated document.",
            )
        )
    return issues


def validate_cover_letter_document(
    document: CoverLetterDocument,
) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []
    if not document.contact.name.strip():
        issues.append(DocumentIssue("missing_name", "Candidate name is missing."))
    if not (document.contact.email or document.contact.phone):
        issues.append(
            DocumentIssue(
                "missing_contact",
                "No verified email or phone number was found.",
            )
        )
    if not document.greeting.strip():
        issues.append(
            DocumentIssue("missing_greeting", "Cover-letter greeting is missing.")
        )
    if len(document.paragraphs) < 2:
        issues.append(
            DocumentIssue(
                "insufficient_content",
                "Cover letter needs at least two body paragraphs.",
            )
        )
    if not document.closing.strip() or not document.signature.strip():
        issues.append(
            DocumentIssue(
                "missing_closing",
                "Cover-letter closing or signature is missing.",
            )
        )
    if _PLACEHOLDER_RE.search(" ".join(document.paragraphs)):
        issues.append(
            DocumentIssue(
                "placeholder_text",
                "Placeholder text was found in the generated cover letter.",
            )
        )
    return issues
