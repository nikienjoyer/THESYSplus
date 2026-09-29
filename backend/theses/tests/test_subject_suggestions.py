"""Top-2 subject suggestions (theses/services/subject_suggestions.py) and
GET /api/v1/theses/<id>/subject-suggestions/."""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from theses.models import FileType, Program, ResearchSubject, Thesis, ThesisStatus


def _vec(*values):
    vector = [0.0] * 384
    for index, value in enumerate(values):
        vector[index] = value
    return vector


@pytest.fixture
def faculty(db):
    return User.objects.create_user(
        email='suggest-faculty@pampangastateu.edu.ph', first_name='F', last_name='S',
        role=Role.FACULTY, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(faculty):
    counter = {'n': 0}

    def _make(vector, subject_code=None, status=ThesisStatus.APPROVED):
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=f'Suggestion Thesis {n}', abstract='Abstract.', authors=['T, T.'], keywords=['k'],
            program=Program.BSIT.value, year=2024, adviser='', file_type=FileType.PDF,
            sha256=(f'{n:x}' + 'd' * 64)[:64], extracted_text='', status=status,
            uploaded_by=faculty, embedding_vector=vector,
        )
        if subject_code:
            thesis.primary_subject = ResearchSubject.objects.get(pk=subject_code)
            thesis.subject_reviewed_by = faculty
            thesis.subject_reviewed_at = timezone.now()
        thesis.uploaded_file.save(f'suggest_{n}.pdf', ContentFile(b'%PDF-1.4'), save=False)
        thesis.save()
        return thesis

    return _make


class TestSuggestSubjects:
    def test_closest_subjects_come_first(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        make_thesis(_vec(0.9, 0.1), 'EDU')
        make_thesis(_vec(0.0, 1.0), 'HEA')
        make_thesis(_vec(0.0, 0.0, 1.0), 'AGR')
        target = make_thesis(_vec(0.8, 0.2))
        assert [s['code'] for s in suggest_subjects(target)] == ['EDU', 'HEA']

    def test_a_thesis_never_supports_its_own_suggestion(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        only_health = make_thesis(_vec(0.0, 1.0), 'HEA')
        assert [s['code'] for s in suggest_subjects(only_health)] == ['EDU']

    def test_fewer_than_two_when_few_subjects_are_reviewed(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        target = make_thesis(_vec(0.5, 0.5))
        assert [s['code'] for s in suggest_subjects(target)] == ['EDU']

    def test_no_vector_means_no_suggestions(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        assert suggest_subjects(make_thesis(None)) == []


@pytest.mark.django_db
class TestSubjectSuggestionsEndpoint:
    @staticmethod
    def _get(client, user, thesis):
        from auth_service.services import issue_token_pair
        token = issue_token_pair(user, request=None, remember_me=False).access_token
        return client.get(
            reverse('thesis-subject-suggestions', kwargs={'id': str(thesis.id)}),
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def test_faculty_get_suggestions(self, client, faculty, make_thesis):
        make_thesis(_vec(1.0), 'EDU')
        response = self._get(client, faculty, make_thesis(_vec(0.9, 0.1)))
        assert response.status_code == 200
        assert [s['code'] for s in response.json()['suggestions']] == ['EDU']

    def test_students_are_refused(self, client, make_thesis):
        student = User.objects.create_user(
            email='suggest-student@pampangastateu.edu.ph', first_name='S', last_name='T',
            role=Role.STUDENT, password='Test12345!Test',
        )
        assert self._get(client, student, make_thesis(_vec(1.0))).status_code == 403

    def test_unpublished_thesis_gets_no_suggestions(self, client, faculty, make_thesis):
        make_thesis(_vec(1.0), 'EDU')
        pending = make_thesis(_vec(1.0), status=ThesisStatus.PENDING_REVIEW)
        assert self._get(client, faculty, pending).json() == {'suggestions': []}

    def test_administrators_get_suggestions(self, client, make_thesis):
        admin = User.objects.create_user(
            email='suggest-admin@pampangastateu.edu.ph', first_name='A', last_name='D',
            role=Role.ADMINISTRATOR, password='Test12345!Test',
        )
        make_thesis(_vec(1.0), 'EDU')
        response = self._get(client, admin, make_thesis(_vec(0.9, 0.1)))
        assert response.status_code == 200
        assert [s['code'] for s in response.json()['suggestions']] == ['EDU']

    def test_unknown_and_malformed_ids_are_not_found(self, client, faculty):
        from auth_service.services import issue_token_pair
        token = issue_token_pair(faculty, request=None, remember_me=False).access_token
        for thesis_id in ('00000000-0000-0000-0000-000000000000', 'not-a-uuid'):
            response = client.get(
                reverse('thesis-subject-suggestions', kwargs={'id': thesis_id}),
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            assert response.status_code == 404, thesis_id
