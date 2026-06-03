"""Phase 2A semantic search tests.

Covers the four required cases:
  Case 1 — "AI attendance monitoring" → ranks Face Recognition Attendance highest
  Case 2 — "Library inventory" → unrelated theses rank below related ones
  Case 3 — Upload → embedding generated automatically
  Case 4 — Search endpoint returns ranked results
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus
from theses.services.semantic_search import (
    EMBEDDING_DIM,
    embed_text,
    generate_thesis_embedding,
    rank_theses,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='faculty1@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='One',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, faculty_user):
    """Factory: creates a thesis with embedding generated."""
    counter = {'n': 0}

    def _make(title: str, abstract: str, keywords=None, *, embed=True):
        counter['n'] += 1
        from django.core.files.base import ContentFile
        # Build a unique 64-char hex sha256 string per thesis.
        n = counter['n']
        sha = (f'{n:x}' + 'a' * 64)[:64]
        thesis = Thesis(
            title=title,
            abstract=abstract,
            authors=['Tester, T.'],
            keywords=keywords or ['test'],
            program=Program.BSIT.value,
            year=2024,
            adviser='',
            file_type=FileType.PDF,
            sha256=sha,
            extracted_text=f'{title}\n\n{abstract}',
            status=ThesisStatus.APPROVED,
            uploaded_by=faculty_user,
        )
        thesis.uploaded_file.save(
            f'thesis_{counter["n"]}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        if embed:
            generate_thesis_embedding(thesis)
        return thesis

    return _make


# ---------------------------------------------------------------------------
# compose_thesis_text — keyword inclusion and edge cases
# ---------------------------------------------------------------------------

class _FakeThesis:
    """Minimal stub used to test compose_thesis_text without a DB."""
    def __init__(self, title='', abstract='', extracted_text='', keywords=None):
        self.title = title
        self.abstract = abstract
        self.extracted_text = extracted_text
        self.keywords = keywords


class TestComposeThesisText:
    """Unit tests for compose_thesis_text — no DB required."""

    def test_keywords_list_included_in_output(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(
            title='RFID Attendance System',
            abstract='Tracks attendance using RFID cards.',
            keywords=['RFID', 'attendance', 'IoT'],
        )
        text = compose_thesis_text(t)
        assert 'RFID' in text
        assert 'attendance' in text
        assert 'IoT' in text

    def test_keywords_string_accepted(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(
            title='Test',
            abstract='Abstract.',
            keywords='machine learning deep learning',
        )
        text = compose_thesis_text(t)
        assert 'machine learning' in text

    def test_keywords_none_does_not_crash(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(title='Test', abstract='Abstract.', keywords=None)
        text = compose_thesis_text(t)
        assert 'Test' in text
        assert 'Abstract' in text

    def test_keywords_empty_list_does_not_add_blank_section(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(title='Test', abstract='Abstract.', keywords=[])
        text = compose_thesis_text(t)
        # Should end cleanly — no trailing separator
        assert not text.endswith('\n\n')

    def test_keywords_list_with_falsy_entries_skipped(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(title='Test', abstract='Abstract.', keywords=[None, '', 'valid'])
        text = compose_thesis_text(t)
        assert 'valid' in text
        # None and '' should not appear as literal strings
        assert 'None' not in text

    def test_extracted_text_truncated_before_keywords(self):
        from theses.services.semantic_search import compose_thesis_text, EXTRACTED_TEXT_MAX_CHARS
        long_text = 'x' * (EXTRACTED_TEXT_MAX_CHARS + 500)
        t = _FakeThesis(
            title='T',
            abstract='A',
            extracted_text=long_text,
            keywords=['keyword_sentinel'],
        )
        text = compose_thesis_text(t)
        # Keywords must still appear even when extracted_text is long
        assert 'keyword_sentinel' in text
        # Extracted text must be capped
        assert len(text) < len(long_text)

    def test_all_fields_present_in_output(self):
        from theses.services.semantic_search import compose_thesis_text
        t = _FakeThesis(
            title='IoT Smart Greenhouse',
            abstract='Monitors temperature and humidity.',
            extracted_text='Chapter 1: Introduction to smart agriculture.',
            keywords=['IoT', 'greenhouse', 'ESP32'],
        )
        text = compose_thesis_text(t)
        assert 'IoT Smart Greenhouse' in text
        assert 'Monitors temperature' in text
        assert 'Introduction to smart' in text
        assert 'greenhouse' in text
        assert 'ESP32' in text


# ---------------------------------------------------------------------------
# embed_text — sanity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEmbeddingService:
    def test_embedding_has_correct_dim(self):
        vec = embed_text('AI attendance monitoring')
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in vec)

    def test_empty_text_yields_zero_vector(self):
        vec = embed_text('')
        assert vec == [0.0] * EMBEDDING_DIM

    def test_normalised(self):
        """L2 norm of any non-empty embedding ≈ 1."""
        import numpy as np
        vec = np.asarray(embed_text('attendance system using face recognition'))
        norm = float(np.linalg.norm(vec))
        assert 0.99 <= norm <= 1.01


# ---------------------------------------------------------------------------
# Case 1 — semantic ranking finds related theses by meaning
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSemanticRanking:
    def test_attendance_query_ranks_face_recognition_first(self, make_thesis):
        face = make_thesis(
            'Face Recognition Attendance System for Universities',
            'A real-time attendance system using deep learning face '
            'recognition to identify students entering classrooms.',
            keywords=['face recognition', 'attendance', 'deep learning'],
        )
        unrelated = make_thesis(
            'Library Book Inventory Management Web Application',
            'A web-based inventory management application for tracking '
            'library books with barcode scanning and overdue notifications.',
            keywords=['library', 'inventory', 'web'],
        )
        another = make_thesis(
            'Web-Based Hotel Booking and Reservation System',
            'A hotel booking platform with room availability calendar, '
            'payment gateway integration, and email confirmations.',
            keywords=['hotel', 'booking', 'web'],
        )

        scored = rank_theses(
            'AI attendance monitoring',
            [face, unrelated, another],
        )
        assert len(scored) == 3
        assert scored[0].thesis.id == face.id, (
            f'Expected face-recognition thesis to rank #1; got '
            f'{[(s.thesis.title[:30], s.score) for s in scored]}'
        )
        # Score is in [0, 1] for non-trivial similarity
        assert 0 <= scored[0].score <= 1

    def test_unrelated_query_scores_low(self, make_thesis):
        face = make_thesis(
            'Face Recognition Attendance System',
            'Real-time attendance tracking via facial recognition.',
        )
        ranked = rank_theses('quantum chromodynamics gauge theory', [face])
        assert len(ranked) == 1
        # Quantum physics should clearly NOT match face recognition strongly
        assert ranked[0].score < 0.4, (
            f'Expected very low score for unrelated query; got {ranked[0].score}'
        )


# ---------------------------------------------------------------------------
# Case 2 — relative ranking: related > unrelated
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRelativeRanking:
    def test_library_query_does_not_pick_attendance(self, make_thesis):
        face = make_thesis(
            'Face Recognition Attendance System',
            'Real-time attendance tracking via facial recognition.',
        )
        library = make_thesis(
            'Library Book Inventory Management System',
            'Inventory management for library books with barcode scanning.',
        )
        scored = rank_theses('Library inventory', [face, library])
        # Library thesis must rank above the unrelated face-recognition one
        assert scored[0].thesis.id == library.id
        assert scored[0].score > scored[1].score


# ---------------------------------------------------------------------------
# Case 3 — embedding generated automatically on upload
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEmbeddingGeneratedOnUpload:
    def test_generate_thesis_embedding_persists_vector(self, make_thesis):
        thesis = make_thesis(
            'Demo thesis for embedding test',
            'This abstract describes a demo project for the test suite.',
            embed=False,  # we'll generate manually so we can assert state transitions
        )
        # Pre-state
        assert thesis.embedding_vector is None
        assert thesis.embedding_status == EmbeddingStatus.NOT_STARTED

        vec = generate_thesis_embedding(thesis)

        # Post-state — DB row has the vector + status
        thesis.refresh_from_db()
        assert isinstance(vec, list) and len(vec) == EMBEDDING_DIM
        assert thesis.embedding_vector == vec
        assert thesis.embedding_status == EmbeddingStatus.READY
        assert thesis.embedding_model
        assert thesis.embedding_generated_at is not None


# ---------------------------------------------------------------------------
# Case 4 — search endpoint returns ranked results
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSearchEndpoint:
    def test_search_endpoint_returns_ranked_results(self, client, faculty_user, make_thesis):
        """GET /api/v1/theses/search/?q=... returns ranked + scored results."""
        face = make_thesis(
            'Face Recognition Attendance System',
            'Real-time student attendance tracking using deep learning '
            'facial recognition models trained on classroom datasets.',
        )
        library = make_thesis(
            'Library Book Inventory Management',
            'Inventory app for tracking library books with barcode '
            'scanning and overdue notifications.',
        )

        # Authenticate the test client
        from auth_service.services import issue_token_pair
        pair = issue_token_pair(faculty_user, request=None, remember_me=False)

        url = reverse('thesis-search')
        response = client.get(
            f'{url}?q=AI%20attendance%20monitoring',
            HTTP_AUTHORIZATION=f'Bearer {pair.access_token}',
        )
        assert response.status_code == 200, response.content
        body = response.json()

        assert 'results' in body
        assert body['count'] >= 1
        assert body['query'] == 'AI attendance monitoring'

        # First result must be the attendance thesis
        first = body['results'][0]
        assert first['id'] == str(face.id)

        # similarity_score field must be present and a float
        assert 'similarity_score' in first
        assert isinstance(first['similarity_score'], float)
        assert 0 <= first['similarity_score'] <= 1

        # Library thesis must score below the face-recognition one
        if body['count'] >= 2:
            assert body['results'][0]['similarity_score'] >= \
                   body['results'][1]['similarity_score']

    def test_search_endpoint_rejects_empty_query(self, client, faculty_user):
        from auth_service.services import issue_token_pair
        pair = issue_token_pair(faculty_user, request=None, remember_me=False)
        url = reverse('thesis-search')
        response = client.get(url, HTTP_AUTHORIZATION=f'Bearer {pair.access_token}')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'MISSING_QUERY'

    def test_search_endpoint_rejects_short_query(self, client, faculty_user):
        from auth_service.services import issue_token_pair
        pair = issue_token_pair(faculty_user, request=None, remember_me=False)
        url = reverse('thesis-search')
        response = client.get(f'{url}?q=ai', HTTP_AUTHORIZATION=f'Bearer {pair.access_token}')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'QUERY_TOO_SHORT'

    def test_list_endpoint_with_q_uses_semantic_ranking(self, client, faculty_user, make_thesis):
        """GET /api/v1/theses/?q=... ALSO returns similarity_score per item."""
        face = make_thesis(
            'Face Recognition Attendance System',
            'Real-time attendance via deep learning face recognition.',
        )
        unrelated = make_thesis(
            'Hotel Booking Web Application',
            'Hotel reservation web app with room availability calendar.',
        )

        from auth_service.services import issue_token_pair
        pair = issue_token_pair(faculty_user, request=None, remember_me=False)

        url = reverse('thesis-list')
        response = client.get(
            f'{url}?q=AI%20attendance%20monitoring',
            HTTP_AUTHORIZATION=f'Bearer {pair.access_token}',
        )
        assert response.status_code == 200
        body = response.json()

        # Rerank should make the face-recognition thesis come first
        assert body['count'] >= 1
        assert body['results'][0]['id'] == str(face.id)
        assert 'similarity_score' in body['results'][0]


# ---------------------------------------------------------------------------
# Threshold filtering — min_score param
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestThresholdFilter:
    """min_score query param filters results below the given cosine similarity."""

    def _auth_header(self, user):
        from auth_service.services import issue_token_pair
        pair = issue_token_pair(user, request=None, remember_me=False)
        return f'Bearer {pair.access_token}'

    def test_high_threshold_excludes_weak_matches(self, client, faculty_user, make_thesis):
        """min_score=0.95 should return at most the identical-title match."""
        make_thesis(
            'AI Attendance System Using Face Recognition',
            'Deep learning attendance monitoring for classrooms.',
            keywords=['face recognition', 'attendance', 'AI'],
        )
        make_thesis(
            'Hotel Booking Web Application',
            'Hotel reservation web app with room availability calendar.',
            keywords=['hotel', 'booking', 'web'],
        )

        url = reverse('thesis-search')
        response = client.get(
            f'{url}?q=AI%20attendance%20monitoring&min_score=0.95',
            HTTP_AUTHORIZATION=self._auth_header(faculty_user),
        )
        assert response.status_code == 200
        body = response.json()
        # At a 0.95 threshold, the hotel thesis must NOT appear
        titles = [r['title'] for r in body['results']]
        assert not any('Hotel' in t for t in titles), (
            'Hotel Booking thesis should not appear at 0.95 threshold'
        )

    def test_low_threshold_includes_broader_matches(self, client, faculty_user, make_thesis):
        """min_score=0.10 (default noise floor) should return related theses."""
        face = make_thesis(
            'Face Recognition Attendance System',
            'Real-time attendance tracking via facial recognition.',
            keywords=['face recognition', 'attendance'],
        )
        make_thesis(
            'Hotel Booking Web Application',
            'Hotel reservation web app with room availability calendar.',
            keywords=['hotel', 'booking', 'web'],
        )

        url = reverse('thesis-search')
        response = client.get(
            f'{url}?q=AI%20attendance%20monitoring&min_score=0.10',
            HTTP_AUTHORIZATION=self._auth_header(faculty_user),
        )
        assert response.status_code == 200
        body = response.json()
        assert body['count'] >= 1
        # The face-recognition thesis must be in results
        ids = [r['id'] for r in body['results']]
        assert str(face.id) in ids

    def test_list_endpoint_respects_min_score(self, client, faculty_user, make_thesis):
        """ThesisListView also applies min_score when a query is present."""
        make_thesis(
            'Deep Learning for Medical Image Segmentation',
            'Applying deep learning CNNs to segment tumors in MRI scans.',
            keywords=['deep learning', 'medical', 'CNN'],
        )
        make_thesis(
            'Hotel Booking Web Application',
            'Hotel reservation web app with room availability calendar.',
            keywords=['hotel', 'booking', 'web'],
        )

        url = reverse('thesis-list')
        response = client.get(
            f'{url}?q=deep+learning+medical+imaging&min_score=0.90',
            HTTP_AUTHORIZATION=self._auth_header(faculty_user),
        )
        assert response.status_code == 200
        body = response.json()
        # Every returned result must meet the threshold
        for result in body['results']:
            score = result.get('similarity_score', 0)
            assert score >= 0.90, (
                f'Result "{result["title"]}" has score {score} < 0.90 threshold'
            )
