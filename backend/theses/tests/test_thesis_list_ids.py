"""Tests for the ``ids`` filter on GET /api/v1/theses/.

Covers the cluster drill-down data path: the frontend resolves a topic
cluster's ``thesis_ids`` (already present in the topic-trends response) into
full thesis cards by requesting exactly those IDs from the list endpoint.

  1. ``ids=<comma-joined uuids>`` returns exactly the requested VISIBLE
     theses, with ``count`` equal to the filtered total.
  2. A malformed UUID anywhere in the list → 400 INVALID_FILTER.
  3. A student cannot retrieve another user's non-approved thesis via
     ``ids`` — it's layered on ``_visible_queryset``, never a bypass.
  4. Unknown/non-visible IDs are silently absent, not an error.
  5. Composes with ``page_size``.
  6. Too many IDs (over ``MAX_IDS``) → 400 INVALID_FILTER.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='faculty.ids@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Ids',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def student_a(db):
    return User.objects.create_user(
        email='student.a.ids@pampangastateu.edu.ph',
        first_name='Student',
        last_name='A',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def student_b(db):
    return User.objects.create_user(
        email='student.b.ids@pampangastateu.edu.ph',
        first_name='Student',
        last_name='B',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    """Factory: creates a Thesis uploaded by an arbitrary user."""
    counter = {'n': 0}

    def _make(uploaded_by, title='Test Thesis', program=Program.BSIT.value,
              year=2024, status=ThesisStatus.APPROVED, keywords=None):
        counter['n'] += 1
        n = counter['n']
        sha = (f'{n:x}' + 'b' * 64)[:64]
        from django.core.files.base import ContentFile

        thesis = Thesis(
            title=title,
            abstract=f'Abstract for {title}.',
            authors=['Tester, T.'],
            keywords=keywords or [],
            program=program,
            year=year,
            adviser='',
            file_type=FileType.PDF,
            sha256=sha,
            extracted_text='',
            status=status,
            uploaded_by=uploaded_by,
        )
        thesis.uploaded_file.save(
            f'thesis_ids_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        thesis.save()
        return thesis

    return _make


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIdsFilter:
    URL_NAME = 'thesis-list'

    def test_returns_exactly_the_requested_visible_theses(self, client, faculty_user, make_thesis):
        a = make_thesis(faculty_user, title='Alpha')
        b = make_thesis(faculty_user, title='Beta')
        make_thesis(faculty_user, title='Gamma')  # not requested

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={a.id},{b.id}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 2
        ids = {r['id'] for r in body['results']}
        assert ids == {str(a.id), str(b.id)}

    def test_malformed_uuid_returns_400(self, client, faculty_user, make_thesis):
        a = make_thesis(faculty_user, title='Alpha')
        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={a.id},not-a-uuid',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'INVALID_FILTER'

    def test_student_cannot_retrieve_another_users_non_approved_thesis(
        self, client, student_a, student_b, make_thesis,
    ):
        hidden = make_thesis(student_b, title='Hidden Pending', status=ThesisStatus.PENDING_REVIEW)

        token = _bearer(student_a)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={hidden.id}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        # Not an error — the ID simply doesn't match any row this student
        # can see, exactly like requesting an ID that doesn't exist at all.
        assert body['count'] == 0
        assert body['results'] == []

    def test_unknown_id_is_silently_absent(self, client, faculty_user, make_thesis):
        a = make_thesis(faculty_user, title='Alpha')
        unknown_id = uuid.uuid4()

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={a.id},{unknown_id}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['id'] == str(a.id)

    def test_composes_with_page_size(self, client, faculty_user, make_thesis):
        theses = [make_thesis(faculty_user, title=f'Thesis {i}') for i in range(10)]
        ids_param = ','.join(str(t.id) for t in theses)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={ids_param}&page_size=100',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 10
        assert len(body['results']) == 10

    def test_too_many_ids_returns_400(self, client, faculty_user):
        too_many = ','.join(str(uuid.uuid4()) for _ in range(301))
        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={too_many}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'INVALID_FILTER'

    def test_default_ordering_is_preserved(self, client, faculty_user, make_thesis):
        import time
        a = make_thesis(faculty_user, title='Older')
        b = make_thesis(faculty_user, title='Newer')

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?ids={a.id},{b.id}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        body = response.json()
        # Endpoint default ordering is -created_at (newest first); both were
        # created in this test in order a, then b — b should sort first.
        assert body['results'][0]['title'] == 'Newer'
        assert body['results'][1]['title'] == 'Older'

    def test_empty_ids_param_returns_empty_visible_narrowing(self, client, faculty_user, make_thesis):
        # An `ids=` with no actual values parses to an empty list, which
        # `id__in=[]` matches nothing — this documents that behaviour rather
        # than asserting it's ideal; the frontend is responsible for never
        # firing a request with no IDs (see Task 2 edge cases).
        make_thesis(faculty_user, title='Alpha')
        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?ids=', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        assert response.json()['count'] == 0
