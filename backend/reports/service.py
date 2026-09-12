"""Summary + PDF builder wrappers for the reports module."""

from __future__ import annotations

from reports import models as report_models


class ReportBuildError(Exception):
    """Raised when the PDF backend dependency is missing or generation fails."""


def require_reportlab():
    try:
        import reportlab  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ReportBuildError(
            "Server-side PDF generation is unavailable: the 'reportlab' "
            "dependency is not installed. Install it with "
            "`pip install reportlab`."
        ) from exc


def build_pdf_bytes(
    metadata: report_models.ReportMetadata, context: dict
) -> bytes:
    """Render selected sections to a PDF byte stream."""
    require_reportlab()

    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"CryptoTrace report - {metadata.case_name}",
        author=metadata.investigator or "CryptoTrace",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CryptoTraceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "CryptoTraceSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#1a2b4a"),
        spaceBefore=14,
        spaceAfter=4,
    )
    body = styles["BodyText"]

    story = [
        Paragraph("CryptoTrace - Investigation Report", title_style),
        Paragraph(
            f"Case: {metadata.case_name}<br/>"
            f"Primary wallet: {metadata.primary_wallet or 'UNAVAILABLE'}<br/>"
            f"Network: {metadata.network}<br/>"
            f"Investigator: {metadata.investigator or 'UNAVAILABLE'}<br/>"
            f"Generated: {metadata.generated_at or 'UNAVAILABLE'}<br/>"
            f"Classification: {metadata.classification}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]

    sections = []
    for key in report_models.REPORT_SECTIONS:
        if key in context.get("selected_sections", []) or not context.get(
            "selected_sections"
        ):
            sections.append(key)

    rendered = 0
    for key in sections:
        if key not in report_models._SECTION_TITLES:
            continue
        content = report_models.build_section_content(key, context)
        story.append(Paragraph(report_models._SECTION_TITLES[key], section_style))
        for para in content.split("\n\n"):
            text = para.replace("\n", "<br/>")
            if not text.strip():
                continue
            story.append(Paragraph(text, body))
        rendered += 1

    doc.build(story)
    return buffer.getvalue(), rendered