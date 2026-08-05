"""Phase 2B — Title Similarity Validation tests.

Covers:
  * Threshold classification (HIGHLY_SIMILAR / MODERATELY_SIMILAR / LOW_SIMILARITY)
  * Recommendation messages
  * rank_titles ranks duplicate-flavoured candidates highest
  * classify_title produces the correct classification end-to-end
  * The /api/v1/theses/validate-title/ endpoint:
      - returns 200 with the full envelope shape
      - rejects empty / too-short titles
      - matches "AI-Based Attendance Monitoring" against the attendance thesis
      - "Library Inventory Management" matches inventory-related theses
      - "Quantum Cryptography Implementation" yields LOW_SIMILARITY
      - requires authentication
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus
from theses.services.semantic_search import generate_thesis_embedding
from theses.services.title_similarity import (
    CLASS_HIGH,
    CLASS_LOW,
    CLASS_MODERATE,
    THRESHOLD_HIGH,
    THRESHOLD_MODERATE,
    classify,
    classify_title,
    rank_titles,
    recommendation_for,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='facultyt@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Tester',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, faculty_user):
    """Factory: creates an APPROVED thesis with embedding generated."""
    counter = {'n': 0}

    def _make(title: str, abstract: str = '', keywords=None, *, embed=True):
        counter['n'] += 1
        n = counter['n']
        sha = (f'{n:x}' + 'a' * 64)[:64]
        from django.core.files.base import ContentFile

        thesis = Thesis(
            title=title,
            abstract=abstract or f'Abstract for {title}',
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
            f'thesis_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        if embed:
            generate_thesis_embedding(thesis)
        return thesis

    return _make


# ---------------------------------------------------------------------------
# classify() — threshold cut-offs
# ---------------------------------------------------------------------------

class TestClassify:
    def test_high_threshold_inclusive(self):
        assert classify(THRESHOLD_HIGH) == CLASS_HIGH
        assert classify(0.91) == CLASS_HIGH
        assert classify(1.0) == CLASS_HIGH

    def test_moderate_band(self):
        assert classify(THRESHOLD_MODERATE) == CLASS_MODERATE
        assert classify(0.75) == CLASS_MODERATE
        assert classify(THRESHOLD_HIGH - 0.0001) == CLASS_MODERATE

    def test_low_band(self):
        assert classify(THRESHOLD_MODERATE - 0.0001) == CLASS_LOW
        assert classify(0.40) == CLASS_LOW
        assert classify(0.0) == CLASS_LOW
        assert classify(-0.5) == CLASS_LOW


class TestRecommendations:
    def test_high_recommendation_includes_revision_hint(self):
        msg = recommendation_for(CLASS_HIGH)
        assert 'highly similar' in msg.lower()
        assert 'revis' in msg.lower()

    def test_moderate_recommendation_mentions_acceptable(self):
        msg = recommendation_for(CLASS_MODERATE)
        assert 'similar' in msg.lower()
        assert 'acceptable' in msg.lower() or 'different' in msg.lower()

    def test_low_recommendation_says_distinct(self):
        msg = recommendation_for(CLASS_LOW)
        assert 'distinct' in msg.lower()


# ---------------------------------------------------------------------------
# rank_titles() — title-vs-title cosine similarity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRankTitles:
    def test_attendance_candidate_matches_attendance_thesis(self, make_thesis):
        face = make_thesis('Face Recognition Attendance System for Universities')
        library = make_thesis('Library Book Inventory Management Web Application')
        hotel = make_thesis('Web-Based Hotel Booking and Reservation System')

        scored = rank_titles(
            'AI-Based Attendance Monitoring System',
            [face, library, hotel],
        )

        assert len(scored) == 3
        assert scored[0].thesis.id == face.id
        # Attendance match should clearly beat library / hotel
        assert scored[0].score > scored[1].score

    def test_short_candidate_returns_empty(self, make_thesis):
        face = make_thesis('Face Recognition Attendance System')
        # 4 chars — below MIN_TITLE_LENGTH (5)
        assert rank_titles('abcd', [face]) == []
        assert rank_titles('   ', [face]) == []
        assert rank_titles('', [face]) == []

    def test_top_k_caps_results(self, make_thesis):
        a = make_thesis('Alpha System')
        b = make_thesis('Beta System')
        c = make_thesis('Gamma System')
        scored = rank_titles('System Implementation', [a, b, c], top_k=2)
        assert len(scored) == 2


# ---------------------------------------------------------------------------
# classify_title() — end-to-end pipeline
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClassifyTitleE2E:
    def test_near_duplicate_classified_high(self, make_thesis):
        face = make_thesis('AI-Powered Attendance Monitoring Using Facial Recognition')
        result = classify_title(
            'AI-Powered Attendance Monitoring Using Facial Recognition',
            [face],
        )
        # Identical-ish title against itself should be near-1.0
        assert result.classification == CLASS_HIGH
        assert result.similarity_score >= THRESHOLD_HIGH
        assert 'revis' in result.recommendation.lower()
        assert result.matches[0].thesis.id == face.id

    def test_unrelated_classified_low(self, make_thesis):
        face = make_thesis('Face Recognition Attendance System')
        library = make_thesis('Library Book Inventory Management')

        result = classify_title(
            'Quantum Cryptography Lattice-Based Implementation',
            [face, library],
        )
        assert result.classification == CLASS_LOW
        assert result.similarity_score < THRESHOLD_MODERATE
        assert 'distinct' in result.recommendation.lower()

    def test_empty_corpus_returns_low(self):
        result = classify_title('Some Proposed Title', [])
        assert result.classification == CLASS_LOW
        assert result.similarity_score == 0.0
        assert result.matches == []


# ---------------------------------------------------------------------------
# /api/v1/theses/validate-title/ endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidateTitleEndpoint:
    @staticmethod
    def _bearer(user):
        from auth_service.services import issue_token_pair
        return issue_token_pair(user, request=None, remember_me=False).access_token

    def test_endpoint_requires_authentication(self, client, make_thesis):
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'AI-Based Attendance Monitoring System'},
            content_type='application/json',
        )
        assert response.status_code == 401

    def test_endpoint_rejects_empty_title(self, client, faculty_user):
        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': ''},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'TITLE_TOO_SHORT'

    def test_endpoint_rejects_too_short(self, client, faculty_user):
        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'AI'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'TITLE_TOO_SHORT'

    def test_attendance_query_returns_high_match(self, client, faculty_user, make_thesis):
        face = make_thesis('AI-Powered Attendance Monitoring Using Facial Recognition')
        make_thesis('Library Book Inventory Management')

        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'AI-Based Attendance Monitoring System'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()

        # Envelope shape
        assert body['query'] == 'AI-Based Attendance Monitoring System'
        assert body['classification'] in (CLASS_HIGH, CLASS_MODERATE, CLASS_LOW)
        assert isinstance(body['similarity_score'], float)
        assert isinstance(body['recommendation'], str)
        assert isinstance(body['matches'], list)

        # The attendance thesis must be the top match
        assert len(body['matches']) >= 1
        assert body['matches'][0]['id'] == str(face.id)
        assert 0 <= body['matches'][0]['similarity'] <= 1
        # And the candidate is clearly close enough to be at least MODERATE
        assert body['classification'] in (CLASS_HIGH, CLASS_MODERATE)

    def test_library_query_matches_inventory_thesis(
        self, client, faculty_user, make_thesis,
    ):
        inv = make_thesis(
            'Web-Based Inventory Management System for Small Retail Businesses',
        )
        make_thesis('Face Recognition Attendance System')

        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'Library Inventory Management Web Application'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        assert body['matches'][0]['id'] == str(inv.id)

    def test_unrelated_query_returns_low(self, client, faculty_user, make_thesis):
        make_thesis('Face Recognition Attendance System')
        make_thesis('Library Book Inventory Management')

        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'Blockchain-Based Decentralized Voting Protocol'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        # The ranked list should still contain the corpus, but the top
        # similarity should be below the moderate threshold.
        assert body['similarity_score'] < THRESHOLD_MODERATE
        assert body['classification'] == CLASS_LOW
        assert 'distinct' in body['recommendation'].lower()

    def test_endpoint_excludes_pending_and_rejected(self, client, faculty_user, make_thesis):
        """Only APPROVED theses should appear in matches."""
        from theses.models import ThesisStatus

        approved = make_thesis('Public Approved Thesis on Attendance Systems')

        # Now make a pending one and a rejected one with overlapping titles
        pending = make_thesis('Hidden Pending Thesis on Attendance Systems', embed=True)
        pending.status = ThesisStatus.PENDING_REVIEW
        pending.save(update_fields=['status'])

        rejected = make_thesis('Rejected Thesis on Attendance Systems', embed=True)
        rejected.status = ThesisStatus.REJECTED
        rejected.save(update_fields=['status'])

        token = self._bearer(faculty_user)
        url = reverse('thesis-validate-title')
        response = client.post(
            url,
            data={'title': 'AI-Based Attendance Monitoring System'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        ids = {m['id'] for m in body['matches']}
        assert str(approved.id) in ids
        assert str(pending.id) not in ids
        assert str(rejected.id) not in ids
