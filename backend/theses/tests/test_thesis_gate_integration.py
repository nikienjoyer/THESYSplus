"""Integration tests for the thesis document-type gate on all three surfaces.

The gate is a HARD BLOCK: upload, extract-title and extract-metadata all refuse
a non-thesis document, for every role, with no override.

The upload assertions are the ones that matter most. A Certificate of
Registration reaching the repository is a data-quality problem that outlives
whoever uploaded it, so rejection must leave behind NO Thesis row AND NO file on
disk — the second is asserted explicitly because Django does not delete files
when rows are rolled back, and an earlier ordering (extract after create) would
have left an orphan.
"""
from __future__ import annotations

import io
import os
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from reportlab.pdfgen import canvas

from accounts.models import Role, User
from theses.models import Thesis

UPLOAD_URL_NAME = 'thesis-upload'
EXTRACT_TITLE_URL_NAME = 'thesis-extract-title'
EXTRACT_METADATA_URL_NAME = 'thesis-extract-metadata'


@pytest.fixture(autouse=True)
def isolate_media(settings, tmp_path):
    """Never write test uploads into the real MEDIA_ROOT."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='gatefaculty@pampangastateu.edu.ph',
        first_name='Gate',
        last_name='Faculty',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email='gatestudent@pampangastateu.edu.ph',
        first_name='Gate',
        last_name='Student',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------

COR_LINES = [
    'PAMPANGA STATE UNIVERSITY',
    'CERTIFICATE OF REGISTRATION',
    'Student No.: 2023313546   Name: SALONGA, ROMEL S.',
    'Bachelor of Science in Information Systems 4th Year SCHEDULE / ROOM',
    'SECTION Lec U N I T SUBJECT TITLE CODE Lab Credit',
    '303 Data Mining and Business Intelligence ISDBI 413 BSIS 4-A',
    '303 Strategy Management and Acquisition ISSMA 414 BSIS 4-A',
    '303 Systems Integration and Architecture ISSIA 415 BSIS 4-A',
    '303 Information Assurance and Security ISIAS 416 BSIS 4-A',
    'TOTAL UNITS: 24',
    'Assessment: Tuition Fee 12,000.00  Misc 2,500.00  Total 14,500.00',
    'Registrar   Cashier   Adviser',
    'Date Enrolled: August 12, 2026',
    'This certificate is issued upon request for enrolment verification only.',
    'Any alteration renders this document invalid and void for all purposes.',
]

THESIS_LINES = [
    'PAMPANGA STATE UNIVERSITY',
    'College of Computing Studies',
    '',
    'A MOBILE HEALTH RECORDS SYSTEM FOR RURAL CLINICS',
    '',
    'A Capstone',
    'Presented to the Faculty of',
    'In Partial Fulfillment',
    'of the Requirements for the Degree',
    '',
    'by:',
    'Dela Cruz, Juan M.',
    '',
    'May 2025',
    '',
    'ABSTRACT',
    'This study developed and evaluated a mobile health records platform for',
    'rural clinics, applying an iterative development methodology across three',
    'pilot sites and measuring staff adoption over two academic terms.',
    '',
    'Keywords: mobile health, records management, rural clinics',
    '',
    'CHAPTER I',
    'THE PROBLEM AND ITS BACKGROUND',
    'The researchers observed that paper records were routinely mislaid.',
    '',
    'REFERENCES',
]


def _pdf_from_lines(lines, pages=1) -> bytes:
    """A real multi-line PDF, one text line per drawn row."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 740
    for line in lines:
        if y < 60:
            pdf.showPage()
            y = 740
        pdf.drawString(54, y, line)
        y -= 16
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _docx_from_lines(lines) -> bytes:
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
            f'<w:p><w:r><w:t xml:space="preserve">{line}</w:t></w:r></w:p>'
            for line in lines if line
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


DOCX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
)


def _upload(client, user, payload, name='doc.pdf', content_type='application/pdf'):
    return client.post(
        reverse(UPLOAD_URL_NAME),
        data={
            'title': 'A Mobile Health Records System For Rural Clinics',
            'abstract': 'An abstract comfortably longer than twenty characters.',
            'authors': '["Dela Cruz, Juan M."]',
            'keywords': '["mobile health"]',
            'program': 'BS Information Technology',
            'year': '2025',
            'adviser': '',
            'file': SimpleUploadedFile(name, payload, content_type=content_type),
        },
        HTTP_AUTHORIZATION=f'Bearer {_bearer(user)}',
    )


def _media_files(settings):
    """Every file currently under MEDIA_ROOT."""
    root = settings.MEDIA_ROOT
    if not os.path.isdir(root):
        return []
    found = []
    for dirpath, _dirs, files in os.walk(root):
        found.extend(os.path.join(dirpath, f) for f in files)
    return found


