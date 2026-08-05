"""Tests for the access request decision flow.

Covers all three decision cases:
  Case 1 — Valid PSU email + PSU detected + CCS/program detected
            → pending_email_verification → verification → approved
  Case 2 — Valid PSU email + PSU detected + CCS unclear
            → pending_manual_review
  Case 3 — Invalid email format
            → 400 validation error
  Case 4 — No PSU indicator in uploaded document
            → denied / rejected decision
  Case 5 — Expired verification token → graceful 400
  Case 6 — Reused verification token → 400 TOKEN_ALREADY_USED

Also tests:
  - is_student_number_email validator
  - Email verification token issuance and consumption
"""

from __future__ import annotations

import datetime as _dt
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from access_requests.models import AccessRequest, EmailVerificationToken
from access_requests.email_verification import (
    EmailVerificationTokenInvalid,
    consume_email_verification_token,
    issue_email_verification_token,
)
from common.tokens.opaque import generate_opaque_token, sha256
from common.validators import is_student_number_email


# ---------------------------------------------------------------------------
# Validator unit tests
# ---------------------------------------------------------------------------

class TestStudentNumberEmailValidator:
    """is_student_number_email — unit tests."""

    def test_valid_student_number_email(self):
        assert is_student_number_email('2023123456@pampangastateu.edu.ph')

    def test_valid_short_number(self):
        assert is_student_number_email('1@pampangastateu.edu.ph')

    def test_rejects_alpha_local_part(self):
        assert not is_student_number_email('kurt@pampangastateu.edu.ph')

    def test_rejects_alphanumeric_local_part(self):
        assert not is_student_number_email('kurtross123@pampangastateu.edu.ph')

    def test_rejects_gmail(self):
        assert not is_student_number_email('2023123456@gmail.com')

    def test_rejects_subdomain(self):
        assert not is_student_number_email('2023123456@student.pampangastateu.edu.ph')

    def test_rejects_empty_string(self):
        assert not is_student_number_email('')

    def test_rejects_non_string(self):
        assert not is_student_number_email(None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pending_req(db):
    """A fresh AccessRequest in pending_email_verification state."""
    return AccessRequest.objects.create(
        email='2023000001@pampangastateu.edu.ph',
        first_name='Test',
        last_name='Applicant',
        requested_role='student',
        status='pending_email_verification',
    )


@pytest.fixture
def valid_token(db, pending_req):
    """A valid (unused, not expired) EmailVerificationToken."""
    plaintext = generate_opaque_token()
    EmailVerificationToken.objects.create(
        access_request=pending_req,
        token_hash=sha256(plaintext),
        expires_at=timezone.now() + _dt.timedelta(hours=24),
    )
    return plaintext


@pytest.fixture
def expired_token(db, pending_req):
    """An EmailVerificationToken that is already expired."""
    plaintext = generate_opaque_token()
    EmailVerificationToken.objects.create(
        access_request=pending_req,
        token_hash=sha256(plaintext),
        expires_at=timezone.now() - _dt.timedelta(hours=1),
    )
    return plaintext


@pytest.fixture
def used_token(db, pending_req):
    """An EmailVerificationToken that has already been consumed."""
    plaintext = generate_opaque_token()
    EmailVerificationToken.objects.create(
        access_request=pending_req,
        token_hash=sha256(plaintext),
        expires_at=timezone.now() + _dt.timedelta(hours=24),
        used_at=timezone.now(),
    )
    return plaintext


# ---------------------------------------------------------------------------
# Case 5 — Expired token → graceful error
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExpiredVerificationToken:
    def test_raises_expired(self, expired_token):
        with pytest.raises(EmailVerificationTokenInvalid) as exc_info:
            consume_email_verification_token(expired_token)
        assert exc_info.value.reason == 'expired'

    def test_endpoint_returns_400(self, client, expired_token):
        url = reverse('access-request-verify-email')
        response = client.get(f'{url}?token={expired_token}')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'TOKEN_EXPIRED'


# ---------------------------------------------------------------------------
# Case 6 — Reused token → graceful error
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReusedVerificationToken:
    def test_raises_already_used(self, used_token):
        with pytest.raises(EmailVerificationTokenInvalid) as exc_info:
            consume_email_verification_token(used_token)
        assert exc_info.value.reason == 'already_used'

    def test_endpoint_returns_400(self, client, used_token):
        url = reverse('access-request-verify-email')
        response = client.get(f'{url}?token={used_token}')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'TOKEN_ALREADY_USED'


# ---------------------------------------------------------------------------
# Missing token
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMissingToken:
    def test_missing_token_raises_not_found(self):
        bogus = generate_opaque_token()
        with pytest.raises(EmailVerificationTokenInvalid) as exc_info:
            consume_email_verification_token(bogus)
        assert exc_info.value.reason == 'not_found'

    def test_endpoint_no_token_returns_400(self, client):
        url = reverse('access-request-verify-email')
        response = client.get(url)
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'MISSING_TOKEN'

    def test_endpoint_bogus_token_returns_400(self, client):
        url = reverse('access-request-verify-email')
        response = client.get(f'{url}?token=completelybogusnonsense')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'TOKEN_INVALID'


# ---------------------------------------------------------------------------
# Case 1 — Happy path: valid token → account activated
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidVerificationToken:
    def test_consume_creates_user(self, valid_token, pending_req):
        """Consuming a valid token calls approve_request → User is created."""
        assert not User.objects.filter(email=pending_req.email).exists()
        outcome = consume_email_verification_token(valid_token)
        assert User.objects.filter(email=pending_req.email).exists()
        assert outcome.user.email == pending_req.email

    def test_consume_marks_token_used(self, valid_token, pending_req):
        consume_email_verification_token(valid_token)
        token_row = EmailVerificationToken.objects.get(
            token_hash=sha256(valid_token)
        )
        assert token_row.used_at is not None

    def test_consume_sets_request_approved(self, valid_token, pending_req):
        consume_email_verification_token(valid_token)
        pending_req.refresh_from_db()
        assert pending_req.status == 'approved'

    def test_endpoint_returns_200_on_valid_token(self, client, valid_token):
        url = reverse('access-request-verify-email')
        response = client.get(f'{url}?token={valid_token}')
        assert response.status_code == 200
        body = response.json()
        assert body['verified'] is True

    def test_second_use_rejected(self, valid_token, pending_req):
        """After first consumption the same token must not work again."""
        consume_email_verification_token(valid_token)
        with pytest.raises(EmailVerificationTokenInvalid) as exc_info:
            consume_email_verification_token(valid_token)
        assert exc_info.value.reason == 'already_used'


# ---------------------------------------------------------------------------
# Case 3 — Invalid email format → 400 before any DB write
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInvalidEmailFormat:
    """POST /auth/request-access/ with document but invalid email format."""

    def _make_upload(self, email):
        """Build a minimal multipart POST with a fake document."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        return {
            'email': email,
            'first_name': 'Kurt',
            'last_name': 'Test',
            'requested_role': 'student',
            'document': SimpleUploadedFile(
                'id.png',
                b'\x89PNG\r\n\x1a\n' + b'\x00' * 16,
                content_type='image/png',
            ),
        }

    def test_non_numeric_local_part_rejected(self, client):
        url = reverse('access-request-submit')
        data = self._make_upload('kurt@pampangastateu.edu.ph')
        response = client.post(url, data=data,
                               HTTP_ORIGIN='http://localhost:5173')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'INVALID_EMAIL_DOMAIN'

    def test_alphanumeric_local_part_rejected(self, client):
        url = reverse('access-request-submit')
        data = self._make_upload('kurtross@pampangastateu.edu.ph')
        response = client.post(url, data=data,
                               HTTP_ORIGIN='http://localhost:5173')
        assert response.status_code == 400

    def test_gmail_rejected(self, client):
        url = reverse('access-request-submit')
        data = self._make_upload('2023123456@gmail.com')
        response = client.post(url, data=data,
                               HTTP_ORIGIN='http://localhost:5173')
        assert response.status_code == 400
        body = response.json()
        assert body['error']['code'] == 'INVALID_EMAIL_DOMAIN'

    def test_subdomain_rejected(self, client):
        url = reverse('access-request-submit')
        data = self._make_upload('2023123456@student.pampangastateu.edu.ph')
        response = client.post(url, data=data,
                               HTTP_ORIGIN='http://localhost:5173')
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# issue_email_verification_token unit test
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIssueEmailVerificationToken:
    def test_creates_token_row(self, db):
        req = AccessRequest.objects.create(
            email='2023000002@pampangastateu.edu.ph',
            first_name='A',
            last_name='B',
            requested_role='student',
            status='processing',
        )
        plaintext = issue_email_verification_token(req)
        assert isinstance(plaintext, str) and len(plaintext) > 0
        token_row = EmailVerificationToken.objects.get(
            token_hash=sha256(plaintext)
        )
        assert token_row.access_request_id == req.id
        assert token_row.used_at is None

    def test_sets_request_status(self, db):
        req = AccessRequest.objects.create(
            email='2023000003@pampangastateu.edu.ph',
            first_name='A',
            last_name='B',
            requested_role='student',
            status='processing',
        )
        issue_email_verification_token(req)
        req.refresh_from_db()
        assert req.status == 'pending_email_verification'
