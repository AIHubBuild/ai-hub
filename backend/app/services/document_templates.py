"""DOCX and PDF renderers for the approved CV and cover-letter designs."""

from io import BytesIO
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.services.document_content import (
    ContactInfo,
    CoverLetterDocument,
    ResumeDocument,
)

BLUE = "#1F4E79"
DOCX_CV_FONT = "Calibri"
DOCX_COVER_FONT = "Times New Roman"
PDF_CV_FONT = "Carlito"
PDF_COVER_FONT = "LiberationSerif"

_FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_FONT_FILES = {
    "Carlito": "Carlito-Regular.ttf",
    "Carlito-Bold": "Carlito-Bold.ttf",
    "Carlito-Italic": "Carlito-Italic.ttf",
    "Carlito-BoldItalic": "Carlito-BoldItalic.ttf",
    "LiberationSerif": "LiberationSerif-Regular.ttf",
    "LiberationSerif-Bold": "LiberationSerif-Bold.ttf",
    "LiberationSerif-Italic": "LiberationSerif-Italic.ttf",
    "LiberationSerif-BoldItalic": "LiberationSerif-BoldItalic.ttf",
}


@lru_cache(maxsize=1)
def _register_pdf_fonts() -> None:
    for font_name, filename in _FONT_FILES.items():
        path = _FONT_DIR / filename
        if not path.is_file():
            raise RuntimeError(f"Required PDF font is missing: {filename}")
        pdfmetrics.registerFont(TTFont(font_name, str(path)))
    pdfmetrics.registerFontFamily(
        "Carlito",
        normal="Carlito",
        bold="Carlito-Bold",
        italic="Carlito-Italic",
        boldItalic="Carlito-BoldItalic",
    )
    pdfmetrics.registerFontFamily(
        "LiberationSerif",
        normal="LiberationSerif",
        bold="LiberationSerif-Bold",
        italic="LiberationSerif-Italic",
        boldItalic="LiberationSerif-BoldItalic",
    )


def _pdf_styles() -> dict[str, ParagraphStyle]:
    _register_pdf_fonts()
    return {
        "name": ParagraphStyle(
            "CvName",
            fontName="Carlito-Bold",
            fontSize=15,
            leading=17,
            alignment=TA_CENTER,
            spaceAfter=1,
        ),
        "title": ParagraphStyle(
            "CvTitle",
            fontName="Carlito-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor(BLUE),
            spaceAfter=1,
        ),
        "contact": ParagraphStyle(
            "CvContact",
            fontName="Carlito",
            fontSize=10,
            leading=11.5,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "heading": ParagraphStyle(
            "CvHeading",
            fontName="Carlito-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor(BLUE),
            spaceBefore=7,
            spaceAfter=1,
            keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "CvBody",
            fontName="Carlito",
            fontSize=10,
            leading=11.5,
            spaceAfter=1.5,
        ),
        "bullet": ParagraphStyle(
            "CvBullet",
            fontName="Carlito",
            fontSize=10,
            leading=11.5,
            leftIndent=12,
            bulletIndent=2,
            spaceAfter=1.2,
        ),
        "cover_contact": ParagraphStyle(
            "CoverContact",
            fontName="LiberationSerif",
            fontSize=12,
            leading=15,
            alignment=TA_LEFT,
        ),
        "cover_greeting": ParagraphStyle(
            "CoverGreeting",
            fontName="LiberationSerif",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=9,
        ),
        "cover_body": ParagraphStyle(
            "CoverBody",
            fontName="LiberationSerif",
            fontSize=12,
            leading=14.4,
            spaceAfter=9,
        ),
        "cover_close": ParagraphStyle(
            "CoverClose",
            fontName="LiberationSerif",
            fontSize=12,
            leading=15,
            spaceBefore=4,
        ),
    }


def _xml_escape(value: str) -> str:
    return escape(value)


def _pdf_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_xml_escape(text), style)


def _pdf_heading(text: str, styles: dict[str, ParagraphStyle]):
    heading = _pdf_paragraph(text.upper(), styles["heading"])
    rule = HRFlowable(
        width="100%",
        thickness=0.75,
        color=colors.HexColor(BLUE),
        spaceBefore=0,
        spaceAfter=4,
    )
    return KeepTogether([heading, rule])


