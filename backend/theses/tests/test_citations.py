"""Citation links between repository theses, and finding them in reference lists."""

from __future__ import annotations

from io import StringIO
from uuid import UUID

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
    assert out == [{'id': str(cited.id), 'title': cited.title, 'year': 2021}]


def test_shared_eight_word_prefix_is_not_a_match(uploader, make_thesis):
    make_thesis(uploader, 'Development of a Web-Based Student Information System for Lubao')
    refs = 'REFERENCES\nCruz, J. (2020). Development of a web-based student information system for Guagua.'
    assert find_cited_theses(refs) == []


def test_title_match_ignores_case_and_punctuation(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    refs = 'REFERENCES\nManalo (2021). SMART-PARKING availability detection: using ultrasonic\nsensors.'
    assert [c['id'] for c in find_cited_theses(refs)] == [str(cited.id)]


def test_title_inside_a_longer_reference_title_is_not_a_match(uploader, make_thesis):
    make_thesis(uploader, 'Library Management System for Schools')
    refs = ('REFERENCES\n'
            'Cruz, J. (2020). Online library management system for schools. PSU.\n'
            'Reyes, A. (2021). Library management system for schools in Lubao. PSU.')
    assert find_cited_theses(refs) == []


def test_apa_and_ieee_reference_styles_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Library Management System for Schools')
    for refs in ('REFERENCES\nCruz, J. (2020). Library management system for schools. PSU.',
                 'REFERENCES\n[3] J. Cruz, "Library management system for schools," PSU, 2020.',
                 'REFERENCES\nCruz, J. (2020).\nLibrary management system for schools [Undergraduate thesis].'):
        assert [c['id'] for c in find_cited_theses(refs)] == [str(cited.id)], refs


def test_reference_without_the_stored_titles_trailing_words_matches(uploader, make_thesis):
    """The stored title kept a cover-page line; the reference cites the real title."""
    cited = make_thesis(uploader, 'DEVELOPMENT OF AN AI-POWERED STUDENT ACADEMIC PERFORMANCE '
                                  'MONITORING SYSTEM A Sample Undergraduate Thesis Manuscript')
    refs = ('REFERENCES\nReyes, M. A. (2026). Development of an AI-powered student academic '
            'performance monitoring system [Unpublished sample thesis manuscript].')
    assert [c['id'] for c in find_cited_theses(refs)] == [str(cited.id)]


def test_shared_first_eight_words_with_more_after_is_not_a_match(uploader, make_thesis):
    make_thesis(uploader, 'Development of a Web-Based Student Information System for Lubao National High School')
    refs = 'REFERENCES\nCruz (2020). Development of a web-based student information system for Guagua.'
    assert find_cited_theses(refs) == []


def test_ligatures_and_decomposed_accents_still_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Peñaflor Barangay Profiling and Identification System')
    refs = 'REFERENCES\nCruz (2022). Peñaflor barangay profiling and identiﬁcation system. PSU.'
    assert [c['id'] for c in find_cited_theses(refs)] == [str(cited.id)]


def test_short_title_never_matches(uploader, make_thesis):
    make_thesis(uploader, 'Inventory System', authors=['Garcia, Liza'])
    assert find_cited_theses('REFERENCES\nGarcia (2022). Inventory system for a store.') == []


def test_excludes_self_and_unapproved(uploader, make_thesis):
    me = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'],
                year=2022, status=ThesisStatus.PENDING_REVIEW)
    assert find_cited_theses(REFS, exclude_id=me.id) == []


