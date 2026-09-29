"""Focused access, integrity and migration checks for private admin previews."""

import hashlib
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from accounts.models import Role, User
from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument


@pytest.fixture
def storage(tmp_path):
    with override_settings(
        MEDIA_ROOT=tmp_path / 'media',
        PRIVATE_STORAGE_ROOT=tmp_path / 'private_media',
    ):
        yield tmp_path


def make_document(root, *, kind='jpeg'):
    access_request = AccessRequest.objects.create(
        email='preview-applicant@example.test',
        first_name='Preview',
        last_name='Applicant',
        requested_role='student',
        status='pending',
    )
    content = {
        'pdf': b'%PDF-1.4\npreview',
        'jpeg': b'\xff\xd8\xffpreview',
        'png': b'\x89PNG\r\n\x1a\npreview',
    }[kind]
    digest = hashlib.sha256(content).hexdigest()
    suffix = {'pdf': '.pdf', 'jpeg': '.jpeg', 'png': '.png'}[kind]
    file_path = root / str(access_request.pk) / f'{digest}{suffix}'
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(content)
    document = VerificationDocument.objects.create(
        access_request=access_request,
        file_path=str(file_path),
        mime_type={'pdf': 'application/pdf', 'jpeg': 'image/jpeg', 'png': 'image/png'}[kind],
        sha256=digest,
        size_bytes=len(content),
    )
    return document, file_path, content


@pytest.mark.django_db
@pytest.mark.parametrize('kind', ['jpeg', 'png', 'pdf'])
def test_admin_preview_is_private_and_verifies_bytes(client, storage, kind):
    root = storage / 'private_media' / 'verification_docs'
    document, path, content = make_document(root, kind=kind)
    url = reverse('admin:identity_verification_verificationdocument_preview', args=(document.pk,))

    assert client.get(url).status_code == 302
    student = User.objects.create_user(
        email='staff-student@example.test', password='Test12345!Test',
        first_name='Staff', last_name='Student', role=Role.STUDENT,
    )
    student.is_staff = True
    student.save(update_fields=['is_staff'])
    client.force_login(student)
    assert client.get(url).status_code == 403

    admin_user = User.objects.create_superuser(
        email='preview-admin@example.test', password='Test12345!Test',
        first_name='Preview', last_name='Admin',
    )
    client.force_login(admin_user)
    detail = client.get(reverse('admin:identity_verification_verificationdocument_change', args=(document.pk,)))
    assert detail.status_code == 200
    assert ('Open PDF' if kind == 'pdf' else 'Uploaded verification document') in detail.content.decode()
    response = client.get(url)
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == content
    assert 'no-store' in response['Cache-Control']
    assert 'private' in response['Cache-Control']
    assert response['Content-Type'] == document.mime_type
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert client.get(f'/media/private/verification_docs/{document.access_request_id}/{path.name}').status_code == 404

    path.write_bytes(content + b'tampered')
    assert client.get(url).status_code == 404
    assert 'File unavailable' in client.get(
        reverse('admin:identity_verification_verificationdocument_change', args=(document.pk,))
    ).content.decode()
    path.unlink()
    assert client.get(url).status_code == 404
    document.purged_at = document.uploaded_at
    document.save(update_fields=['purged_at'])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_recorded_path_outside_private_storage_is_denied(client, storage):
    root = storage / 'private_media' / 'verification_docs'
    document, _path, _content = make_document(root)
    outside = storage / 'unrelated' / Path(document.file_path).name
    outside.parent.mkdir()
    outside.write_bytes(Path(document.file_path).read_bytes())
    document.file_path = str(outside)
    document.save(update_fields=['file_path'])
    admin_user = User.objects.create_superuser(
        email='path-admin@example.test', password='Test12345!Test',
        first_name='Path', last_name='Admin',
    )
    client.force_login(admin_user)
    url = reverse('admin:identity_verification_verificationdocument_preview', args=(document.pk,))
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_legacy_migration_is_verified_and_resumable(storage):
    old_root = storage / 'media' / 'private' / 'verification_docs'
    document, old_file, content = make_document(old_root)
    call_command('migrate_verification_documents')
    document.refresh_from_db()
    assert Path(document.file_path) == old_file

    call_command('migrate_verification_documents', apply=True)
    document.refresh_from_db()
    new_file = storage / 'private_media' / 'verification_docs' / str(document.access_request_id) / old_file.name
    assert Path(document.file_path) == new_file
    assert new_file.read_bytes() == content
    assert not old_file.exists()
    call_command('migrate_verification_documents', apply=True)

    new_file.write_bytes(content + b'tampered')
    with pytest.raises(Exception, match='mismatch'):
        call_command('migrate_verification_documents', apply=True)
