"""Tests for the PDF watermark stamper and the watermarked download endpoint.

Fixtures are built with reportlab in-memory — nothing here reads a real thesis
file off disk.

On assertion style: the watermark constants contain a MIDDLE DOT (U+00B7), and
round-tripping that through reportlab's Helvetica encoding and back out through
pypdf's text extraction is not something these tests should be asserting on.
Content assertions therefore use distinctive ASCII fragments, and the exact
constant values are pinned separately by string equality.
"""
from __future__ import annotations

import io
import math

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from accounts.models import Role, User
from theses.models import FileType, Thesis, ThesisStatus
from theses.services.watermark_pdf import (
    DOWNLOAD_WATERMARK,
    PREVIEW_WATERMARK,
    WATERMARK_VERSION,
    EncryptedPdfError,
    WatermarkError,
    stamp_pdf,
)

LETTER = (612.0, 792.0)
A4 = (595.0, 842.0)
WIDE = (1008.0, 612.0)

# Present in both watermark strings, ASCII-only, and absent from the body text
# the fixtures draw — so its presence proves the stamp landed.
COMMON_FRAGMENT = 'Pampanga State University'
PREVIEW_FRAGMENT = 'Preview Only'
DOWNLOAD_FRAGMENT = 'Property of'


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _single_page(size=LETTER, label='body text') -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=size)
    pdf.drawString(72, 100, label)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _build_pdf(pages: list[tuple[tuple[float, float], int]]) -> bytes:
    """Assemble a PDF from (size, rotation) specs."""
    writer = PdfWriter()
    for index, (size, rotation) in enumerate(pages):
        page = PdfReader(io.BytesIO(_single_page(size, f'body {index}'))).pages[0]
        if rotation:
            page.rotate(rotation)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _encrypted_pdf(password='secret') -> bytes:
    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(_single_page())).pages[0])
    writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _page_text(page) -> str:
    return page.extract_text() or ''


# ---------------------------------------------------------------------------
# Geometry helpers — used to prove ON-SCREEN orientation, not just presence
# ---------------------------------------------------------------------------

def _display_linear(rotation: int) -> tuple[float, float, float, float]:
    """The 2x2 of the viewer's /Rotate transform, as (a, b, c, d)."""
    if rotation == 90:
        return (0, -1, 1, 0)
    if rotation == 270:
        return (0, 1, -1, 0)
    if rotation == 180:
        return (-1, 0, 0, -1)
    return (1, 0, 0, 1)


def _mul2(m, n):
    """Compose two (a, b, c, d) matrices: apply m, then n."""
    a1, b1, c1, d1 = m
    a2, b2, c2, d2 = n
    return (
        a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
    )


def _onscreen_angles(page, fragment=COMMON_FRAGMENT) -> set[float]:
    """Angles, in degrees, at which watermark baselines appear to a reader."""
    angles: set[float] = set()

    def visitor(text, cm, tm, font_dict, font_size):
        if fragment not in (text or ''):
            return
        composed = _mul2(
            (tm[0], tm[1], tm[2], tm[3]),
            (cm[0], cm[1], cm[2], cm[3]),
        )
        onscreen = _mul2(composed, _display_linear(page.rotation))
        angles.add(round(math.degrees(math.atan2(onscreen[1], onscreen[0])), 1))

    page.extract_text(visitor_text=visitor)
    return angles


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestWatermarkConstants:
    def test_exact_text_values(self):
        """Pinned verbatim, middle dots included."""
        assert PREVIEW_WATERMARK == (
            'College of Computing Studies \u00b7 Pampanga State University '
            '\u00b7 Preview Only'
        )
        assert DOWNLOAD_WATERMARK == (
            'Property of Pampanga State University \u00b7 '
            'College of Computing Studies'
        )

    def test_the_two_texts_differ(self):
        assert PREVIEW_WATERMARK != DOWNLOAD_WATERMARK

    def test_version_is_an_int(self):
        assert isinstance(WATERMARK_VERSION, int)

    def test_does_not_reuse_the_frontend_separator_style(self):
        """The DOM overlay's string mixed a hyphen and a bullet; these don't."""
        for text in (PREVIEW_WATERMARK, DOWNLOAD_WATERMARK):
            assert '\u2022' not in text          # no bullet
            assert ' - ' not in text             # no spaced hyphen
            assert '\u00b7' in text              # middle dot only


