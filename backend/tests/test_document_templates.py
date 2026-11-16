"""Tests for the approved CV and cover-letter DOCX/PDF templates."""

from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.services.document_content import (
    parse_cover_letter,
    parse_resume,
    validate_cover_letter_document,
    validate_resume_document,
)
from app.services.document_templates import (
    render_cover_letter_docx,
    render_cover_letter_pdf,
    render_resume_docx,
    render_resume_pdf,
)

RESUME_TEXT = """Jane Doe
IT Support Engineer
Berlin, Germany | jane@example.com | +49 123 456789
linkedin.com/in/jane-doe

PROFESSIONAL SUMMARY
IT support engineer with verified experience supporting Windows and
Microsoft 365 users.

CORE SKILLS
End-user Support: Windows 10/11, laptop setup, troubleshooting.
Microsoft & Identity: Microsoft 365, Active Directory, Entra ID.
Networking: DNS, DHCP, VPN and connectivity troubleshooting.

PROFESSIONAL EXPERIENCE
IT Support Engineer | Example GmbH, Berlin Oct 2023 - Present
- Provided first and second-line support to end users.
- Managed incidents through the service desk and documented resolutions.
IT Support Specialist | Sample Ltd., Berlin May 2021 - Sep 2023
- Supported Microsoft 365 applications and user account access.

PROJECTS
- Intune and Autopilot lab in a personal test tenant.
- Linux administration lab with SSH and firewall configuration.

EDUCATION
BSc Computer Science | Example University, Berlin Sep 2018 - Jun 2022

CERTIFICATIONS
Microsoft 365 Certified: Fundamentals

LANGUAGES
English: C2 | German: B2
"""

COVER_TEXT = """Dear Hiring Team,

I am applying for the IT Support Engineer position. My verified experience
includes Windows support, Microsoft 365 administration and service-desk
incident handling.

I have supported users through account access, device setup and connectivity
troubleshooting. I document resolutions clearly and work through incidents in
a structured way.

Sincerely,
Jane Doe
"""

SOURCE_TEXT = """Jane Doe
Berlin, Germany
jane@example.com
+49 123 456789
"""


def test_resume_parser_maps_template_sections():
    document = parse_resume(RESUME_TEXT, source_text=SOURCE_TEXT)
    assert document.contact.name == "Jane Doe"
    assert document.contact.title == "IT Support Engineer"
    assert document.contact.email == "jane@example.com"
    assert document.contact.location == "Berlin, Germany"
    assert document.profile
    assert document.skills[0].label == "End-user Support"
    assert document.experience[0].title == "IT Support Engineer"
    assert document.experience[0].organization == (
        "Example GmbH, Berlin"
    )
    assert document.experience[0].dates == "Oct 2023 - Present"
    assert document.projects
    assert document.education[0].credential == "BSc Computer Science"
    assert document.certifications
    assert document.languages == ["English: C2 | German: B2"]
    assert validate_resume_document(document) == []


def test_resume_docx_uses_approved_layout():
    document = parse_resume(RESUME_TEXT, source_text=SOURCE_TEXT)
    content = render_resume_docx(document)
    assert content.startswith(b"PK")

    parsed = DocxDocument(BytesIO(content))
    section = parsed.sections[0]
    assert round(section.page_width.mm) == 210
    assert round(section.page_height.mm) == 297

    paragraphs = [p for p in parsed.paragraphs if p.text.strip()]
    assert paragraphs[0].text == "JANE DOE"
    assert paragraphs[0].alignment == 1
    assert paragraphs[0].runs[0].font.name == "Calibri"
    assert paragraphs[0].runs[0].font.size.pt == 15

    headings = [
        p for p in paragraphs
        if p.text in {
            "PROFILE",
            "CORE SKILLS",
            "EXPERIENCE",
            "PROJECTS & LABS",
            "EDUCATION & CERTIFICATIONS",
            "LANGUAGES",
        }
    ]
    assert [p.text for p in headings] == [
        "PROFILE",
        "CORE SKILLS",
        "EXPERIENCE",
        "PROJECTS & LABS",
        "EDUCATION & CERTIFICATIONS",
        "LANGUAGES",
    ]
    for heading in headings:
        assert heading.runs[0].bold is True
        assert str(heading.runs[0].font.color.rgb) == "1F4E79"
        assert "w:pBdr" in heading._p.pPr.xml

    body = "\n".join(p.text for p in paragraphs)
    assert "End-user Support: Windows 10/11" in body
    assert "Example GmbH, Berlin" in body


def test_resume_pdf_uses_approved_layout_and_fonts():
    document = parse_resume(RESUME_TEXT, source_text=SOURCE_TEXT)
    content = render_resume_pdf(document)
    assert content.startswith(b"%PDF")

    reader = PdfReader(BytesIO(content))
    assert 1 <= len(reader.pages) <= 2
    page = reader.pages[0]
    assert round(float(page.mediabox.width)) == 595
    assert round(float(page.mediabox.height)) == 842
    text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    for expected in (
        "JANE DOE",
        "PROFILE",
        "CORE SKILLS",
        "EXPERIENCE",
        "PROJECTS & LABS",
        "EDUCATION & CERTIFICATIONS",
        "LANGUAGES",
    ):
        assert expected in text
    fonts = page["/Resources"]["/Font"]
    font_names = {
        str(fonts[key].get_object().get("/BaseFont", ""))
        for key in fonts
    }
    assert any("Carlito" in name for name in font_names)