# ---------------------------------------------------------------------------
# Upload — the surface that matters
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUploadRejectsNonThesis:
    def test_cor_upload_returns_400_not_a_thesis(self, client, faculty_user):
        response = _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'NOT_A_THESIS_DOCUMENT'

    def test_no_thesis_row_is_created(self, client, faculty_user):
        before = Thesis.objects.count()

        _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert Thesis.objects.count() == before

    def test_no_file_is_left_on_disk(self, client, faculty_user, settings):
        """Django does not delete files when a row is rolled back.

        The gate therefore has to run BEFORE the row is created, not after — an
        earlier ordering extracted text from ``thesis.uploaded_file.path``,
        which means the file was already written by then.
        """
        assert _media_files(settings) == []

        _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert _media_files(settings) == [], 'rejected upload left an orphaned file'

    def test_error_details_name_the_reason_and_found_markers(self, client, faculty_user):
        response = _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        details = response.json()['error']['details']
        assert details['reason'] == 'not_a_thesis'
        assert details['found_markers'] == []
        assert details['markers_found_count'] == 0

    def test_message_is_actionable(self, client, faculty_user):
        response = _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        message = response.json()['error']['message']
        assert 'does not appear to be a thesis' in message
        assert 'upload the thesis manuscript' in message.lower()

    def test_docx_cor_is_also_rejected(self, client, faculty_user):
        response = _upload(
            client, faculty_user, _docx_from_lines(COR_LINES),
            name='cor.docx', content_type=DOCX_CONTENT_TYPE,
        )

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'NOT_A_THESIS_DOCUMENT'