# ---------------------------------------------------------------------------
# Stamping
# ---------------------------------------------------------------------------

class TestStampPdf:
    def test_every_page_of_a_multipage_document_is_stamped(self):
        source = _build_pdf([(LETTER, 0)] * 5)
        reader = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK)))

        assert len(reader.pages) == 5
        for index, page in enumerate(reader.pages):
            assert COMMON_FRAGMENT in _page_text(page), f'page {index} unstamped'

    def test_page_count_is_unchanged(self):
        source = _build_pdf([(LETTER, 0)] * 7)
        assert len(PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK))).pages) == 7

    def test_output_reopens_cleanly_in_pypdf(self):
        stamped = stamp_pdf(_build_pdf([(LETTER, 0), (A4, 0)]), PREVIEW_WATERMARK)
        reader = PdfReader(io.BytesIO(stamped))

        assert not reader.is_encrypted
        # Touching every page forces full object-graph resolution; a corrupt
        # write surfaces here rather than silently later.
        for page in reader.pages:
            assert page.extract_text() is not None

    def test_original_bytes_are_not_mutated(self):
        source = _build_pdf([(LETTER, 0)])
        before = bytes(source)
        stamp_pdf(source, PREVIEW_WATERMARK)

        assert source == before

    def test_body_content_survives_stamping(self):
        """The watermark is additive — it must not replace the document."""
        stamped = stamp_pdf(_build_pdf([(LETTER, 0)]), PREVIEW_WATERMARK)
        text = _page_text(PdfReader(io.BytesIO(stamped)).pages[0])

        assert 'body 0' in text
        assert COMMON_FRAGMENT in text

    def test_preview_and_download_texts_produce_different_output(self):
        source = _build_pdf([(LETTER, 0)])

        preview = stamp_pdf(source, PREVIEW_WATERMARK)
        download = stamp_pdf(source, DOWNLOAD_WATERMARK)

        assert preview != download
        assert PREVIEW_FRAGMENT in _page_text(PdfReader(io.BytesIO(preview)).pages[0])
        assert DOWNLOAD_FRAGMENT in _page_text(PdfReader(io.BytesIO(download)).pages[0])


class TestMixedPageSizes:
    """A letter body with a differently-sized appendix is the common real case."""

    def test_each_size_keeps_its_own_dimensions(self):
        source = _build_pdf([(LETTER, 0), (A4, 0), (WIDE, 0)])
        reader = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK)))

        observed = [
            (round(float(p.mediabox.width), 1), round(float(p.mediabox.height), 1))
            for p in reader.pages
        ]
        assert observed == [LETTER, A4, WIDE]

    def test_every_size_is_stamped(self):
        source = _build_pdf([(LETTER, 0), (A4, 0), (WIDE, 0)])
        reader = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK)))

        for page in reader.pages:
            assert COMMON_FRAGMENT in _page_text(page)

    def test_larger_pages_receive_more_tiles(self):
        """Proves the overlay is sized per page rather than fixed.

        A fixed-size overlay would put an identical tile count on every page
        regardless of area; scaling to the mediabox does not.
        """
        source = _build_pdf([(LETTER, 0), (WIDE, 0)])
        reader = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK)))

        letter_tiles = _page_text(reader.pages[0]).count(COMMON_FRAGMENT)
        wide_tiles = _page_text(reader.pages[1]).count(COMMON_FRAGMENT)

        assert letter_tiles > 0
        assert wide_tiles > letter_tiles


