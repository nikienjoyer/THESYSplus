"""Tests for the optional page limit on ThesisTextExtractor.

The regression this guards against is the DEFAULT changing. ``max_pages``
defaults to ``None`` (unlimited) precisely so ``ThesisUploadView`` Step 6 keeps
storing the FULL document in ``Thesis.extracted_text`` — semantic search and
redundancy analysis depend on that. A front-matter limit leaking into the
default would silently truncate every uploaded thesis to its first few pages.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from theses.services import text_extractor as te
from theses.services.text_extractor import (
    FRONT_MATTER_PAGES,
    OCR_MAX_PAGES,
    ThesisTextExtractor,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _multipage_pdf(page_texts: list[str]) -> bytes:
    """Build a minimal valid multi-page PDF, one text line per page."""
    n = len(page_texts)
    # Object ids: 1 = catalog, 2 = page tree, then (page, content) pairs.
    page_ids = [3 + 2 * i for i in range(n)]
    content_ids = [4 + 2 * i for i in range(n)]

    offsets: dict[int, int] = {}
    out = bytearray(b'%PDF-1.4\n')

    def emit(obj_id: int, payload: bytes) -> None:
        offsets[obj_id] = len(out)
        out.extend(payload)

    emit(1, b'1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n')

    kids = ' '.join(f'{pid} 0 R' for pid in page_ids)
    emit(2, f'2 0 obj <</Type /Pages /Count {n} /Kids [{kids}]>> endobj\n'.encode())

    for pid, cid, text in zip(page_ids, content_ids, page_texts):
        emit(pid, (
            f'{pid} 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            f'/Contents {cid} 0 R /Resources <</Font <</F1 <</Type /Font '
            f'/Subtype /Type1 /BaseFont /Helvetica>>>>>>>> endobj\n'
        ).encode())

        safe = (text.replace('\\', '\\\\')
                    .replace('(', '\\(')
                    .replace(')', '\\)'))
        stream = f'BT /F1 12 Tf 50 750 Td ({safe}) Tj ET'.encode('latin-1', 'replace')
        emit(cid, (
            f'{cid} 0 obj <</Length {len(stream)}>>\nstream\n'.encode()
            + stream
            + b'\nendstream endobj\n'
        ))

    max_id = max(offsets)
    xref_off = len(out)
    out.extend(f'xref\n0 {max_id + 1}\n'.encode())
    out.extend(b'0000000000 65535 f \n')
    for obj_id in range(1, max_id + 1):
        out.extend(f'{offsets[obj_id]:010d} 00000 n \n'.encode())
    out.extend(
        f'trailer <</Size {max_id + 1} /Root 1 0 R>>\nstartxref\n{xref_off}\n'.encode()
        + b'%%EOF\n'
    )
    return bytes(out)


def _docx(paragraphs: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org'
            '/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.'
            'openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        zf.writestr(
            '_rels/.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org'
            '/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        para_xml = ''.join(
            f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs
        )
        zf.writestr(
            'word/document.xml',
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
            'openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{para_xml}</w:body></w:document>',
        )
        zf.writestr(
            'word/_rels/document.xml.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"/>',
        )
    return buf.getvalue()


# 12 pages, each carrying enough text to clear PDF_TEXT_FALLBACK_THRESHOLD
# once a couple of pages are read, so OCR never engages in these tests.
PAGE_TEXTS = [
    f'Page {i} sentinel content for the page limit regression suite, '
    f'padded so the extracted text is comfortably long. Marker PAGE{i}END.'
    for i in range(1, 13)
]


@pytest.fixture
def pdf_path(tmp_path):
    p = tmp_path / 'twelve_pages.pdf'
    p.write_bytes(_multipage_pdf(PAGE_TEXTS))
    return str(p)


@pytest.fixture
def docx_path(tmp_path):
    p = tmp_path / 'sample.docx'
    p.write_bytes(_docx([
        'A MOBILE HEALTH RECORDS SYSTEM',
        'FOR RURAL CLINICS',
        'Body paragraph one.',
        'Body paragraph two.',
    ]))
    return str(p)


# ---------------------------------------------------------------------------
# The default must stay unlimited
# ---------------------------------------------------------------------------

class TestDefaultIsUnlimited:
    def test_no_argument_reads_every_page(self, pdf_path):
        result = ThesisTextExtractor().extract(pdf_path)

        assert result.success
        assert result.method == 'pypdf'
        for i in range(1, 13):
            assert f'PAGE{i}END' in result.text

    def test_explicit_none_matches_no_argument_byte_for_byte(self, pdf_path):
        extractor = ThesisTextExtractor()

        assert (
            extractor.extract(pdf_path, max_pages=None).text
            == extractor.extract(pdf_path).text
        )

    def test_signature_default_is_none(self):
        """Pin the default in the signature itself, not just its behaviour."""
        import inspect

        sig = inspect.signature(ThesisTextExtractor.extract)
        param = sig.parameters['max_pages']

        assert param.default is None
        assert param.kind is inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# Limiting
# ---------------------------------------------------------------------------

class TestPageLimit:
    def test_limit_truncates_to_leading_pages(self, pdf_path):
        result = ThesisTextExtractor().extract(pdf_path, max_pages=3)

        assert result.success
        assert 'PAGE1END' in result.text
        assert 'PAGE3END' in result.text
        assert 'PAGE4END' not in result.text
        assert 'PAGE12END' not in result.text

    def test_front_matter_constant_limits_to_five_pages(self, pdf_path):
        assert FRONT_MATTER_PAGES == 5
        result = ThesisTextExtractor().extract(pdf_path, max_pages=FRONT_MATTER_PAGES)

        assert 'PAGE5END' in result.text
        assert 'PAGE6END' not in result.text

    def test_limit_larger_than_document_is_harmless(self, pdf_path):
        extractor = ThesisTextExtractor()

        assert (
            extractor.extract(pdf_path, max_pages=500).text
            == extractor.extract(pdf_path).text
        )

    @pytest.mark.parametrize('bad', [0, -1, -50])
    def test_non_positive_limit_falls_back_to_unlimited(self, pdf_path, bad):
        """A caller passing 0 must not silently get an empty extraction."""
        extractor = ThesisTextExtractor()
        result = extractor.extract(pdf_path, max_pages=bad)

        assert result.success
        assert result.text == extractor.extract(pdf_path).text


# ---------------------------------------------------------------------------
# DOCX ignores the limit
# ---------------------------------------------------------------------------

class TestDocxIgnoresLimit:
    def test_docx_text_identical_with_and_without_limit(self, docx_path):
        """.docx has no page boundaries to slice — pagination is a render-time
        property, so the limit is documented as ignored rather than faked."""
        extractor = ThesisTextExtractor()

        limited = extractor.extract(docx_path, max_pages=1)
        full = extractor.extract(docx_path)

        assert limited.success
        assert limited.method == 'python_docx'
        assert limited.text == full.text
        assert 'Body paragraph two.' in limited.text


# ---------------------------------------------------------------------------
# OCR path — the memory-bounded one
# ---------------------------------------------------------------------------

class TestOcrPageCeiling:
    """_ocr_pdf must respect the limit, and OCR_MAX_PAGES must stay a ceiling.

    Rasterising at 200 dpi costs roughly 12 MB per page, so this is where the
    limit actually buys something.
    """

    @pytest.fixture
    def captured(self, monkeypatch):
        calls: list[dict] = []

        def fake_convert_from_path(path, **kwargs):
            calls.append(kwargs)
            return []

        import pdf2image
        monkeypatch.setattr(pdf2image, 'convert_from_path', fake_convert_from_path)

        import identity_verification.services.ocr_extractor as ocr_mod
        monkeypatch.setattr(ocr_mod.OCRExtractor, '_tesseract_configured', True)
        return calls

    @pytest.mark.parametrize('max_pages, expected_last_page', [
        (None, OCR_MAX_PAGES),          # unchanged legacy behaviour
        (FRONT_MATTER_PAGES, 5),        # front-matter callers
        (1, 1),
        (OCR_MAX_PAGES + 150, OCR_MAX_PAGES),   # ceiling cannot be raised
    ])
    def test_last_page_passed_to_pdf2image(
        self, captured, tmp_path, max_pages, expected_last_page,
    ):
        target = tmp_path / 'scanned.pdf'
        target.write_bytes(b'%PDF-1.4\n%%EOF\n')

        text = ThesisTextExtractor()._ocr_pdf(target, max_pages=max_pages)

        assert text == ''
        assert len(captured) == 1
        assert captured[0]['last_page'] == expected_last_page
        assert captured[0]['first_page'] == 1
        assert captured[0]['dpi'] == 200

    def test_ocr_ceiling_is_fifty(self):
        assert OCR_MAX_PAGES == 50


# ---------------------------------------------------------------------------
# The upload pipeline still asks for the full document
# ---------------------------------------------------------------------------

class TestUploadPipelineStillUnlimited:
    def test_upload_view_passes_no_page_limit(self):
        """ThesisUploadView must never page-limit — extracted_text feeds search.

        Asserted against the source so a future edit that adds max_pages to
        that call site fails loudly here.

        The call moved ahead of ``Thesis.objects.create()`` when the
        document-type gate landed: the bytes are written to a temp file and
        parsed there, so a rejected upload leaves no row and no stored file
        behind. The text is then reused as ``extracted_text``, so there is
        still exactly one full parse per upload.
        """
        import inspect

        from theses.views import ThesisUploadView

        source = inspect.getsource(ThesisUploadView.post)

        assert 'ThesisTextExtractor().extract(tmp_path)' in source, (
            'upload extract() call changed shape'
        )
        assert 'extracted_text=extracted_text' in source, (
            'the gate-time extraction must still be reused as '
            'Thesis.extracted_text — dropping it would reintroduce a second '
            'full parse, or leave the column empty.'
        )
        assert 'max_pages' not in source, (
            'ThesisUploadView must extract the FULL document; a page limit '
            'here would truncate Thesis.extracted_text and degrade semantic '
            'search and redundancy analysis.'
        )


def test_module_exposes_tunables():
    """These are imported by views; keep them public."""
    assert te.PDF_TEXT_FALLBACK_THRESHOLD == 200
    assert te.OCR_MAX_PAGES == 50
    assert te.FRONT_MATTER_PAGES == 5