def test_no_heading_uses_tail(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    text = ('body ' * 400) + '\nSmart Parking Availability Detection Using Ultrasonic Sensors'
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


def test_post_citations_not_allowed(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    r = client.post(reverse('thesis-citations', args=[mine.id]), {},
                    content_type='application/json', **_auth(uploader))
    assert r.status_code == 405


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
    assert cited.title[:50] in out.getvalue()

    call_command('detect_citations', '--apply', stdout=StringIO())
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id')) == [(citing.id, cited.id)]

    call_command('detect_citations', '--apply', stdout=StringIO())   # re-run is safe
    assert ThesisCitation.objects.count() == 1


@pytest.fixture
def faculty(db):
    return User.objects.create_user(
        email='cite.fac@pampangastateu.edu.ph', first_name='Fa', last_name='Culty',
        role=Role.FACULTY, password='Test12345!Test',
    )


@pytest.fixture
def upload_env(settings, tmp_path):
    settings.DOCUMENT_PROCESSING_ASYNC = False
    settings.MEDIA_ROOT = str(tmp_path / 'media')


def _upload(client, user, extra_lines):
    """Real upload path (sync) with a PDF whose text ends with ``extra_lines``."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from theses.tests.test_thesis_gate_integration import THESIS_LINES, _pdf_from_lines

    pdf = _pdf_from_lines(THESIS_LINES + list(extra_lines))
    return client.post(reverse('thesis-upload'), data={
        'title': 'A Mobile Health Records System For Rural Clinics',
        'abstract': 'An abstract comfortably longer than twenty characters.',
        'authors': '["Dela Cruz, Juan M."]', 'keywords': '["mobile health"]',
        'program': 'BS Information Technology', 'year': '2025', 'adviser': '',
        'file': SimpleUploadedFile('t.pdf', pdf, content_type='application/pdf'),
    }, **_auth(user))


SMART_PARKING = 'Smart Parking Availability Detection Using Ultrasonic Sensors'


def test_upload_saves_cited_theses(client, faculty, make_thesis, upload_env):
    cited = make_thesis(faculty, SMART_PARKING, year=2021)
    r = _upload(client, faculty, [cited.title])
    assert r.status_code == 201, r.content
    assert r.json()['cited'] == [{'id': str(cited.id), 'title': cited.title, 'year': 2021}]
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id', 'created_by_id')) == [
        (UUID(r.json()['id']), cited.id, faculty.id)]


def test_student_upload_saves_but_does_not_count_yet(client, uploader, faculty, make_thesis, upload_env):
    cited = make_thesis(faculty, SMART_PARKING, year=2021)
    r = _upload(client, uploader, [cited.title])
    assert r.status_code == 201, r.content
    assert r.json()['cited'][0]['id'] == str(cited.id)
    assert ThesisCitation.objects.count() == 1
    rows = client.get(reverse('thesis-list'), **_auth(uploader)).json()['results']
    assert {x['id']: x['cited_by_count'] for x in rows}[str(cited.id)] == 0


def test_worker_retry_after_commit_still_saves_and_returns_citations(faculty, make_thesis, upload_env):
    """A job attempt that committed the thesis then died is retried: the
    retry takes the 'already created by this job' path and must still save
    and return citations."""
    import uuid
    from types import SimpleNamespace
    from django.core.files.uploadedfile import SimpleUploadedFile
    from theses.tests.test_thesis_gate_integration import THESIS_LINES, _pdf_from_lines
    from theses.views import ThesisUploadView

    cited = make_thesis(faculty, SMART_PARKING, year=2021)
    pdf = _pdf_from_lines(THESIS_LINES + [cited.title])
    job_id = uuid.uuid4()

    def attempt():
        return ThesisUploadView()._process_synchronous(SimpleNamespace(
            FILES={'file': SimpleUploadedFile('t.pdf', pdf, content_type='application/pdf')},
            data={
                'title': 'A Mobile Health Records System For Rural Clinics',
                'abstract': 'An abstract comfortably longer than twenty characters.',
                'authors': '["Dela Cruz, Juan M."]', 'keywords': '["mobile health"]',
                'program': 'BS Information Technology', 'year': '2025', 'adviser': '',
            },
            user=faculty, processing_job_id=job_id, storage_year=2025,
        ))

    assert attempt().status_code == 201
    ThesisCitation.objects.all().delete()   # first attempt died before Step 8
    retry = attempt()
    assert retry.status_code == 201
    assert retry.data['cited'] == [{'id': str(cited.id), 'title': cited.title, 'year': 2021}]
    assert ThesisCitation.objects.filter(cited=cited).count() == 1


def test_upload_survives_detection_error(client, faculty, make_thesis, upload_env, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('detection broke')

    monkeypatch.setattr('theses.services.citations.find_cited_theses', boom)
    cited = make_thesis(faculty, SMART_PARKING, year=2021)
    r = _upload(client, faculty, [cited.title])
    assert r.status_code == 201, r.content
    assert r.json()['cited'] == []
    assert ThesisCitation.objects.count() == 0