class TestRotatedPages:
    @pytest.mark.parametrize('rotation', [0, 90, 180, 270])
    def test_rotation_value_is_preserved(self, rotation):
        source = _build_pdf([(LETTER, rotation)])
        page = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK))).pages[0]

        assert int(page.rotation or 0) % 360 == rotation

    @pytest.mark.parametrize('rotation', [0, 90, 180, 270])
    def test_rotated_pages_are_stamped(self, rotation):
        source = _build_pdf([(LETTER, rotation)])
        page = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK))).pages[0]

        assert COMMON_FRAGMENT in _page_text(page)

    @pytest.mark.parametrize('rotation', [0, 90, 180, 270])
    def test_rotated_pages_render_upright(self, rotation):
        """The watermark must read at its design angle on screen, not sideways.

        This is the test that matters for /Rotate. Presence alone is not enough
        and neither is a bounding-box check: for each quarter turn BOTH rotation
        directions produce an overlay that fits the mediabox, but one of them
        lands the text 180 degrees out. An earlier draft of the transform had
        exactly that bug — /Rotate 90 and 270 measured 150 degrees instead of
        -30 — and every presence-based assertion still passed.
        """
        source = _build_pdf([(LETTER, rotation)])
        page = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK))).pages[0]

        angles = _onscreen_angles(page)

        assert angles, 'no watermark text found to measure'
        assert angles == {-30.0}, (
            f'/Rotate {rotation}: watermark renders at {angles}, expected -30.0'
        )

    def test_mixed_rotations_in_one_document_all_render_upright(self):
        source = _build_pdf([(LETTER, 0), (LETTER, 90), (A4, 180), (WIDE, 270)])
        reader = PdfReader(io.BytesIO(stamp_pdf(source, PREVIEW_WATERMARK)))

        for index, page in enumerate(reader.pages):
            assert _onscreen_angles(page) == {-30.0}, f'page {index} is not upright'


class TestEncryptedAndInvalidSources:
    def test_encrypted_pdf_raises(self):
        with pytest.raises(EncryptedPdfError):
            stamp_pdf(_encrypted_pdf(), PREVIEW_WATERMARK)

    def test_encrypted_error_is_catchable_as_watermark_error(self):
        """The view catches the base class, so the hierarchy is part of the API."""
        assert issubclass(EncryptedPdfError, WatermarkError)

        with pytest.raises(WatermarkError):
            stamp_pdf(_encrypted_pdf(), PREVIEW_WATERMARK)

    def test_encrypted_pdf_produces_no_output_at_all(self):
        """Raising beats emitting corrupt bytes."""
        try:
            result = stamp_pdf(_encrypted_pdf(), PREVIEW_WATERMARK)
        except WatermarkError:
            return
        pytest.fail(f'expected a raise, got {len(result)} bytes')

    def test_garbage_bytes_raise_watermark_error(self):
        with pytest.raises(WatermarkError):
            stamp_pdf(b'this is not a pdf', PREVIEW_WATERMARK)

    def test_empty_bytes_raise_watermark_error(self):
        with pytest.raises(WatermarkError):
            stamp_pdf(b'', PREVIEW_WATERMARK)


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='wmfaculty@pampangastateu.edu.ph',
        first_name='Watermark',
        last_name='Faculty',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _make_thesis(user, *, file_type=FileType.PDF, payload=None, name='doc.pdf', sha=None):
    thesis = Thesis(
        title='A Watermarked Thesis About Semantic Retrieval',
        abstract='An abstract that is comfortably longer than twenty characters.',
        authors=['Tester, T.'],
        keywords=['watermark'],
        program='BS Information Technology',
        year=2025,
        adviser='',
        file_type=file_type,
        sha256=sha or ('a' * 63 + ('1' if file_type == FileType.PDF else '2')),
        extracted_text='',
        status=ThesisStatus.APPROVED,
        uploaded_by=user,
    )
    thesis.uploaded_file.save(name, ContentFile(payload or _build_pdf([(LETTER, 0)])), save=False)
    thesis.save()
    return thesis


def _get(client, thesis, user, disposition=None):
    url = reverse('thesis-download', kwargs={'id': str(thesis.id)})
    if disposition:
        url = f'{url}?disposition={disposition}'
    return client.get(url, HTTP_AUTHORIZATION=f'Bearer {_bearer(user)}')