def test_cover_letter_docx_uses_serif_template():
    document = parse_cover_letter(
        COVER_TEXT, source_text=SOURCE_TEXT
    )
    assert validate_cover_letter_document(document) == []
    content = render_cover_letter_docx(document)
    parsed = DocxDocument(BytesIO(content))
    paragraphs = [p for p in parsed.paragraphs if p.text.strip()]
    assert paragraphs[0].text == "Jane Doe"
    assert paragraphs[0].runs[0].font.name == "Times New Roman"
    assert paragraphs[0].runs[0].font.size.pt == 12
    assert any(p.text == "Dear Hiring Team," for p in paragraphs)
    assert any(p.text == "Sincerely," for p in paragraphs)
    assert paragraphs[-1].text == "Jane Doe"


def test_cover_letter_pdf_uses_serif_template():
    document = parse_cover_letter(
        COVER_TEXT, source_text=SOURCE_TEXT
    )
    content = render_cover_letter_pdf(document)
    assert content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(content))
    assert 1 <= len(reader.pages) <= 2
    page = reader.pages[0]
    assert round(float(page.mediabox.width)) == 595
    assert round(float(page.mediabox.height)) == 842
    text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    assert "Jane Doe" in text
    assert "Dear Hiring Team," in text
    assert "Sincerely," in text
    fonts = page["/Resources"]["/Font"]
    font_names = {
        str(fonts[key].get_object().get("/BaseFont", ""))
        for key in fonts
    }
    assert any("LiberationSerif" in name for name in font_names)


def test_validation_reports_missing_sections_and_placeholders():
    resume = parse_resume(
        "Jane Doe\n[Email]\n\nPROFILE\nProfile text.",
        source_text="Jane Doe\n",
    )
    codes = {issue.code for issue in validate_resume_document(resume)}
    assert "missing_contact" in codes
    assert "missing_skills" in codes
    assert "missing_experience" in codes
    assert "missing_education" in codes
    assert "placeholder_text" in codes

    cover = parse_cover_letter(
        "Hello,\n\n[Company] is a great place to work.",
        source_text="Jane Doe\n",
    )
    codes = {
        issue.code for issue in validate_cover_letter_document(cover)
    }
    assert "missing_contact" in codes
    assert "placeholder_text" in codes


import re
from pathlib import Path

REFERENCE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "reference_templates"
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _docx_text(content: bytes) -> str:
    parsed = DocxDocument(BytesIO(content))
    return "\n".join(p.text for p in parsed.paragraphs)


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_renderer_keeps_users_separate():
    alice_source = (
        "Alice Alpha\nBerlin, Germany\nalice@example.com\n+49 111 111111\n"
    )
    alice_resume = """Alice Alpha
IT Support Engineer
Berlin, Germany | alice@example.com | +49 111 111111

PROFILE
Alice supports Alpha Corp users.

CORE SKILLS
Support: Windows and Microsoft 365.

EXPERIENCE
IT Support Engineer | Alpha Corp, Berlin Jan 2020 - Present
- Supported Alpha Corp staff.

EDUCATION
BSc Computing | Alpha University, Berlin Sep 2015 - Jun 2019
"""
    bob_source = (
        "Bob Beta\nMunich, Germany\nbob@example.com\n+49 222 222222\n"
    )
    bob_resume = """Bob Beta
Desktop Support Engineer
Munich, Germany | bob@example.com | +49 222 222222

PROFILE
Bob supports Beta Systems users.

CORE SKILLS
Support: Windows and networking.

EXPERIENCE
Desktop Support Engineer | Beta Systems, Munich Feb 2021 - Present
- Supported Beta Systems staff.

EDUCATION
BSc Networking | Beta University, Munich Sep 2016 - Jun 2020
"""
    alice_cover = """Dear Hiring Team,

I am applying because my verified experience at Alpha Corp matches this role.

I support Windows users and document resolutions clearly.

Sincerely,
Alice Alpha
"""
    bob_cover = """Dear Hiring Team,

I am applying because my verified experience at Beta Systems matches this role.

I support Windows users and document resolutions clearly.

Sincerely,
Bob Beta
"""

    def rendered_for(resume_text, cover_text, source_text):
        resume = parse_resume(resume_text, source_text=source_text)
        cover = parse_cover_letter(cover_text, source_text=source_text)
        return _normalize(
            "\n".join(
                [
                    _docx_text(render_resume_docx(resume)),
                    _pdf_text(render_resume_pdf(resume)),
                    _docx_text(render_cover_letter_docx(cover)),
                    _pdf_text(render_cover_letter_pdf(cover)),
                ]
            )
        )

    alice_rendered = rendered_for(
        alice_resume, alice_cover, alice_source
    )
    bob_rendered = rendered_for(bob_resume, bob_cover, bob_source)

    assert "Alice Alpha" in alice_rendered
    assert "alice@example.com" in alice_rendered
    assert "Alpha Corp" in alice_rendered
    assert "Bob Beta" not in alice_rendered
    assert "bob@example.com" not in alice_rendered

    assert "Bob Beta" in bob_rendered
    assert "bob@example.com" in bob_rendered
    assert "Beta Systems" in bob_rendered
    assert "Alice Alpha" not in bob_rendered
    assert "alice@example.com" not in bob_rendered
    assert "Alpha Corp" not in bob_rendered
    assert "Alpha University" not in bob_rendered


