"""Citation links between repository theses, and finding them in reference lists."""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.db import IntegrityError

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