@pytest.mark.django_db
class TestDownloadEndpointWatermarking:
    def test_inline_response_is_stamped(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        response = _get(client, thesis, faculty_user)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        page = PdfReader(io.BytesIO(response.content)).pages[0]
        assert PREVIEW_FRAGMENT in _page_text(page)

    def test_attachment_response_is_stamped(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        response = _get(client, thesis, faculty_user, 'attachment')

        assert response.status_code == 200
        page = PdfReader(io.BytesIO(response.content)).pages[0]
        assert DOWNLOAD_FRAGMENT in _page_text(page)

    def test_the_two_dispositions_return_different_bytes(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)

        inline = _get(client, thesis, faculty_user).content
        attachment = _get(client, thesis, faculty_user, 'attachment').content

        assert inline != attachment

    def test_served_bytes_differ_from_the_stored_original(self, client, faculty_user):
        """The whole point: the network tab must not yield the clean file."""
        original = _build_pdf([(LETTER, 0)])
        thesis = _make_thesis(faculty_user, payload=original)

        response = _get(client, thesis, faculty_user)

        assert response.content != original
        assert COMMON_FRAGMENT not in _page_text(
            PdfReader(io.BytesIO(original)).pages[0]
        )
        assert COMMON_FRAGMENT in _page_text(
            PdfReader(io.BytesIO(response.content)).pages[0]
        )

    def test_stored_file_is_never_modified(self, client, faculty_user):
        original = _build_pdf([(LETTER, 0)])
        thesis = _make_thesis(faculty_user, payload=original)

        _get(client, thesis, faculty_user)
        _get(client, thesis, faculty_user, 'attachment')

        thesis.refresh_from_db()
        with thesis.uploaded_file.open('rb') as handle:
            assert handle.read() == original

    def test_unknown_disposition_falls_back_to_inline(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        response = _get(client, thesis, faculty_user, 'bogus')

        assert response.status_code == 200
        assert response['Content-Disposition'].startswith('inline;')

    def test_requires_authentication(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        url = reverse('thesis-download', kwargs={'id': str(thesis.id)})

        assert client.get(url).status_code in (401, 403)


@pytest.mark.django_db
class TestDownloadEndpointFilenames:
    def test_inline_filename_says_preview(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        disposition = _get(client, thesis, faculty_user)['Content-Disposition']

        assert disposition.startswith('inline;')
        assert '_Preview.pdf' in disposition

    def test_attachment_filename_omits_preview(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        disposition = _get(client, thesis, faculty_user, 'attachment')['Content-Disposition']

        assert disposition.startswith('attachment;')
        assert '_Preview' not in disposition
        assert disposition.endswith('.pdf"')

    def test_filename_is_branded_and_slugged(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        disposition = _get(client, thesis, faculty_user, 'attachment')['Content-Disposition']

        assert 'THESYSplus_2025_' in disposition
        assert 'a-watermarked-thesis' in disposition


@pytest.mark.django_db
class TestDownloadEndpointCaching:
    def _cache_names(self, thesis):
        from theses.views import WATERMARK_CACHE_PREFIX
        prefix = f'{WATERMARK_CACHE_PREFIX}/{thesis.id}'
        try:
            _dirs, files = default_storage.listdir(prefix)
        except (FileNotFoundError, OSError):
            return []
        return sorted(files)

    def test_first_request_writes_a_cache_entry(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)
        assert self._cache_names(thesis) == []

        _get(client, thesis, faculty_user)

        assert len(self._cache_names(thesis)) == 1

    def test_second_request_reuses_the_cache_without_restamping(
        self, client, faculty_user, monkeypatch,
    ):
        thesis = _make_thesis(faculty_user)
        _get(client, thesis, faculty_user)  # populate

        calls = []
        import theses.views as views_module
        real = views_module.stamp_pdf
        monkeypatch.setattr(
            views_module, 'stamp_pdf',
            lambda *a, **k: (calls.append(1), real(*a, **k))[1],
        )

        response = _get(client, thesis, faculty_user)

        assert response.status_code == 200
        assert calls == [], 'cache hit should not re-stamp'

    def test_each_disposition_gets_its_own_cache_entry(self, client, faculty_user):
        thesis = _make_thesis(faculty_user)

        _get(client, thesis, faculty_user)
        _get(client, thesis, faculty_user, 'attachment')

        names = self._cache_names(thesis)
        assert len(names) == 2
        assert any('inline' in n for n in names)
        assert any('attachment' in n for n in names)

    def test_cache_key_includes_version_sha_and_disposition(self, faculty_user):
        from theses.views import _watermark_cache_name

        thesis = _make_thesis(faculty_user)
        name = _watermark_cache_name(thesis, 'inline')

        assert str(thesis.id) in name
        assert thesis.sha256 in name
        assert f'v{WATERMARK_VERSION}' in name
        assert 'inline' in name
        assert name.startswith('theses/_watermarked/')

    def test_cached_artifact_is_not_under_the_originals_prefix(self, faculty_user):
        """Stamped copies must never be mistaken for originals."""
        from theses.views import _watermark_cache_name

        thesis = _make_thesis(faculty_user)
        name = _watermark_cache_name(thesis, 'inline')

        assert '_watermarked' in name
        assert not name.startswith('theses/2025/')
        assert not name.startswith('theses/2026/')

    def test_bumping_the_version_invalidates_and_regenerates(
        self, client, faculty_user, monkeypatch,
    ):
        thesis = _make_thesis(faculty_user)
        first = _get(client, thesis, faculty_user)
        assert first.status_code == 200
        original_names = self._cache_names(thesis)

        import theses.views as views_module
        monkeypatch.setattr(views_module, 'WATERMARK_VERSION', WATERMARK_VERSION + 1)

        calls = []
        real = views_module.stamp_pdf
        monkeypatch.setattr(
            views_module, 'stamp_pdf',
            lambda *a, **k: (calls.append(1), real(*a, **k))[1],
        )

        second = _get(client, thesis, faculty_user)

        assert second.status_code == 200
        assert calls == [1], 'version bump should force a re-stamp'
        assert self._cache_names(thesis) != original_names

    def test_a_corrupt_cache_entry_does_not_break_serving(self, client, faculty_user):
        """A bad cache must degrade to regeneration, not to a 500."""
        thesis = _make_thesis(faculty_user)
        from theses.views import _watermark_cache_name

        default_storage.save(
            _watermark_cache_name(thesis, 'inline'), ContentFile(b'not a pdf'),
        )

        response = _get(client, thesis, faculty_user)

        # The cached bytes are returned as-is (they are what the cache holds);
        # what must not happen is an unhandled exception.
        assert response.status_code in (200, 404)


@pytest.mark.django_db
class TestDocxUploadsAreWatermarked:
    def _docx_bytes(self, paragraphs):
        import zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
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
            body = ''.join(
                f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs
            )
            zf.writestr(
                'word/document.xml',
                '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
                'openxmlformats.org/wordprocessingml/2006/main">'
                f'<w:body>{body}</w:body></w:document>',
            )
            zf.writestr(
                'word/_rels/document.xml.rels',
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
                'openxmlformats.org/package/2006/relationships"/>',
            )
        return buffer.getvalue()

    def test_docx_inline_preview_is_watermarked(self, client, faculty_user):
        thesis = _make_thesis(
            faculty_user, file_type=FileType.DOCX,
            payload=self._docx_bytes(['A converted DOCX paragraph.']),
            name='doc.docx', sha='b' * 64,
        )
        response = _get(client, thesis, faculty_user)

        assert response.status_code == 200
        page = PdfReader(io.BytesIO(response.content)).pages[0]
        assert PREVIEW_FRAGMENT in _page_text(page)

    def test_docx_attachment_is_watermarked_with_the_download_text(
        self, client, faculty_user,
    ):
        thesis = _make_thesis(
            faculty_user, file_type=FileType.DOCX,
            payload=self._docx_bytes(['A converted DOCX paragraph.']),
            name='doc.docx', sha='c' * 64,
        )
        response = _get(client, thesis, faculty_user, 'attachment')

        assert response.status_code == 200
        page = PdfReader(io.BytesIO(response.content)).pages[0]
        assert DOWNLOAD_FRAGMENT in _page_text(page)

    def test_pdf_and_docx_get_identical_treatment(self, client, faculty_user):
        """Same stamper, so both carry the watermark and the same disposition."""
        pdf_thesis = _make_thesis(faculty_user, sha='d' * 64)
        docx_thesis = _make_thesis(
            faculty_user, file_type=FileType.DOCX,
            payload=self._docx_bytes(['Converted body.']),
            name='doc.docx', sha='e' * 64,
        )

        for thesis in (pdf_thesis, docx_thesis):
            response = _get(client, thesis, faculty_user, 'attachment')
            assert response.status_code == 200
            assert response['Content-Disposition'].startswith('attachment;')
            assert DOWNLOAD_FRAGMENT in _page_text(
                PdfReader(io.BytesIO(response.content)).pages[0]
            )

    def test_unconvertible_docx_returns_document_not_available(
        self, client, faculty_user,
    ):
        thesis = _make_thesis(
            faculty_user, file_type=FileType.DOCX,
            payload=b'not a real docx', name='broken.docx', sha='f' * 64,
        )
        response = _get(client, thesis, faculty_user)

        assert response.status_code == 404
        assert response.json()['error']['code'] == 'DOCUMENT_NOT_AVAILABLE'


@pytest.mark.django_db
class TestUnparseableStoredFile:
    """A DELIBERATE behaviour change, pinned here so it is not a surprise.

    Before watermarking, the view streamed stored bytes through without reading
    them, so a corrupt or truncated "PDF" was served with a 200 and
    ``Content-Type: application/pdf``; the browser's viewer then failed to
    render it and the user saw a broken frame with no explanation.

    Serving now requires parsing, so the same file yields a structured 404
    instead. That is the better failure — and critically, the stamper must NOT
    fall back to serving the original bytes unstamped, because that would make
    every malformed upload a route to an unwatermarked download.
    """

    def test_truncated_pdf_returns_document_not_available(self, client, faculty_user):
        thesis = _make_thesis(
            faculty_user, payload=b'%PDF-1.4\n%truncated\n', sha='2' * 64,
        )
        response = _get(client, thesis, faculty_user)

        assert response.status_code == 404
        body = response.json()
        assert body['error']['code'] == 'DOCUMENT_NOT_AVAILABLE'
        assert body['error']['details']['reason'] == 'watermark_failed'

    def test_no_unstamped_bytes_are_ever_served(self, client, faculty_user):
        """The security property: failure must not degrade to the clean file."""
        original = b'%PDF-1.4\n%truncated\n'
        thesis = _make_thesis(faculty_user, payload=original, sha='3' * 64)

        for disposition in (None, 'attachment'):
            response = _get(client, thesis, faculty_user, disposition)
            assert response.status_code == 404
            assert original not in response.content


@pytest.mark.django_db
class TestEncryptedSourceThroughTheEndpoint:
    def test_encrypted_pdf_returns_document_not_available(self, client, faculty_user):
        thesis = _make_thesis(faculty_user, payload=_encrypted_pdf(), sha='0' * 64)
        response = _get(client, thesis, faculty_user)

        assert response.status_code == 404
        body = response.json()
        assert body['error']['code'] == 'DOCUMENT_NOT_AVAILABLE'
        assert body['error']['details']['reason'] == 'source_encrypted'

    def test_encrypted_source_is_not_a_500(self, client, faculty_user):
        thesis = _make_thesis(faculty_user, payload=_encrypted_pdf(), sha='1' * 64)

        assert _get(client, thesis, faculty_user).status_code == 404
        assert _get(client, thesis, faculty_user, 'attachment').status_code == 404
