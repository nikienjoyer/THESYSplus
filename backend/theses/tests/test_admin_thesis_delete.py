"""Deleting a thesis in Django admin lists and removes its files on disk:
the uploaded manuscript plus the cached watermarked copies, preview page
images and converted preview PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    return Path(settings.MEDIA_ROOT)


@pytest.fixture
def admin_client(client, db):
    admin_user = User.objects.create_superuser(
        email='thesis.delete.admin@example.test', first_name='Ad', last_name='Min',
        password='Test12345!Test',
    )
    client.force_login(admin_user)
    return client


def _thesis_with_files(n):
    student = User.objects.create_user(
        email=f'uploader{n}@example.test', password='Test12345!Test',
        first_name='Up', last_name='Loader', role=Role.STUDENT,
    )
    thesis = Thesis(
        title=f'Thesis {n}', abstract='Abstract', authors=['Tester, T.'],
        keywords=['test'], program=Program.BSIT.value, year=2024,
        file_type=FileType.PDF, sha256=(f'{n:x}' + 'd' * 64)[:64],
        status=ThesisStatus.APPROVED, uploaded_by=student,
    )
    thesis.uploaded_file.save(f'delete_me_{n}.pdf', ContentFile(b'%PDF-1.4\n'), save=False)
    thesis.save()
    cached = [
        f'theses/_watermarked/{thesis.id}/{thesis.sha256}-v1-inline.pdf',
        f'theses/_watermarked/{thesis.id}/{thesis.sha256}-v1-attachment.pdf',
        f'theses/_preview_pages/{thesis.id}/{thesis.sha256}-v1-p1.jpg',
        f'theses/_preview_sources/{thesis.id}/{thesis.sha256}.pdf',
    ]
    for name in cached:
        default_storage.save(name, ContentFile(b'x'))
    return thesis, [thesis.uploaded_file.name, *cached]


def test_delete_confirmation_lists_thesis_files(admin_client, media):
    thesis, files = _thesis_with_files(1)
    _thesis_with_files(2)

    response = admin_client.get(reverse('admin:theses_thesis_delete', args=(thesis.pk,)))
    assert response.status_code == 200
    assert not response.context['perms_lacking']

    counts = dict(response.context['model_count'])
    assert counts['uploaded files'] == 1
    assert counts['watermarked copies'] == 2
    assert counts['preview page images'] == 1
    assert counts['converted preview PDFs'] == 1
    body = response.content.decode()
    for name in files:
        assert name in body
    assert 'delete_me_2' not in body
    assert all((media / name).exists() for name in files)


def test_delete_removes_thesis_files(admin_client, media, django_capture_on_commit_callbacks):
    thesis, files = _thesis_with_files(1)
    other, other_files = _thesis_with_files(2)

    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse('admin:theses_thesis_delete', args=(thesis.pk,)), {'post': 'yes'},
        )
    assert response.status_code == 302

    assert not Thesis.objects.filter(pk=thesis.pk).exists()
    assert not any((media / name).exists() for name in files)
    for prefix in ('_watermarked', '_preview_pages', '_preview_sources'):
        assert not (media / 'theses' / prefix / str(thesis.id)).exists()
    # The other thesis keeps everything.
    assert Thesis.objects.filter(pk=other.pk).exists()
    assert all((media / name).exists() for name in other_files)


def test_shared_upload_is_not_deleted(admin_client, media, django_capture_on_commit_callbacks):
    """If another thesis row points at the same stored file, keep the file."""
    thesis, files = _thesis_with_files(1)
    other, _ = _thesis_with_files(2)
    Thesis.objects.filter(pk=other.pk).update(uploaded_file=thesis.uploaded_file.name)

    response = admin_client.get(reverse('admin:theses_thesis_delete', args=(thesis.pk,)))
    assert 'uploaded files' not in dict(response.context['model_count'])

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse('admin:theses_thesis_delete', args=(thesis.pk,)), {'post': 'yes'})
    assert (media / thesis.uploaded_file.name).exists()
