"""Private, on-demand watermarked page images for the thesis viewer."""

from __future__ import annotations

import io

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pdf2image import convert_from_bytes
from pypdf import PdfReader, PdfWriter

from theses.models import FileType
from theses.services.preview_pdf import render_docx_to_pdf
from theses.services.watermark_pdf import PREVIEW_WATERMARK, WATERMARK_VERSION, stamp_pdf


class InvalidPreviewPage(ValueError):
    """The requested page number is outside the document."""


def _source_pdf(thesis) -> bytes:
    if thesis.file_type != FileType.DOCX:
        with thesis.uploaded_file.open('rb') as source:
            return source.read()

    name = f'theses/_preview_sources/{thesis.id}/{thesis.sha256}.pdf'
    if default_storage.exists(name):
        try:
            with default_storage.open(name, 'rb') as cached:
                return cached.read()
        except (OSError, ValueError):
            pass

    converted = render_docx_to_pdf(thesis.uploaded_file.path)
    if not default_storage.exists(name):
        default_storage.save(name, ContentFile(converted))
    return converted


def render_preview_page(thesis, page_number: int) -> tuple[bytes, int, bool]:
    """Return JPEG bytes, total pages, and whether the image was cached."""
    source = _source_pdf(thesis)
    reader = PdfReader(io.BytesIO(source))
    if reader.is_encrypted:
        raise ValueError('Encrypted source PDF')
    total = len(reader.pages)
    if page_number < 1 or page_number > total:
        raise InvalidPreviewPage('Page is outside the document')

    name = (
        f'theses/_preview_pages/{thesis.id}/'
        f'{thesis.sha256}-v{WATERMARK_VERSION}-p{page_number}.jpg'
    )
    if default_storage.exists(name):
        try:
            with default_storage.open(name, 'rb') as cached:
                return cached.read(), total, True
        except (OSError, ValueError):
            pass

    one_page = PdfWriter()
    one_page.add_page(reader.pages[page_number - 1])
    buffer = io.BytesIO()
    one_page.write(buffer)
    marked = stamp_pdf(buffer.getvalue(), PREVIEW_WATERMARK)
    images = convert_from_bytes(marked, first_page=1, last_page=1, fmt='jpeg', size=1600)
    if not images:
        raise ValueError('The page could not be rendered')
    output = io.BytesIO()
    images[0].convert('RGB').save(output, format='JPEG', quality=82, optimize=True)
    image_bytes = output.getvalue()
    if not default_storage.exists(name):
        default_storage.save(name, ContentFile(image_bytes))
    return image_bytes, total, False
