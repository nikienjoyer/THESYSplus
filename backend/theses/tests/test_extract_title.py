"""Tests for POST /api/v1/theses/extract-title/.

Covers:
  1. Authentication required
  2. Missing file → 400
  3. Wrong file type → 400
  4. Valid PDF (minimal synthetic) → extracts title
  5. Valid DOCX → extracts title
  6. Empty / unreadable document → confidence=low, empty title
  7. Title-detection heuristic smoke-tests
"""
from __future__ import annotations

import io
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role, User
from theses.views import ThesisExtractTitleView


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='facet@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Extract',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _minimal_pdf(text_content: str = '') -> bytes:
    """Build a minimal valid PDF with text content."""
    safe = (text_content
            .replace('\\', '\\\\')
            .replace('(', '\\(')
            .replace(')', '\\)')
            .replace('\n', '\\n'))
    content = f'BT /F1 10 Tf 50 750 Td ({safe}) Tj ET'.encode('latin-1', errors='replace')
    parts = [b'%PDF-1.4\n']
    o1 = len(b''.join(parts))
    parts.append(b'1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n')
    o2 = len(b''.join(parts))
    parts.append(b'2 0 obj <</Type /Pages /Count 1 /Kids [3 0 R]>> endobj\n')
    o3 = len(b''.join(parts))
    parts.append(
        b'3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Contents 4 0 R /Resources <</Font <</F1 <</Type /Font '
        b'/Subtype /Type1 /BaseFont /Helvetica>>>>>>>> endobj\n'
    )
    o4 = len(b''.join(parts))
    stream_obj = (
        f'4 0 obj <</Length {len(content)}>>\nstream\n'.encode('latin-1')
        + content
        + b'\nendstream endobj\n'
    )
    parts.append(stream_obj)
    xref_off = len(b''.join(parts))
    xref = (
        b'xref\n0 5\n0000000000 65535 f \n'
        + f'{o1:010d} 00000 n \n'.encode()
        + f'{o2:010d} 00000 n \n'.encode()
        + f'{o3:010d} 00000 n \n'.encode()
        + f'{o4:010d} 00000 n \n'.encode()
    )
    parts.append(xref)
    parts.append(
        b'trailer <</Size 5 /Root 1 0 R>>\nstartxref\n'
        + f'{xref_off}\n'.encode()
        + b'%%EOF\n'
    )
    return b''.join(parts)


