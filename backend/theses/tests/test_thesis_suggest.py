"""GET /api/v1/theses/suggest/ — typing suggestions for the search boxes.

Anonymous callers get keywords only (no titles or authors). Signed-in callers
get titles and authors from what they are allowed to see.
"""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email='student.sg@pampangastateu.edu.ph', first_name='Stu', last_name='Dent',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def other_student(db):
    return User.objects.create_user(
        email='other.sg@pampangastateu.edu.ph', first_name='Oth', last_name='Er',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    counter = {'n': 0}

    def _make(uploaded_by, title, keywords=(), authors=('Dela Cruz, Juan',),
              status=ThesisStatus.APPROVED, year=2024):
        counter['n'] += 1
        n = counter['n']
        t = Thesis(
            title=title, abstract=f'Abstract for {title}.', authors=list(authors),
            keywords=list(keywords), program=Program.BSIT.value, year=year,
            file_type=FileType.PDF, sha256=(f'{n:x}' + 'd' * 64)[:64],
            status=status, uploaded_by=uploaded_by,
        )
        t.uploaded_file.save(f'sg_{n}.pdf', ContentFile(b'%PDF-1.4\n%x'), save=False)
        t.save()
        return t

    return _make


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _get(client, q, user=None):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {_bearer(user)}'} if user else {}
    return client.get(reverse('thesis-suggest'), {'q': q}, **headers)


def test_short_query_returns_empty_lists(client, student):
    body = _get(client, 'a', student).json()
    assert body == {'titles': [], 'keywords': [], 'authors': []}


def test_anonymous_gets_keywords_only(client, student, make_thesis):
    make_thesis(student, 'RFID Attendance Monitoring System', keywords=['RFID', 'IoT'])
    r = _get(client, 'rfid')
    assert r.status_code == 200
    body = r.json()
    assert body['keywords'] == ['RFID']
    assert body['titles'] == [] and body['authors'] == []


def test_signed_in_gets_titles_and_authors(client, student, make_thesis):
    t = make_thesis(student, 'RFID Attendance Monitoring System', keywords=['RFID'],
                    authors=['Rivera, Ana'])
    body = _get(client, 'rfid', student).json()
    assert body['titles'] == [{'id': str(t.id), 'title': t.title, 'year': 2024}]
    assert _get(client, 'rive', student).json()['authors'] == ['Rivera, Ana']


def test_student_never_sees_others_pending_title(client, student, other_student, make_thesis):
    make_thesis(other_student, 'Pending Drone Mapping Study', status=ThesisStatus.PENDING_REVIEW)
    assert _get(client, 'drone', student).json()['titles'] == []


def test_keywords_dedupe_case_and_space_blind(client, student, make_thesis):
    make_thesis(student, 'Alpha thesis title here', keywords=['Machine  Learning'])
    make_thesis(student, 'Beta thesis title here', keywords=['machine learning'])
    assert _get(client, 'machine', student).json()['keywords'] == ['Machine Learning']


def test_long_and_odd_input_is_safe(client, student, make_thesis):
    make_thesis(student, 'Some thesis title words', keywords=['RFID'])
    for q in ['%_%', "o'reilly \"x\"", 'x' * 5000]:
        assert _get(client, q, student).status_code == 200


def test_anonymous_suggest_is_throttled_but_signed_in_is_not(client, student, monkeypatch):
    from django.core.cache import cache
    from theses.views import _SuggestAnonThrottle
    cache.clear()  # earlier anonymous GETs share this IP's throttle history
    monkeypatch.setattr(_SuggestAnonThrottle, 'rate', '2/min')
    codes = [_get(client, 'rf').status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert [_get(client, 'rf', student).status_code for _ in range(3)] == [200, 200, 200]