def _docx_set_run(
    run,
    *,
    font: str,
    size: int,
    bold: bool = False,
    italic: bool = False,
    color: str | None = None,
) -> None:
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:eastAsia"), font)


def _docx_paragraph(
    document,
    *,
    text: str = "",
    font: str,
    size: int,
    bold: bool = False,
    italic: bool = False,
    color: str | None = None,
    align=None,
    space_before: int = 0,
    space_after: int = 0,
    line_spacing: float | None = None,
):
    paragraph = document.add_paragraph()
    if align is not None:
        paragraph.alignment = align
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.space_after = Pt(space_after)
    if line_spacing is not None:
        paragraph.paragraph_format.line_spacing = line_spacing
    if text:
        run = paragraph.add_run(text)
        _docx_set_run(
            run,
            font=font,
            size=size,
            bold=bold,
            italic=italic,
            color=color,
        )
    return paragraph


def _docx_bottom_border(paragraph, color: str = BLUE) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color.lstrip("#"))
    pbdr.append(bottom)


def _docx_heading(document, text: str, font: str):
    paragraph = _docx_paragraph(
        document,
        text=text.upper(),
        font=font,
        size=12,
        bold=True,
        color=BLUE,
        space_before=7,
        space_after=2,
        line_spacing=1.0,
    )
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.keep_together = True
    _docx_bottom_border(paragraph)
    return paragraph


def _docx_bullet(document, text: str, font: str):
    paragraph = document.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.left_indent = Mm(4.8)
    paragraph.paragraph_format.first_line_indent = Mm(-3.2)
    paragraph.paragraph_format.space_after = Pt(1.2)
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run(text)
    _docx_set_run(run, font=font, size=10)
    return paragraph


def _cv_header_lines(contact: ContactInfo) -> list[str]:
    if contact.lines:
        return contact.lines
    lines: list[str] = []
    if contact.location:
        lines.append(contact.location)
    if contact.email:
        lines.append(contact.email)
    if contact.phone:
        lines.append(contact.phone)
    if contact.links:
        lines.append(" | ".join(contact.links))
    return lines


def _cover_contact_lines(contact: ContactInfo) -> list[str]:
    return [
        value
        for value in (
            contact.name,
            contact.location,
            contact.email,
            contact.phone,
        )
        if value
    ]


def _cover_contact(doc: CoverLetterDocument) -> ContactInfo:
    if doc.contact.name:
        return doc.contact
    return ContactInfo(name=doc.signature)