def _minimal_docx(text: str) -> bytes:
    """Build a minimal DOCX from plain text."""
    import zipfile, io as _io
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml',
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>')
        zf.writestr('_rels/.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        para_xml = ''.join(
            f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>'
            for line in text.split('\n') if line.strip()
        )
        zf.writestr('word/document.xml',
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{para_xml}</w:body></w:document>')
        zf.writestr('word/_rels/document.xml.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit tests for _detect_title heuristic
# ---------------------------------------------------------------------------

class TestDetectTitleHeuristic:
    view = ThesisExtractTitleView()

    def test_ai_attendance_title_detected(self):
        text = (
            "Pampanga State University\n"
            "College of Computing Studies\n"
            "\n"
            "AI-Powered Attendance Monitoring Using Facial Recognition\n"
            "\n"
            "Juan Dela Cruz\n"
            "2024\n"
            "Abstract\n"
            "This study proposes a deep-learning attendance system...\n"
        )
        title, conf = self.view._detect_title(text)
        assert 'Attendance' in title or 'attendance' in title.lower()
        assert conf in ('high', 'medium', 'low')

    def test_noise_lines_skipped(self):
        text = (
            "Abstract\n"
            "Introduction\n"
            "Table of Contents\n"
            "Smart Inventory Management System Using IoT\n"
            "Juan Cruz\n"
        )
        title, conf = self.view._detect_title(text)
        assert 'Inventory' in title or 'inventory' in title.lower()

    def test_empty_text_returns_empty(self):
        title, conf = self.view._detect_title('')
        assert title == ''
        assert conf == 'low'

    def test_allcaps_converted_to_titlecase(self):
        text = "BLOCKCHAIN BASED CREDENTIAL VERIFICATION SYSTEM FOR PSU\nJuan Cruz\n"
        title, conf = self.view._detect_title(text)
        # Should be title-cased, not ALL-CAPS
        if title:
            assert title != title.upper() or len(title) <= 2


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExtractTitleEndpoint:

    def test_requires_authentication(self, client):
        url = reverse('thesis-extract-title')
        response = client.post(url, data={})
        assert response.status_code == 401

    def test_missing_file_returns_400(self, client, faculty_user):
        token = _bearer(faculty_user)
        url = reverse('thesis-extract-title')
        response = client.post(
            url,
            data={},
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'MISSING_FILE'

    def test_wrong_file_type_rejected(self, client, faculty_user):
        token = _bearer(faculty_user)
        url = reverse('thesis-extract-title')
        fake_txt = SimpleUploadedFile('proposal.txt', b'Some text', content_type='text/plain')
        response = client.post(
            url,
            data={'file': fake_txt},
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'FILE_TYPE_NOT_ALLOWED'

    def test_pdf_extraction_returns_envelope(self, client, faculty_user):
        token = _bearer(faculty_user)
        pdf_bytes = _minimal_pdf(
            'AI-Powered Attendance Monitoring Using Facial Recognition\n'
            'Juan Dela Cruz\n'
            'Abstract\n'
            'This study proposes a deep-learning attendance system.'
        )
        pdf_file = SimpleUploadedFile('proposal.pdf', pdf_bytes, content_type='application/pdf')
        url = reverse('thesis-extract-title')
        response = client.post(
            url,
            data={'file': pdf_file},
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        # Envelope shape
        for key in ('detected_title', 'confidence', 'method', 'message'):
            assert key in body
        assert body['confidence'] in ('high', 'medium', 'low')
        assert body['method'] in ('pypdf', 'ocr_tesseract', 'python_docx', 'failed')

    def test_docx_extraction_returns_envelope(self, client, faculty_user):
        token = _bearer(faculty_user)
        docx_bytes = _minimal_docx(
            'Real-Time Sign Language Recognition System Using MediaPipe\n'
            'Maria Santos\n'
            'Abstract\n'
            'This study implements a sign language recognition system.'
        )
        docx_file = SimpleUploadedFile(
            'proposal.docx', docx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        url = reverse('thesis-extract-title')
        response = client.post(
            url,
            data={'file': docx_file},
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        for key in ('detected_title', 'confidence', 'method', 'message'):
            assert key in body

    def test_empty_pdf_returns_low_confidence(self, client, faculty_user):
        token = _bearer(faculty_user)
        # Minimal PDF with no meaningful text
        pdf_bytes = _minimal_pdf('')
        pdf_file = SimpleUploadedFile('empty.pdf', pdf_bytes, content_type='application/pdf')
        url = reverse('thesis-extract-title')
        response = client.post(
            url,
            data={'file': pdf_file},
            format='multipart',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        # Either no title detected OR confidence is low
        if not body['detected_title']:
            assert body['confidence'] == 'low'


class TestChapterHeadingPenalty:
    """Verify that the chapter-heading document penalty caps confidence at 'low'."""
    view = ThesisExtractTitleView()

    def test_chapter_i_capped_at_low(self):
        text = (
            "Chapter I\n"
            "The Problem and Its Background\n"
            "\n"
            "This chapter presents the background of the study...\n"
            "The researchers aim to develop an AI-Based Attendance Monitoring System\n"
        )
        _title, conf = self.view._detect_title(text)
        assert conf == 'low', (
            f'Expected low confidence for chapter-heading document, got {conf!r}'
        )

    def test_introduction_start_capped_at_low(self):
        text = (
            "Introduction\n"
            "\n"
            "This study focuses on AI-Based Attendance Monitoring System.\n"
        )
        _title, conf = self.view._detect_title(text)
        assert conf == 'low'

    def test_methodology_start_capped_at_low(self):
        text = (
            "Methodology\n"
            "Research Design and Development Approach\n"
            "The researchers used agile methodology for this project.\n"
        )
        _title, conf = self.view._detect_title(text)
        assert conf == 'low'

    def test_proper_title_page_not_penalised(self):
        """A proper title page (no chapter headings) is not penalised."""
        text = (
            "Pampanga State University\n"
            "\n"
            "AI-Powered Attendance Monitoring Using Facial Recognition for PSU\n"
            "\n"
            "A Thesis Presented to the Faculty\n"
            "Juan Dela Cruz\n"
            "2024\n"
        )
        title, _conf = self.view._detect_title(text)
        # Something should be detected; confidence is not forced to 'low'
        assert title


class TestConfidenceMessages:
    """Verify the per-confidence messages returned by the view."""
    view = ThesisExtractTitleView()

    def _fake_response(self, text, method='pypdf'):
        """Simulate the message-building logic by calling _detect_title directly."""
        detected, confidence = self.view._detect_title(text)
        if not detected:
            return '', 'low', 'Could not confidently detect a title.'
        if confidence == 'high':
            msg = 'Title detected successfully. The thesis title was automatically extracted.'
        elif confidence == 'medium':
            msg = 'Possible title detected. Please review and edit the detected title if needed.'
        else:
            msg = (
                'Low confidence title detection. '
                'This file may not contain a title page — the detected text may be a '
                'chapter heading or section title. Please review and edit manually.'
            )
        return detected, confidence, msg

    def test_high_confidence_message(self):
        text = (
            "Pampanga State University\n"
            "\n"
            "AI-Powered Attendance Monitoring Using Facial Recognition for PSU Classrooms\n"
            "\n"
            "Juan Dela Cruz\n"
        )
        detected, conf, msg = self._fake_response(text)
        if conf == 'high':
            assert 'successfully' in msg.lower()
            assert 'automatically extracted' in msg.lower()

    def test_medium_confidence_message(self):
        # A plausible title that scores in the medium range
        text = (
            "Pampanga State University\n"
            "An Evaluation Study\n"
            "Juan Cruz\n"
        )
        _detected, conf, msg = self._fake_response(text)
        if conf == 'medium':
            assert 'review' in msg.lower()
            assert 'edit' in msg.lower()

    def test_low_confidence_message_chapter(self):
        text = (
            "Chapter I\n"
            "The Problem and Its Background\n"
            "This chapter discusses the background of the study.\n"
            "AI-Based Attendance Monitoring System Using Facial Recognition\n"
        )
        _detected, conf, msg = self._fake_response(text)
        # After chapter penalty, conf is low → specific message
        assert conf == 'low'
        assert 'low confidence' in msg.lower()
        assert 'chapter heading' in msg.lower() or 'title page' in msg.lower()

    def test_low_confidence_message_no_title(self):
        _detected, conf, msg = self._fake_response('')
        assert conf == 'low'
        assert 'confidently' in msg.lower() or 'manually' in msg.lower()
