"""Tests for the placeholder-manuscript backfill command.

The bug this guards against: ``backend/media/`` is gitignored, so a checkout
carries thesis rows but not the uploaded bytes. ``ThesisDownloadView`` then
returns ``DOCUMENT_NOT_AVAILABLE`` and the previewer shows "source document is
not available". These tests pin the backfill, its idempotence, and the fact
that the download endpoint serves a real PDF afterwards.
"""

from __future__ import annotations

import io

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, User
from theses.management.commands.attach_sample_manuscripts import (
    STAMP_TEXT,
    build_manuscript_pdf,
    file_state,
)
from theses.models import FileType, Program, Thesis, ThesisStatus
from theses.views import ThesisDownloadView


@pytest.fixture(autouse=True)
def isolate_media(settings, tmp_path):
    """Never touch the real MEDIA_ROOT from tests."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email='manuscript.uploader@pampangastateu.edu.ph',
        first_name='Man',
        last_name='Uscript',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, uploader):
    counter = {'n': 0}

    def _make(
        title: str = 'A Thesis Without A File',
        *,
        with_file: bool = False,
        file_bytes: bytes = b'%PDF-1.4\n%real\n',
        status: str = ThesisStatus.APPROVED,
        **kwargs,
    ) -> Thesis:
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=title,
            abstract=kwargs.pop('abstract', f'Abstract for {title}.'),
            authors=kwargs.pop('authors', ['Dela Cruz, Juan M.', 'Santos, Maria L.']),
            keywords=kwargs.pop('keywords', ['alpha', 'beta']),
            program=kwargs.pop('program', Program.BSIT.value),
            year=kwargs.pop('year', 2024),
            adviser=kwargs.pop('adviser', 'Prof. Reyes, Roberto'),
            file_type=FileType.PDF,
            sha256=f'{n:064x}',
            status=status,
            uploaded_by=uploader,
            **kwargs,
        )
        if with_file:
            thesis.uploaded_file.save(
                f'real_{n}.pdf', ContentFile(file_bytes), save=False,
            )
        thesis.save()
        return thesis

    return _make


def download(thesis, user):
    request = APIRequestFactory().get(f'/api/v1/theses/{thesis.id}/download/')
    force_authenticate(request, user=user)
    response = ThesisDownloadView.as_view()(request, id=str(thesis.id))
    if hasattr(response, 'render'):
        response.render()
    return response


def payload(response) -> bytes:
    if getattr(response, 'streaming', False):
        return b''.join(response.streaming_content)
    return response.content


# ---------------------------------------------------------------------------
# The failure this fixes
# ---------------------------------------------------------------------------

class TestTheOriginalFailure:
    def test_missing_file_yields_document_not_available(self, make_thesis, uploader):
        """Reproduce the reported error before backfilling."""
        thesis = make_thesis('Row Without Bytes')
        thesis.uploaded_file.name = 'theses/2026/gone.pdf'
        thesis.save(update_fields=['uploaded_file'])

        response = download(thesis, uploader)

        assert response.status_code == 404
        assert response.data['error']['code'] == 'DOCUMENT_NOT_AVAILABLE'
        assert response.data['error']['details']['reason'] == 'file_missing_from_storage'

    def test_backfill_makes_the_same_thesis_previewable(self, make_thesis, uploader):
        thesis = make_thesis('Row Without Bytes')
        thesis.uploaded_file.name = 'theses/2026/gone.pdf'
        thesis.save(update_fields=['uploaded_file'])

        call_command('attach_sample_manuscripts', verbosity=0)

        response = download(thesis, uploader)
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert response['Content-Disposition'].startswith('inline')
        assert payload(response).startswith(b'%PDF-')


# ---------------------------------------------------------------------------
# File-state classification
# ---------------------------------------------------------------------------

class TestFileState:
    def test_blank_field(self, make_thesis):
        assert file_state(make_thesis('No File')) == 'blank'

    def test_missing_on_disk(self, make_thesis):
        thesis = make_thesis('Dangling')
        thesis.uploaded_file.name = 'theses/2026/nope.pdf'
        thesis.save(update_fields=['uploaded_file'])
        assert file_state(thesis) == 'missing'

    def test_present(self, make_thesis):
        assert file_state(make_thesis('Has File', with_file=True)) == 'present'

    def test_zero_byte_file_counts_as_empty(self, make_thesis):
        """A zero-byte file passes an existence check but cannot render."""
        thesis = make_thesis('Empty File', with_file=True, file_bytes=b'')
        assert file_state(thesis) == 'empty'


# ---------------------------------------------------------------------------
# Backfill behaviour
# ---------------------------------------------------------------------------

class TestBackfill:
    def test_blank_field_gets_a_file(self, make_thesis):
        thesis = make_thesis('Needs One')
        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        assert thesis.uploaded_file.name
        assert file_state(thesis) == 'present'

    def test_zero_byte_file_is_replaced(self, make_thesis):
        thesis = make_thesis('Empty', with_file=True, file_bytes=b'')
        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        assert file_state(thesis) == 'present'
        assert thesis.uploaded_file.size > 0

    def test_existing_valid_file_is_left_alone(self, make_thesis):
        """The core idempotence guarantee: never clobber a real manuscript."""
        original = b'%PDF-1.4\n%the real manuscript\n'
        thesis = make_thesis('Real Manuscript', with_file=True, file_bytes=original)
        before_name = thesis.uploaded_file.name
        before_hash = thesis.sha256

        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        assert thesis.uploaded_file.name == before_name
        assert thesis.sha256 == before_hash
        with thesis.uploaded_file.open('rb') as handle:
            assert handle.read() == original

    def test_running_twice_changes_nothing_the_second_time(self, make_thesis):
        thesis = make_thesis('Twice')
        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        first_name, first_hash = thesis.uploaded_file.name, thesis.sha256
        with thesis.uploaded_file.open('rb') as handle:
            first_bytes = handle.read()

        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        assert thesis.uploaded_file.name == first_name
        assert thesis.sha256 == first_hash
        with thesis.uploaded_file.open('rb') as handle:
            assert handle.read() == first_bytes

    def test_dry_run_writes_nothing(self, make_thesis):
        thesis = make_thesis('Untouched')
        call_command('attach_sample_manuscripts', '--dry-run', verbosity=0)

        thesis.refresh_from_db()
        assert file_state(thesis) == 'blank'

    def test_force_regenerates_an_existing_file(self, make_thesis):
        from pypdf import PdfReader

        original = b'%PDF-1.4\n%the original manuscript\n'
        thesis = make_thesis('Forced', with_file=True, file_bytes=original)

        call_command('attach_sample_manuscripts', '--force', verbosity=0)

        thesis.refresh_from_db()
        with thesis.uploaded_file.open('rb') as handle:
            replaced = handle.read()

        # Assert on the rendered document rather than raw byte substrings:
        # ReportLab embeds font names like Helvetica-Bold, so naive substring
        # checks against the binary are unreliable.
        assert replaced != original
        text = '\n'.join(
            (p.extract_text() or '') for p in PdfReader(io.BytesIO(replaced)).pages
        )
        assert STAMP_TEXT in text
        assert 'Forced' in text

    def test_sha256_is_recomputed_to_match_the_bytes(self, make_thesis):
        import hashlib

        thesis = make_thesis('Hashed')
        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        with thesis.uploaded_file.open('rb') as handle:
            on_disk = handle.read()
        assert thesis.sha256 == hashlib.sha256(on_disk).hexdigest()

    def test_keep_hash_leaves_sha256_alone(self, make_thesis):
        thesis = make_thesis('Kept Hash')
        before = thesis.sha256

        call_command('attach_sample_manuscripts', '--keep-hash', verbosity=0)

        thesis.refresh_from_db()
        assert thesis.sha256 == before
        assert file_state(thesis) == 'present'

    def test_existing_recorded_path_is_reused(self, make_thesis):
        """Honour the DB name so a stray duplicate file is not created."""
        thesis = make_thesis('Recorded Path')
        thesis.uploaded_file.name = 'theses/2026/Recorded_Path.pdf'
        thesis.save(update_fields=['uploaded_file'])

        call_command('attach_sample_manuscripts', verbosity=0)

        thesis.refresh_from_db()
        assert thesis.uploaded_file.name.endswith('Recorded_Path.pdf')

    def test_all_statuses_are_backfilled(self, make_thesis):
        rows = [
            make_thesis('Approved Row', status=ThesisStatus.APPROVED),
            make_thesis('Pending Row', status=ThesisStatus.PENDING_REVIEW),
            make_thesis('Rejected Row', status=ThesisStatus.REJECTED),
        ]
        call_command('attach_sample_manuscripts', verbosity=0)

        for row in rows:
            row.refresh_from_db()
            assert file_state(row) == 'present'


# ---------------------------------------------------------------------------
# Generated document
# ---------------------------------------------------------------------------

class TestGeneratedPdf:
    def test_is_a_valid_two_page_pdf(self, make_thesis):
        from pypdf import PdfReader

        pdf = build_manuscript_pdf(make_thesis('Valid PDF'))

        assert pdf.startswith(b'%PDF-')
        reader = PdfReader(io.BytesIO(pdf))
        assert len(reader.pages) == 2

    def test_carries_the_catalogued_metadata_and_stamp(self, make_thesis):
        from pypdf import PdfReader

        thesis = make_thesis(
            'Distinctive Marker Title',
            abstract='An abstract containing the token XYZZYPLUGH for retrieval.',
            program=Program.BSCS.value,
            year=2021,
        )
        pdf = build_manuscript_pdf(thesis)
        text = '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(pdf)).pages)

        assert 'Distinctive Marker Title' in text
        assert 'XYZZYPLUGH' in text
        assert Program.BSCS.value in text
        assert '2021' in text
        assert 'Dela Cruz, Juan M.' in text
        # The reader must never mistake this for the original submission.
        assert STAMP_TEXT in text

    def test_titles_with_xml_metacharacters_do_not_break_rendering(self, make_thesis):
        from pypdf import PdfReader

        thesis = make_thesis('Ampersands & <Angle> Brackets "Quoted"')
        pdf = build_manuscript_pdf(thesis)

        reader = PdfReader(io.BytesIO(pdf))
        assert len(reader.pages) == 2
        text = '\n'.join((p.extract_text() or '') for p in reader.pages)
        assert 'Ampersands' in text

    def test_missing_optional_metadata_is_tolerated(self, make_thesis):
        from pypdf import PdfReader

        thesis = make_thesis(
            'Sparse Record', abstract='', authors=[], keywords=[], adviser='',
        )
        pdf = build_manuscript_pdf(thesis)
        assert len(PdfReader(io.BytesIO(pdf)).pages) == 2

    def test_each_thesis_gets_distinct_bytes(self, make_thesis):
        """Distinct content matters: sha256 is UNIQUE on the model."""
        a = build_manuscript_pdf(make_thesis('First Distinct Title'))
        b = build_manuscript_pdf(make_thesis('Second Distinct Title'))
        assert a != b


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_every_thesis_is_previewable_after_backfill(self, make_thesis, uploader):
        rows = [make_thesis(f'Repository Row {i}') for i in range(5)]
        rows.append(make_thesis('Already Real', with_file=True))

        call_command('attach_sample_manuscripts', verbosity=0)

        for row in rows:
            response = download(row, uploader)
            assert response.status_code == 200, row.title
            assert payload(response).startswith(b'%PDF-')