def render_resume_docx(document: ResumeDocument) -> bytes:
    doc = DocxDocument()
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.left_margin = Mm(13.3)
    section.right_margin = Mm(13.3)
    section.top_margin = Mm(13.3)
    section.bottom_margin = Mm(13.3)

    normal = doc.styles["Normal"]
    normal.font.name = DOCX_CV_FONT
    normal.font.size = Pt(10)

    _docx_paragraph(
        doc,
        text=document.contact.name.upper(),
        font=DOCX_CV_FONT,
        size=15,
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=1,
    )
    if document.contact.title:
        _docx_paragraph(
            doc,
            text=document.contact.title,
            font=DOCX_CV_FONT,
            size=10,
            bold=True,
            color=BLUE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    for line in _cv_header_lines(document.contact):
        _docx_paragraph(
            doc,
            text=line,
            font=DOCX_CV_FONT,
            size=10,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    if document.profile:
        _docx_heading(doc, "Profile", DOCX_CV_FONT)
        for paragraph in document.profile:
            _docx_paragraph(
                doc, text=paragraph, font=DOCX_CV_FONT, size=10
            )

    if document.skills:
        _docx_heading(doc, "Core Skills", DOCX_CV_FONT)
        for group in document.skills:
            if group.label:
                paragraph = doc.add_paragraph()
                paragraph.paragraph_format.space_after = Pt(1.5)
                paragraph.paragraph_format.line_spacing = 1.0
                label = paragraph.add_run(f"{group.label}: ")
                _docx_set_run(
                    label, font=DOCX_CV_FONT, size=10, bold=True
                )
                value = paragraph.add_run(group.text)
                _docx_set_run(value, font=DOCX_CV_FONT, size=10)
            else:
                _docx_paragraph(
                    doc, text=group.text, font=DOCX_CV_FONT, size=10
                )

    if document.experience:
        _docx_heading(doc, "Experience", DOCX_CV_FONT)
        for entry in document.experience:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(4)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.line_spacing = 1.0
            title = paragraph.add_run(entry.title)
            _docx_set_run(
                title, font=DOCX_CV_FONT, size=10, bold=True
            )
            if entry.organization:
                org = paragraph.add_run(f" / {entry.organization}")
                _docx_set_run(
                    org, font=DOCX_CV_FONT, size=10, italic=True
                )
            if entry.dates:
                dates = paragraph.add_run(f" {entry.dates}")
                _docx_set_run(
                    dates, font=DOCX_CV_FONT, size=10, bold=True
                )
            for bullet in entry.bullets:
                _docx_bullet(doc, bullet, DOCX_CV_FONT)

    if document.projects:
        _docx_heading(doc, "Projects & Labs", DOCX_CV_FONT)
        for project in document.projects:
            _docx_bullet(doc, project, DOCX_CV_FONT)

    if document.education or document.certifications:
        _docx_heading(
            doc, "Education & Certifications", DOCX_CV_FONT
        )
        for entry in document.education:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(3)
            paragraph.paragraph_format.space_after = Pt(1)
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.line_spacing = 1.0
            credential = paragraph.add_run(entry.credential)
            _docx_set_run(
                credential, font=DOCX_CV_FONT, size=10, bold=True
            )
            if entry.institution:
                institution = paragraph.add_run(
                    f" | {entry.institution}"
                )
                _docx_set_run(
                    institution, font=DOCX_CV_FONT, size=10
                )
            if entry.dates:
                dates = paragraph.add_run(f" {entry.dates}")
                _docx_set_run(
                    dates, font=DOCX_CV_FONT, size=10, bold=True
                )
            for detail in entry.details:
                _docx_bullet(doc, detail, DOCX_CV_FONT)
        for certification in document.certifications:
            _docx_paragraph(
                doc,
                text=certification,
                font=DOCX_CV_FONT,
                size=10,
            )

    if document.languages:
        _docx_heading(doc, "Languages", DOCX_CV_FONT)
        _docx_paragraph(
            doc,
            text=" | ".join(document.languages),
            font=DOCX_CV_FONT,
            size=10,
        )

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def render_cover_letter_docx(document: CoverLetterDocument) -> bytes:
    doc = DocxDocument()
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.left_margin = Mm(25.4)
    section.right_margin = Mm(25.4)
    section.top_margin = Mm(25.4)
    section.bottom_margin = Mm(25.4)

    normal = doc.styles["Normal"]
    normal.font.name = DOCX_COVER_FONT
    normal.font.size = Pt(12)

    for line in _cover_contact_lines(_cover_contact(document)):
        _docx_paragraph(
            doc,
            text=line,
            font=DOCX_COVER_FONT,
            size=12,
            line_spacing=1.15,
        )
    _docx_paragraph(
        doc, font=DOCX_COVER_FONT, size=12, space_after=0
    )
    _docx_paragraph(
        doc,
        text=document.greeting,
        font=DOCX_COVER_FONT,
        size=12,
        space_after=8,
    )
    for paragraph in document.paragraphs:
        _docx_paragraph(
            doc,
            text=paragraph,
            font=DOCX_COVER_FONT,
            size=12,
            space_after=8,
            line_spacing=1.15,
        )
    closing = _docx_paragraph(
        doc,
        text=document.closing,
        font=DOCX_COVER_FONT,
        size=12,
        space_before=4,
    )
    closing.paragraph_format.keep_with_next = True
    signature = _docx_paragraph(
        doc,
        text=document.signature,
        font=DOCX_COVER_FONT,
        size=12,
    )
    signature.paragraph_format.keep_together = True

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def render_resume_pdf(document: ResumeDocument) -> bytes:
    styles = _pdf_styles()
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=37.65,
        rightMargin=37.65,
        topMargin=37.65,
        bottomMargin=37.65,
        title=f"{document.contact.name or 'CV'} CV",
    )
    story = [
        _pdf_paragraph(
            document.contact.name.upper(), styles["name"]
        )
    ]
    if document.contact.title:
        story.append(
            _pdf_paragraph(document.contact.title, styles["title"])
        )
    header_lines = _cv_header_lines(document.contact)
    if header_lines:
        story.append(
            Paragraph(
                "<br/>".join(_xml_escape(line) for line in header_lines),
                styles["contact"],
            )
        )

    if document.profile:
        story.append(_pdf_heading("Profile", styles))
        for paragraph in document.profile:
            story.append(_pdf_paragraph(paragraph, styles["body"]))

    if document.skills:
        story.append(_pdf_heading("Core Skills", styles))
        for group in document.skills:
            if group.label:
                story.append(
                    Paragraph(
                        f"<b>{_xml_escape(group.label)}:</b> "
                        f"{_xml_escape(group.text)}",
                        styles["body"],
                    )
                )
            else:
                story.append(
                    Paragraph(
                        _xml_escape(group.text),
                        styles["bullet"],
                        bulletText="•",
                    )
                )

    if document.experience:
        story.append(_pdf_heading("Experience", styles))
        for entry in document.experience:
            parts = [f"<b>{_xml_escape(entry.title)}</b>"]
            if entry.organization:
                parts.append(
                    f"/ <i>{_xml_escape(entry.organization)}</i>"
                )
            if entry.dates:
                parts.append(f"<b>{_xml_escape(entry.dates)}</b>")
            header = Paragraph(
                " ".join(parts),
                styles["body"],
            )
            bullets = [
                Paragraph(
                    _xml_escape(bullet),
                    styles["bullet"],
                    bulletText="•",
                )
                for bullet in entry.bullets
            ]
            story.append(
                KeepTogether([header, *bullets])
                if bullets
                else header
            )

    if document.projects:
        story.append(_pdf_heading("Projects & Labs", styles))
        for project in document.projects:
            story.append(
                Paragraph(
                    _xml_escape(project),
                    styles["bullet"],
                    bulletText="•",
                )
            )

    if document.education or document.certifications:
        story.append(
            _pdf_heading("Education & Certifications", styles)
        )
        for entry in document.education:
            parts = [f"<b>{_xml_escape(entry.credential)}</b>"]
            if entry.institution:
                parts.append(
                    f"| {_xml_escape(entry.institution)}"
                )
            if entry.dates:
                parts.append(f"<b>{_xml_escape(entry.dates)}</b>")
            details = [
                Paragraph(
                    _xml_escape(detail),
                    styles["bullet"],
                    bulletText="•",
                )
                for detail in entry.details
            ]
            story.append(
                KeepTogether(
                    [
                        Paragraph(" ".join(parts), styles["body"]),
                        *details,
                    ]
                )
            )
        for certification in document.certifications:
            story.append(
                _pdf_paragraph(certification, styles["body"])
            )

    if document.languages:
        story.append(_pdf_heading("Languages", styles))
        story.append(
            _pdf_paragraph(" | ".join(document.languages), styles["body"])
        )

    pdf.build(story)
    return buffer.getvalue()


def render_cover_letter_pdf(document: CoverLetterDocument) -> bytes:
    styles = _pdf_styles()
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=72,
        rightMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=f"{document.signature or document.contact.name} Cover Letter",
    )
    story = []
    for line in _cover_contact_lines(_cover_contact(document)):
        story.append(
            _pdf_paragraph(line, styles["cover_contact"])
        )
    story.append(Spacer(1, 8))
    story.append(
        _pdf_paragraph(document.greeting, styles["cover_greeting"])
    )
    for paragraph in document.paragraphs:
        story.append(
            _pdf_paragraph(paragraph, styles["cover_body"])
        )
    story.append(
        KeepTogether(
            [
                _pdf_paragraph(document.closing, styles["cover_close"]),
                Spacer(1, 2),
                _pdf_paragraph(
                    document.signature, styles["cover_contact"]
                ),
            ]
        )
    )
    pdf.build(story)
    return buffer.getvalue()
