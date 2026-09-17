"""Tests for the ``mine`` filter on GET /api/v1/theses/.

Covers the Profile "Uploaded" count fix:
  1. ``mine=true`` returns only the requesting user's own uploads, with an
     accurate (uncapped) ``count``.
  2. A student's own pending/rejected uploads are included via
     ``_visible_queryset``'s own-upload carve-out.
  3. No role can see another user's thesis through ``mine=true``.
  4. ``mine`` composes with ``year``, ``program``, ``status``, and ``q``.
  5. Invalid ``mine`` values are rejected with INVALID_FILTER, matching the
     convention already used by ``year`` and ``status``.
"""

from __future__ import annotations

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
        email='faculty.mine@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Mine',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email='admin.mine@pampangastateu.edu.ph',
        first_name='Admin',
        last_name='Mine',
        role=Role.ADMINISTRATOR,
        password='Test12345!Test',
    )


@pytest.fixture
def student_a(db):
    return User.objects.create_user(
        email='student.a.mine@pampangastateu.edu.ph',
        first_name='Student',
        last_name='A',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def student_b(db):
    return User.objects.create_user(
        email='student.b.mine@pampangastateu.edu.ph',
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
        sha = (f'{n:x}' + 'a' * 64)[:64]
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
            f'thesis_{n}.pdf',
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
class TestMineFilter:
    URL_NAME = 'thesis-list'

    def test_count_matches_uploads_for_faculty(self, client, faculty_user, make_thesis):
        make_thesis(faculty_user, title='Faculty Thesis 1')
        make_thesis(faculty_user, title='Faculty Thesis 2')
        make_thesis(faculty_user, title='Faculty Thesis 3')

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 3
        assert len(body['results']) == 3

    def test_zero_uploads_returns_zero_count(self, client, faculty_user):
        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 0
        assert body['results'] == []

    def test_count_is_not_capped_by_page_size(self, client, faculty_user, make_thesis):
        # Upload more than the default page_size=5 the frontend requests,
        # and more than the pagination page_size=20 default too, to prove
        # `count` reflects the filtered total, not a page length.
        for i in range(7):
            make_thesis(faculty_user, title=f'Bulk Thesis {i}')

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true&page_size=5', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 7
        assert len(body['results']) == 5  # page is still capped; count is not

    def test_students_own_pending_upload_is_included(self, client, student_a, make_thesis):
        make_thesis(student_a, title='Pending Submission', status=ThesisStatus.PENDING_REVIEW)

        token = _bearer(student_a)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['title'] == 'Pending Submission'
        assert body['results'][0]['status'] == ThesisStatus.PENDING_REVIEW.value

    def test_students_rejected_upload_is_included(self, client, student_a, make_thesis):
        make_thesis(student_a, title='Rejected Submission', status=ThesisStatus.REJECTED)

        token = _bearer(student_a)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['status'] == ThesisStatus.REJECTED.value

    @pytest.mark.parametrize('requester_role_fixture', ['student_a', 'faculty_user', 'admin_user'])
    def test_never_returns_another_users_thesis(
        self, client, request, requester_role_fixture, student_b, make_thesis,
    ):
        # student_b uploads a thesis; the requester (of any role) must never
        # see it via mine=true, since it isn't theirs.
        make_thesis(student_b, title="Someone Else's Thesis")

        requester = request.getfixturevalue(requester_role_fixture)
        token = _bearer(requester)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 0
        titles = [r['title'] for r in body['results']]
        assert "Someone Else's Thesis" not in titles

    def test_composes_with_year_filter(self, client, faculty_user, make_thesis):
        make_thesis(faculty_user, title='2023 Thesis', year=2023)
        make_thesis(faculty_user, title='2024 Thesis', year=2024)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=true&year=2024', HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['title'] == '2024 Thesis'

    def test_composes_with_program_filter(self, client, faculty_user, make_thesis):
        make_thesis(faculty_user, title='BSIT Thesis', program=Program.BSIT.value)
        make_thesis(faculty_user, title='BSCS Thesis', program=Program.BSCS.value)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?mine=true&program={Program.BSCS.value}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['title'] == 'BSCS Thesis'

    def test_composes_with_status_filter(self, client, faculty_user, make_thesis):
        make_thesis(faculty_user, title='Approved One', status=ThesisStatus.APPROVED)
        make_thesis(faculty_user, title='Pending One', status=ThesisStatus.PENDING_REVIEW)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?mine=true&status={ThesisStatus.PENDING_REVIEW.value}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        body = response.json()
        assert body['count'] == 1
        assert body['results'][0]['title'] == 'Pending One'

    def test_composes_with_q_search(self, client, faculty_user, make_thesis, student_b):
        # rank_theses() only scores theses with a stored embedding_vector,
        # so both must be embedded for either to survive into `scored`.
        from theses.services.semantic_search import generate_thesis_embedding

        mine_thesis = make_thesis(faculty_user, title='Face Recognition Attendance System')
        others_thesis = make_thesis(student_b, title='Face Recognition For Security')  # not mine
        generate_thesis_embedding(mine_thesis)
        generate_thesis_embedding(others_thesis)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(
            f'{url}?mine=true&q=face+recognition&min_score=0',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        assert response.status_code == 200
        body = response.json()
        titles = [r['title'] for r in body['results']]
        assert 'Face Recognition Attendance System' in titles
        assert 'Face Recognition For Security' not in titles

    def test_invalid_mine_value_returns_400(self, client, faculty_user):
        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=maybe', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'INVALID_FILTER'

    def test_mine_false_returns_full_visible_set(self, client, faculty_user, student_b, make_thesis):
        make_thesis(faculty_user, title='Faculty Own Thesis')
        make_thesis(student_b, title='Student Thesis', status=ThesisStatus.APPROVED)

        token = _bearer(faculty_user)
        url = reverse(self.URL_NAME)
        response = client.get(f'{url}?mine=false', HTTP_AUTHORIZATION=f'Bearer {token}')
        body = response.json()
        # Faculty sees the full visible set (both theses) when mine=false.
        assert body['count'] == 2

    def test_two_accounts_get_different_counts(self, client, faculty_user, student_a, make_thesis):
        make_thesis(faculty_user, title='Faculty A')
        make_thesis(faculty_user, title='Faculty B')
        make_thesis(student_a, title='Student Thesis', status=ThesisStatus.PENDING_REVIEW)

        token_faculty = _bearer(faculty_user)
        token_student = _bearer(student_a)
        url = reverse(self.URL_NAME)

        resp_faculty = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token_faculty}')
        resp_student = client.get(f'{url}?mine=true', HTTP_AUTHORIZATION=f'Bearer {token_student}')

        assert resp_faculty.json()['count'] == 2
        assert resp_student.json()['count'] == 1