def test_reference_pdf_personal_data_does_not_leak():
    cv_reference = REFERENCE_DIR / "sanitized-reference-cv.pdf"
    cover_reference = (
        REFERENCE_DIR / "sanitized-reference-cover-letter.pdf"
    )
    assert cv_reference.is_file()
    assert cover_reference.is_file()

    profiles = [
        ("Alice Alpha", "alice@example.com", "+49 111 111111", "Berlin", "Alpha Corp", "Alpha University"),
        ("Bob Beta", "bob@example.com", "+49 222 222222", "Munich", "Beta Systems", "Beta University"),
        ("Casey Candidate", "casey@example.com", "+49 333 333333", "Hamburg", "Gamma GmbH", "Gamma University"),
    ]

    def profile_documents(name, email, phone, city, employer, university):
        source = f"{name}\n{city}, Germany\n{email}\n{phone}\n"
        resume = f"""{name}
IT Support Engineer
{city}, Germany | {email} | {phone}

PROFILE
{name} provides verified support for {employer} users.

CORE SKILLS
Support: Windows, Microsoft 365 and networking.

EXPERIENCE
IT Support Engineer | {employer}, {city} Mar 2022 - Present
- Supported {employer} users.

EDUCATION
BSc IT | {university}, {city} Sep 2017 - Jun 2021
"""
        cover = f"""Dear Hiring Team,

I am applying because my verified {employer} experience fits this role.

I support users and document resolutions clearly.

Sincerely,
{name}
"""
        return source, resume, cover

    reference_text = "\n".join(
        [
            _pdf_text(cv_reference.read_bytes()),
            _pdf_text(cover_reference.read_bytes()),
        ]
    )
    reference_lines = [
        _normalize(line)
        for line in reference_text.splitlines()
        if line.strip()
    ]
    markers: set[str] = set()
    if reference_lines:
        markers.add(reference_lines[0])
    markers.update(
        match.group(0)
        for match in re.finditer(
            r"[\w.+-]+@[\w.-]+\.\w+", reference_text
        )
    )
    markers.update(
        _normalize(match.group(0))
        for match in re.finditer(
            r"\+?\d[\d\s().-]{6,}\d", reference_text
        )
    )
    markers.update(
        match.group(0)
        for match in re.finditer(
            r"(?:linkedin\.com/\S+|github\.com/\S+)",
            reference_text,
            re.IGNORECASE,
        )
    )
    personal_markers = {
        marker
        for marker in markers
        if len(marker) >= 4 and marker.lower() not in {"profile"}
    }
    assert personal_markers
    sanitized_sentinels = {
        "Reference Employer LLC",
        "Reference University",
        "reference.person@example.test",
        "+49 000 000000",
    }

    for name, email, phone, city, employer, university in profiles:
        source, resume_text, cover_text = profile_documents(
            name, email, phone, city, employer, university
        )
        resume = parse_resume(resume_text, source_text=source)
        cover = parse_cover_letter(cover_text, source_text=source)
        generated = _normalize(
            "\n".join(
                [
                    _docx_text(render_resume_docx(resume)),
                    _pdf_text(render_resume_pdf(resume)),
                    _docx_text(render_cover_letter_docx(cover)),
                    _pdf_text(render_cover_letter_pdf(cover)),
                ]
            )
        )
        assert name in generated
        assert email in generated
        for marker in personal_markers | sanitized_sentinels:
            assert marker not in generated

def test_source_contact_overrides_ai_header_contact():
    ai_text = """Jane Doe
IT Support Engineer
leak@example.com | +49 999 999999

PROFILE
Verified profile content.

CORE SKILLS
Support: Windows.

EXPERIENCE
IT Support Engineer | Example GmbH, Berlin Jan 2020 - Present
- Supported users.

EDUCATION
BSc IT | Example University, Berlin Sep 2015 - Jun 2019
"""
    source_text = (
        "Jane Doe\nBerlin, Germany\njane@example.com\n+49 123 456789\n"
    )
    document = parse_resume(ai_text, source_text=source_text)
    rendered = _normalize(
        "\n".join(
            [
                _docx_text(render_resume_docx(document)),
                _pdf_text(render_resume_pdf(document)),
            ]
        )
    )
    assert "jane@example.com" in rendered
    assert "+49 123 456789" in rendered
    assert "leak@example.com" not in rendered
    assert "+49 999 999999" not in rendered