@pytest.mark.django_db
class TestGateAppliesToEveryRole:
    """No faculty/admin override — the block is unconditional."""

    def test_student_is_rejected(self, client, student_user):
        response = _upload(client, student_user, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'NOT_A_THESIS_DOCUMENT'

    def test_faculty_is_rejected(self, client, faculty_user):
        response = _upload(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400

    def test_administrator_is_rejected(self, client, db):
        admin = User.objects.create_user(
            email='gateadmin@pampangastateu.edu.ph',
            first_name='Gate', last_name='Admin',
            role=Role.ADMINISTRATOR, password='Test12345!Test',
        )
        response = _upload(client, admin, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400
        assert Thesis.objects.count() == 0


@pytest.mark.django_db
class TestUploadStillAcceptsRealTheses:
    """The gate must not break the working path."""

    def test_thesis_pdf_upload_succeeds(self, client, faculty_user):
        response = _upload(client, faculty_user, _pdf_from_lines(THESIS_LINES))

        assert response.status_code == 201, response.content
        assert Thesis.objects.count() == 1

    def test_extracted_text_is_populated(self, client, faculty_user):
        """Text is now extracted before create and reused, not re-parsed after."""
        _upload(client, faculty_user, _pdf_from_lines(THESIS_LINES))

        thesis = Thesis.objects.get()
        assert thesis.extracted_text
        assert 'ABSTRACT' in thesis.extracted_text.upper()

    def test_thesis_docx_upload_succeeds(self, client, faculty_user):
        response = _upload(
            client, faculty_user, _docx_from_lines(THESIS_LINES),
            name='thesis.docx', content_type=DOCX_CONTENT_TYPE,
        )

        assert response.status_code == 201, response.content

    def test_a_scheduling_thesis_is_accepted(self, client, faculty_user):
        """The false-positive guard, end to end through the view."""
        lines = [
            'AN AUTOMATED CLASS SCHEDULING AND ROOM ALLOCATION SYSTEM',
            'A Capstone',
            'Presented to the Faculty of',
            'In Partial Fulfillment',
            '',
            'ABSTRACT',
            'The system assigns each SECTION to a ROOM and computes the total',
            'UNIT and CREDIT load per student, replacing the manual SCHEDULE.',
            'SUBJECT TITLE and CODE mappings were validated against curriculum.',
            '',
            'Keywords: class scheduling, room allocation, enrolment',
            '',
            'CHAPTER I',
            'INTRODUCTION',
            'The registrar prepares the SCHEDULE by hand each term.',
            '',
            'REFERENCES',
        ]
        response = _upload(client, faculty_user, _pdf_from_lines(lines))

        assert response.status_code == 201, response.content


# ---------------------------------------------------------------------------
# Extraction surfaces
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExtractTitleRejectsNonThesis:
    def _post(self, client, user, payload, name='cor.pdf', ctype='application/pdf'):
        return client.post(
            reverse(EXTRACT_TITLE_URL_NAME),
            data={'file': SimpleUploadedFile(name, payload, content_type=ctype)},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(user)}',
        )

    def test_cor_is_rejected(self, client, faculty_user):
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'NOT_A_THESIS_DOCUMENT'

    def test_no_detected_title_is_returned(self, client, faculty_user):
        """The reported bug: a schedule row came back AS the detected title."""
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert 'detected_title' not in response.json()

    def test_message_asks_for_a_title_document_not_a_manuscript(
        self, client, faculty_user,
    ):
        """This surface validates a PROPOSED title.

        At proposal stage the manuscript does not exist, so "upload the thesis
        manuscript itself" sends the user to produce something they cannot.
        """
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        message = response.json()['error']['message']
        assert 'does not appear to be a thesis' in message
        assert 'proposed thesis or research title' in message
        assert 'manuscript' not in message.lower()

    def test_a_real_thesis_still_extracts(self, client, faculty_user):
        response = self._post(
            client, faculty_user, _pdf_from_lines(THESIS_LINES), name='thesis.pdf',
        )

        assert response.status_code == 200, response.content
        assert 'detected_title' in response.json()


@pytest.mark.django_db
class TestExtractMetadataRejectsNonThesis:
    def _post(self, client, user, payload, name='cor.pdf', ctype='application/pdf'):
        return client.post(
            reverse(EXTRACT_METADATA_URL_NAME),
            data={'file': SimpleUploadedFile(name, payload, content_type=ctype)},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(user)}',
        )

    def test_cor_is_rejected(self, client, faculty_user):
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'NOT_A_THESIS_DOCUMENT'

    def test_no_fields_are_returned(self, client, faculty_user):
        """Auto-filling a form from a COR walks the user into submitting one."""
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        assert 'fields' not in response.json()

    def test_message_keeps_the_upload_wording(self, client, faculty_user):
        """extract-metadata feeds the UPLOAD form, so it keeps the strict text.

        Guards against someone later flipping this call site to the title-check
        surface by analogy with extract-title. Both endpoints read a document,
        but this one is a step in submitting a manuscript.
        """
        response = self._post(client, faculty_user, _pdf_from_lines(COR_LINES))

        message = response.json()['error']['message']
        assert 'upload the thesis manuscript' in message.lower()
        assert 'proposed thesis or research title' not in message

    def test_a_real_thesis_still_auto_fills(self, client, faculty_user):
        response = self._post(
            client, faculty_user, _pdf_from_lines(THESIS_LINES), name='thesis.pdf',
        )

        assert response.status_code == 200, response.content
        assert 'fields' in response.json()


@pytest.mark.django_db
class TestAllThreeSurfacesAgree:
    def test_same_error_code_everywhere(self, client, faculty_user):
        """One threshold, one code — a document refused on one surface is
        refused on all of them."""
        cor = _pdf_from_lines(COR_LINES)
        token = _bearer(faculty_user)
        codes = set()

        upload = _upload(client, faculty_user, cor)
        codes.add(upload.json()['error']['code'])

        for url_name in (EXTRACT_TITLE_URL_NAME, EXTRACT_METADATA_URL_NAME):
            response = client.post(
                reverse(url_name),
                data={'file': SimpleUploadedFile(
                    'cor.pdf', cor, content_type='application/pdf',
                )},
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            codes.add(response.json()['error']['code'])

        assert codes == {'NOT_A_THESIS_DOCUMENT'}

    def test_wording_differs_only_on_the_title_check_surface(self):
        """Same check object, two surfaces, two messages — one code.

        Unit-level so it does not depend on which endpoint is wired where: the
        helper itself must produce both wordings, and must keep the error code
        and the details shape identical between them.
        """
        from theses.services.thesis_document_check import check_thesis_document
        from theses.views import (
            SURFACE_TITLE_CHECK,
            SURFACE_UPLOAD,
            _not_a_thesis_response,
        )

        check = check_thesis_document('\n'.join(COR_LINES))
        assert not check.passed

        upload = _not_a_thesis_response(check, surface=SURFACE_UPLOAD)
        title_check = _not_a_thesis_response(check, surface=SURFACE_TITLE_CHECK)

        upload_error = upload.data['error']
        title_error = title_check.data['error']

        assert upload_error['message'] != title_error['message']
        assert upload_error['code'] == title_error['code'] == 'NOT_A_THESIS_DOCUMENT'
        assert upload_error['details'].keys() == title_error['details'].keys()
        assert upload_error['details'] == title_error['details']
        assert upload.status_code == title_check.status_code == 400

    def test_default_surface_is_the_strict_upload_wording(self):
        """Omitting ``surface`` must not silently relax the message.

        A caller added later and wired without the keyword should get the
        manuscript-demanding sentence, not one that invites a thinner document.
        """
        from theses.services.thesis_document_check import check_thesis_document
        from theses.views import SURFACE_UPLOAD, _not_a_thesis_response

        check = check_thesis_document('\n'.join(COR_LINES))

        default = _not_a_thesis_response(check)
        explicit = _not_a_thesis_response(check, surface=SURFACE_UPLOAD)

        assert default.data['error']['message'] == explicit.data['error']['message']
        assert 'manuscript' in default.data['error']['message'].lower()

    def test_unreadable_message_is_shared_by_both_surfaces(self):
        """The unreadable remedy is genuinely identical, so it is not split."""
        from theses.services.thesis_document_check import (
            REASON_UNREADABLE,
            check_thesis_document,
        )
        from theses.views import (
            SURFACE_TITLE_CHECK,
            SURFACE_UPLOAD,
            _not_a_thesis_response,
        )

        check = check_thesis_document('   ')
        assert check.reason == REASON_UNREADABLE

        upload = _not_a_thesis_response(check, surface=SURFACE_UPLOAD)
        title_check = _not_a_thesis_response(check, surface=SURFACE_TITLE_CHECK)

        assert upload.data['error']['message'] == title_check.data['error']['message']
        assert 'scanned' in upload.data['error']['message'].lower()
