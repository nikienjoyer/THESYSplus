"""Phase 3B — Analytics Dashboard endpoint tests.

Covers:
  1. Authentication required
  2. Envelope shape (all expected keys present)
  3. Semantic-ready count matches theses with embedding_vector
  4. Pending review count visible to faculty/admin, hidden from student
  5. Program distribution sums to approved count
  6. Thesis growth only contains years of approved theses
  7. Top keywords extracted from thesis keyword metadata
  8. Topic summary keys present
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus
from theses.services.semantic_search import generate_thesis_embedding


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='faculty_a@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Analytics',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def student_user(db):
    return User.objects.create_user(
        email='student_a@pampangastateu.edu.ph',
        first_name='Student',
        last_name='Analytics',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, faculty_user):
    counter = {'n': 0}

    def _make(title='Test Thesis', program=Program.BSIT.value,
              year=2024, keywords=None, status=ThesisStatus.APPROVED, embed=False):
        counter['n'] += 1
        n = counter['n']
        sha = (f'{n:x}' + 'a' * 64)[:64]
        from django.core.files.base import ContentFile
        t = Thesis(
            title=title,
            abstract=f'Abstract for {title}.',
            authors=['Tester T.'],
            keywords=keywords or [],
            program=program,
            year=year,
            adviser='',
            file_type=FileType.PDF,
            sha256=sha,
            extracted_text='',
            status=status,
            uploaded_by=faculty_user,
        )
        t.uploaded_file.save(f'thesis_{n}.pdf', ContentFile(b'%PDF-1.4\n%dummy'), save=False)
        t.save()
        if embed:
            generate_thesis_embedding(t)
        return t

    return _make


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsEndpoint:

    URL = '/api/v1/theses/analytics/'

    def test_requires_authentication(self, client):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_envelope_shape(self, client, faculty_user, make_thesis):
        make_thesis('AI Thesis')
        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        for key in (
            'total_theses', 'approved_theses', 'semantic_ready',
            'recent_uploads_count', 'recent_uploads_days', 'most_active_program',
            'program_distribution', 'thesis_growth', 'top_keywords',
            'topic_summary', 'pending_review_count',
        ):
            assert key in body, f'Missing key: {key}'

    def test_semantic_ready_count(self, client, faculty_user, make_thesis):
        # Two theses with embeddings, one without
        t1 = make_thesis('AI Attendance System', embed=True)
        t2 = make_thesis('IoT Greenhouse Monitoring', embed=True)
        t3 = make_thesis('Library Inventory', embed=False)

        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['semantic_ready'] == 2
        assert body['approved_theses'] == 3

    def test_faculty_sees_pending_review_count(self, client, faculty_user, make_thesis):
        make_thesis('Approved Thesis')
        make_thesis('Pending Thesis', status=ThesisStatus.PENDING_REVIEW)

        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        assert body['pending_review_count'] == 1

    def test_student_sees_null_pending_count(self, client, student_user, make_thesis):
        make_thesis('Approved Thesis')
        token = _bearer(student_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        assert body['pending_review_count'] is None

    def test_program_distribution_sums_to_approved(self, client, faculty_user, make_thesis):
        make_thesis('BSIT Thesis 1', program=Program.BSIT.value)
        make_thesis('BSIT Thesis 2', program=Program.BSIT.value)
        make_thesis('BSCS Thesis 1', program=Program.BSCS.value)

        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        dist_total = sum(d['count'] for d in body['program_distribution'])
        assert dist_total == body['approved_theses']

    def test_thesis_growth_by_year(self, client, faculty_user, make_thesis):
        make_thesis('Thesis 2022', year=2022)
        make_thesis('Thesis 2023', year=2023)
        make_thesis('Thesis 2023 B', year=2023)

        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        growth = {r['year']: r['count'] for r in body['thesis_growth']}
        assert growth.get(2022) == 1
        assert growth.get(2023) == 2

    def test_top_keywords_extracted(self, client, faculty_user, make_thesis):
        make_thesis('AI Thesis', keywords=['AI', 'deep learning', 'attendance'])
        make_thesis('IoT Thesis', keywords=['IoT', 'AI', 'sensors'])

        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        keyword_names = [k['keyword'] for k in body['top_keywords']]
        # "ai" should appear (case-normalised) as it appears in both theses
        assert 'ai' in keyword_names

    def test_topic_summary_keys_present(self, client, faculty_user, make_thesis):
        make_thesis('Some Thesis')
        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        summary = body['topic_summary']
        for key in ('emerging_count', 'saturated_count', 'underexplored_count'):
            assert key in summary
            assert isinstance(summary[key], int)

    def test_empty_repository_returns_zeros(self, client, faculty_user):
        token = _bearer(faculty_user)
        response = client.get(self.URL, HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        assert body['total_theses'] == 0
        assert body['approved_theses'] == 0
        assert body['semantic_ready'] == 0
        assert body['program_distribution'] == []
        assert body['thesis_growth'] == []
