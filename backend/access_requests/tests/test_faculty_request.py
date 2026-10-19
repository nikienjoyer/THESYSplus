"""Faculty access requests: name + institutional email, no document, admin review.

Students keep the document-upload branch; the role picks the branch, not the
presence of a file.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from access_requests.models import AccessRequest

SUBMIT_URL_NAME = 'access-request-submit'
FACULTY_EMAIL = 'maria.santos@pampangastateu.edu.ph'
STUDENT_EMAIL = '2024000000@pampangastateu.edu.ph'
ORIGIN = 'http://localhost:5173'

# 1x1 transparent PNG.
PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01'
    b'\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


def _post(client, **overrides):
    body = {
        'first_name': 'Maria',
        'last_name': 'Santos',
        'email': FACULTY_EMAIL,
        'requested_role': 'faculty',
        **overrides,
    }
    return client.post(reverse(SUBMIT_URL_NAME), data=body, content_type='application/json', HTTP_ORIGIN=ORIGIN)


def code(res):
    return res.json()['error']['code']


@pytest.mark.django_db
def test_faculty_valid_email_creates_pending_request(client):
    res = _post(client)
    assert res.status_code == 201
    assert res.json()['decision'] == 'pending_manual_review'
    req = AccessRequest.objects.get(email=FACULTY_EMAIL)
    assert (req.status, req.requested_role, req.justification) == ('pending', 'faculty', None)


@pytest.mark.django_db
def test_faculty_all_digit_email_rejected(client):
    res = _post(client, email=STUDENT_EMAIL)
    assert res.status_code == 400 and code(res) == 'FACULTY_EMAIL_LOOKS_LIKE_STUDENT'


@pytest.mark.django_db
def test_faculty_non_institutional_email_rejected(client):
    res = _post(client, email='maria@gmail.com')
    assert res.status_code == 400 and code(res) == 'INVALID_EMAIL_DOMAIN'


@pytest.mark.django_db
def test_faculty_with_document_is_unknown_field(client):
    res = client.post(reverse(SUBMIT_URL_NAME), data={
        'first_name': 'Maria', 'last_name': 'Santos', 'email': FACULTY_EMAIL,
        'requested_role': 'faculty',
        'document': SimpleUploadedFile('id.png', PNG, content_type='image/png'),
    }, HTTP_ORIGIN=ORIGIN)
    assert res.status_code == 400 and code(res) == 'UNKNOWN_FIELD'


@pytest.mark.django_db
def test_justification_is_unknown_field(client):
    res = _post(client, justification='I teach at CCS and advise thesis groups.')
    assert res.status_code == 400 and code(res) == 'UNKNOWN_FIELD'


@pytest.mark.django_db
def test_student_without_document_rejected(client):
    res = _post(client, email=STUDENT_EMAIL, requested_role='student')
    assert res.status_code == 400 and code(res) == 'DOCUMENT_REQUIRED'


@pytest.mark.django_db
def test_faculty_duplicate_pending_rejected(client):
    assert _post(client).status_code == 201
    second = _post(client)
    assert second.status_code == 409 and code(second) == 'DUPLICATE_REQUEST_PENDING'
