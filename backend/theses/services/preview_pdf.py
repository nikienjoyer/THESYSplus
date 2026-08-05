"""In-memory PDF rendering for the thesis previewer (``ThesisDownloadView``).

Two entry points, both returning raw PDF bytes and never touching disk:

* ``render_docx_to_pdf`` — converts a .docx file's headings/paragraphs/
  tables into a paginated PDF via reportlab, so DOCX uploads can be
  previewed inline exactly like PDF uploads.
* ``render_placeholder_pdf`` — builds a minimal PDF from a thesis's own
  metadata (title, authors, abstract, extracted text excerpt) when the
  real file is missing from disk or fails to convert. The previewer
  should never dead-end on a 404.

These PDFs are generated on the fly for preview purposes only — they are
never persisted and never replace ``Thesis.uploaded_file``.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Cap how much of Thesis.extracted_text we dump into a placeholder PDF —
# it can be very large (a full multi-chapter document) and this is only
# meant to give reviewers a usable excerpt, not a full re-render.
_PLACEHOLDER_EXCERPT_CHARS = 6000


def _escape(text: str) -> str:
    """Escape the handful of characters reportlab's mini-XML markup treats specially."""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('PreviewTitle', parent=base['Title'], fontSize=18, spaceAfter=16),
        'heading': ParagraphStyle('PreviewHeading', parent=base['Heading1'], spaceBefore=14, spaceAfter=8),
        'body': ParagraphStyle(
            'PreviewBody', parent=base['BodyText'],
            alignment=TA_JUSTIFY, leading=15, spaceAfter=8,
        ),
        'notice': ParagraphStyle(
            'PreviewNotice', parent=base['BodyText'],
            alignment=TA_CENTER, textColor='#b45309', spaceAfter=18,
        ),
        'meta': ParagraphStyle('PreviewMeta', parent=base['Normal'], alignment=TA_CENTER, spaceAfter=18),
    }


def _render(story: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        leftMargin=1 * inch, rightMargin=1 * inch,
    )
    doc.build(story)
    return buffer.getvalue()


def render_docx_to_pdf(path: str | Path) -> bytes:
    """Convert a .docx file's headings/paragraphs/tables into a PDF.

    Word paragraph styles named "Heading *" or "Title" render as section
    headings; everything else is a justified body paragraph. Raises on
    any failure (missing file, corrupt docx, empty content) — callers
    should fall back to ``render_placeholder_pdf``.
    """
    from docx import Document

    doc = Document(str(path))
    styles = _build_styles()
    story: list = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name if para.style else '') or ''
        is_heading = style_name.lower().startswith('heading') or style_name.lower() == 'title'
        story.append(Paragraph(_escape(text), styles['heading'] if is_heading else styles['body']))

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    story.append(Paragraph(_escape(cell_text), styles['body']))

    if not story:
        raise ValueError('DOCX contains no extractable content')

    return _render(story)


def render_placeholder_pdf(
    *, title: str, authors: list[str], abstract: str,
    program: str = '', year: int | None = None, extracted_text: str = '',
) -> bytes:
    """Build a metadata-only PDF when the real file can't be shown.

    Always succeeds (no external file/library dependency beyond
    reportlab itself) so the previewer never returns a broken 404.
    """
    styles = _build_styles()
    story: list = [
        Paragraph(_escape(title) or 'Untitled Thesis', styles['title']),
    ]

    meta_bits = [b for b in (program, str(year) if year else '') if b]
    if meta_bits:
        story.append(Paragraph(_escape(' · '.join(meta_bits)), styles['meta']))

    story.append(Paragraph(
        'The original document could not be loaded. Showing the thesis '
        'record’s stored metadata instead.',
        styles['notice'],
    ))

    story.append(Paragraph('Authors', styles['heading']))
    story.append(Paragraph(_escape(', '.join(authors)) or '—', styles['body']))

    story.append(Paragraph('Abstract', styles['heading']))
    story.append(Paragraph(_escape(abstract) or 'No abstract available.', styles['body']))

    excerpt = (extracted_text or '').strip()
    if excerpt:
        story.append(Spacer(1, 8))
        story.append(Paragraph('Document Text (excerpt)', styles['heading']))
        truncated = excerpt[:_PLACEHOLDER_EXCERPT_CHARS]
        if len(excerpt) > _PLACEHOLDER_EXCERPT_CHARS:
            truncated += '…'
        # Extracted text has no paragraph structure; split on blank lines
        # so it doesn't render as one giant unbroken block.
        for chunk in truncated.split('\n\n'):
            chunk = chunk.strip()
            if chunk:
                story.append(Paragraph(_escape(chunk), styles['body']))

    return _render(story)
