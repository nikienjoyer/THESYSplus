"""``manage.py list_acronym_candidates`` - "Long Form (ACR)" pairs found in
approved theses that the glossary does not have yet. Read-only."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


@pytest.fixture
def thesis_with(db):
    user = User.objects.create_user(
        email='acr@pampangastateu.edu.ph', first_name='A', last_name='C',
        role=Role.FACULTY, password='Test12345!Test',
    )

    def _make(abstract, n=1):
        thesis = Thesis(
            title=f'Thesis {n}', abstract=abstract, authors=['T, T.'], keywords=['k'],
            program=Program.BSIT.value, year=2024, file_type=FileType.PDF,
            sha256=(f'{n:x}' + 'b' * 64)[:64], extracted_text=abstract,
            status=ThesisStatus.APPROVED, uploaded_by=user,
        )
        thesis.uploaded_file.save(f'acr_{n}.pdf', ContentFile(b'%PDF-1.4'), save=False)
        thesis.save()
        return thesis

    return _make


def test_lists_unknown_pair_and_skips_known_terms(thesis_with):
    thesis_with('Uses a Learning Management System (LMS) and the '
                'Philippine Statistics Authority (PSA) dataset. '
                'Built on the Internet of Things (IoT).')
    out = StringIO()
    call_command('list_acronym_candidates', stdout=out)
    text = out.getvalue()
    assert 'PSA' in text and 'philippine statistics authority' in text
    assert 'IoT' not in text          # already in the glossary
    assert 'LMS' not in text          # already in the glossary
