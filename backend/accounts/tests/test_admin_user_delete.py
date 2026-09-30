"""Deleting a user in Django admin also removes their access request,
verification records and the uploaded ID file."""

import pytest
from django.test import override_settings
from django.urls import reverse

from accounts.models import Role, User
from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument, VerificationResult


def _student_with_verification(root, email):
    user = User.objects.create_user(
        email=email, password='Test12345!Test',
        first_name='Delete', last_name='Me', role=Role.STUDENT,
    )
    req = AccessRequest.objects.create(
        email=email, first_name='Delete', last_name='Me',
        requested_role='student', status='approved',
    )
    folder = root / str(req.pk)
    folder.mkdir(parents=True)
    (folder / 'abc.jpeg').write_bytes(b'\xff\xd8\xffid')
    VerificationDocument.objects.create(
        access_request=req, file_path=str(folder / 'abc.jpeg'),
        mime_type='image/jpeg', sha256='abc', size_bytes=5,
    )
    VerificationResult.objects.create(access_request=req, status='processing')
    return user, req, folder


@pytest.mark.django_db
@pytest.mark.parametrize('bulk', [False, True])
def test_admin_delete_removes_verification(
    client, tmp_path, bulk, django_capture_on_commit_callbacks,
):
    root = tmp_path / 'private_media' / 'verification_docs'
    with override_settings(PRIVATE_STORAGE_ROOT=tmp_path / 'private_media',
                           MEDIA_ROOT=tmp_path / 'media'):
        user, req, folder = _student_with_verification(root, 'gone@example.test')
        _, other_req, other_folder = _student_with_verification(root, 'stays@example.test')
        admin_user = User.objects.create_superuser(
            email='root@example.test', first_name='Ad', last_name='Min',
            password='Test12345!Test',
        )
        client.force_login(admin_user)

        # The folder is removed after commit; run those callbacks here.
        with django_capture_on_commit_callbacks(execute=True):
            if bulk:
                response = client.post(reverse('admin:accounts_user_changelist'), {
                    'action': 'delete_selected', '_selected_action': [str(user.pk)],
                    'post': 'yes',
                })
            else:
                response = client.post(
                    reverse('admin:accounts_user_delete', args=(user.pk,)), {'post': 'yes'},
                )
        assert response.status_code == 302

        assert not User.objects.filter(pk=user.pk).exists()
        assert not AccessRequest.objects.filter(pk=req.pk).exists()
        assert not VerificationDocument.objects.filter(access_request_id=req.pk).exists()
        assert not VerificationResult.objects.filter(access_request_id=req.pk).exists()
        assert not folder.exists()
        # Another user's verification is untouched.
        assert AccessRequest.objects.filter(pk=other_req.pk).exists()
        assert other_folder.exists()
