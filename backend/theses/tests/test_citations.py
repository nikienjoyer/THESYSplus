"""Citation links between repository theses, and finding them in reference lists."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import IntegrityError
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisCitation, ThesisStatus
from theses.services.citations import find_cited_theses, references_section


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email='cite.up@pampangastateu.edu.ph', first_name='Up', last_name='Loader',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    counter = {'n': 0}

    def _make(uploaded_by, title, authors=('Dela Cruz, Juan',), year=2022,
              status=ThesisStatus.APPROVED, text=''):
        counter['n'] += 1
        n = counter['n']
        t = Thesis(
            title=title, abstract=f'Abstract for {title}.', authors=list(authors),
            keywords=['x'], program=Program.BSIT.value, year=year,
            file_type=FileType.PDF, sha256=(f'{n:x}' + 'e' * 64)[:64],
            status=status, uploaded_by=uploaded_by, extracted_text=text,
        )
        t.uploaded_file.save(f'ct_{n}.pdf', ContentFile(b'%PDF-1.4\n%x'), save=False)
        t.save()
        return t

    return _make


REFS = """Chapter 1 ... body text ...
REFERENCES
Manalo, P. (2021). Smart Parking Availability Detection Using Ultrasonic Sensors. PSU.
Garcia, L. et al. 2022, A mobile app for something else entirely.
"""


def test_title_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors',
                        authors=['Manalo, Paolo'], year=2021)
    out = find_cited_theses(REFS)
    assert out == [{'id': str(cited.id), 'title': cited.title, 'year': 2021, 'match': 'title'}]


def test_author_year_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2022)
    assert find_cited_theses(REFS) == [
        {'id': str(cited.id), 'title': cited.title, 'year': 2022, 'match': 'author_year'},
    ]


def test_author_year_needs_same_line(uploader, make_thesis):
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2019)
    assert find_cited_theses(REFS) == []


def test_short_surname_ignored(uploader, make_thesis):
    make_thesis(uploader, 'Some Other Thesis Title', authors=['Li, Wei'], year=2022)
    assert find_cited_theses('REFERENCES\nLi, W. (2022). Unrelated.') == []


def test_excludes_self_and_unapproved(uploader, make_thesis):
    me = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'],
                year=2022, status=ThesisStatus.PENDING_REVIEW)
    assert find_cited_theses(REFS, exclude_id=me.id) == []


def test_no_heading_uses_tail(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    text = ('body ' * 400) + 'Smart Parking Availability Detection Using Ultrasonic Sensors'
    assert [c['id'] for c in find_cited_theses(text)] == [str(cited.id)]


def test_empty_text(db):
    assert find_cited_theses('') == []
    assert references_section('') == ''


def test_last_heading_wins():
    text = 'Contents\nReferences ... 88\nbody\nReferences\nthe real list'
    assert references_section(text).strip() == 'the real list'


def test_pair_is_unique_and_not_self(uploader, make_thesis):
    a = make_thesis(uploader, 'Thesis A title words')
    b = make_thesis(uploader, 'Thesis B title words')
    ThesisCitation.objects.create(citing=a, cited=b)
    with pytest.raises(IntegrityError):
        ThesisCitation.objects.create(citing=a, cited=b)


def test_self_citation_rejected(uploader, make_thesis):
    a = make_thesis(uploader, 'Thesis A title words')
    with pytest.raises(IntegrityError):
        ThesisCitation.objects.create(citing=a, cited=a)


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _auth(user):
    return {'HTTP_AUTHORIZATION': f'Bearer {_bearer(user)}'}


@pytest.fixture
def other(db):
    return User.objects.create_user(
        email='cite.other@pampangastateu.edu.ph', first_name='Ot', last_name='Her',
        role=Role.STUDENT, password='Test12345!Test',
    )


def _post(client, user, thesis, ids):
    return client.post(
        reverse('thesis-citations', args=[thesis.id]), {'cited_ids': ids},
        content_type='application/json', **_auth(user),
    )


def test_post_saves_valid_and_skips_bad_ids(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words', status=ThesisStatus.PENDING_REVIEW)
    good = make_thesis(uploader, 'Older approved thesis words')
    pending = make_thesis(uploader, 'Pending thesis title words', status=ThesisStatus.PENDING_REVIEW)
    r = _post(client, uploader, mine, [str(good.id), str(mine.id), str(pending.id),
                                       '00000000-0000-0000-0000-000000000000', 'not-a-uuid'])
    assert r.status_code == 200
    assert r.json() == {'count_saved': 1}
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id')) == [(mine.id, good.id)]


def test_post_is_idempotent(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    good = make_thesis(uploader, 'Older approved thesis words')
    _post(client, uploader, mine, [str(good.id)])
    r = _post(client, uploader, mine, [str(good.id)])
    assert r.status_code == 200
    assert ThesisCitation.objects.count() == 1


def test_post_forbidden_for_other_student(client, uploader, other, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    good = make_thesis(uploader, 'Older approved thesis words')
    assert _post(client, other, mine, [str(good.id)]).status_code == 403


def test_get_lists_approved_citing_only(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    a = make_thesis(uploader, 'Approved citing thesis words', year=2024)
    p = make_thesis(uploader, 'Pending citing thesis words', status=ThesisStatus.PENDING_REVIEW)
    ThesisCitation.objects.create(citing=a, cited=cited)
    ThesisCitation.objects.create(citing=p, cited=cited)
    body = client.get(reverse('thesis-citations', args=[cited.id]), **_auth(uploader)).json()
    assert body == {'count': 1, 'cited_by': [{'id': str(a.id), 'title': a.title, 'year': 2024}]}


def test_count_ignores_unapproved_citing(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    p = make_thesis(uploader, 'Pending citing thesis words', status=ThesisStatus.PENDING_REVIEW)
    ThesisCitation.objects.create(citing=p, cited=cited)
    rows = client.get(reverse('thesis-list'), **_auth(uploader)).json()['results']
    assert {r['id']: r['cited_by_count'] for r in rows}[str(cited.id)] == 0


def test_list_shows_cited_by_count(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    a = make_thesis(uploader, 'Approved citing thesis words')
    ThesisCitation.objects.create(citing=a, cited=cited)
    rows = client.get(reverse('thesis-list'), **_auth(uploader)).json()['results']
    assert {r['id']: r['cited_by_count'] for r in rows}[str(cited.id)] == 1


def test_detect_citations_dry_run_and_apply(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2022)
    citing = make_thesis(uploader, 'Newer thesis that cites things', text=REFS)

    out = StringIO()
    call_command('detect_citations', stdout=out)
    assert ThesisCitation.objects.count() == 0
    assert 'title' in out.getvalue() and 'author_year' in out.getvalue()

    call_command('detect_citations', '--apply', stdout=StringIO())
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id')) == [(citing.id, cited.id)]

    call_command('detect_citations', '--apply', stdout=StringIO())   # re-run is safe
    assert ThesisCitation.objects.count() == 1
