"""Test rate limiting for remaining endpoints.

Per Requirements 10.3, 10.4, 19.1, 19.2, 19.3 and design §8.2:
- POST /forgot-password: per-email 3/hour → RATE_LIMITED_FORGOT_PASSWORD
- POST /request-access: per-IP 5/hour → RATE_LIMITED_REQUEST_ACCESS
- POST /request-access: per-email 3/day, ID-check rejections excluded → RATE_LIMITED_REQUEST_ACCESS
- POST /reset-password: per-IP 10/hour → RATE_LIMITED_IP
- POST /reset-password: per-token 5/15min → RATE_LIMITED_RESET_PASSWORD
- POST /refresh: per-IP 60/min → RATE_LIMITED_IP

All 429 responses must include a Retry-After header.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from access_requests.models import AccessRequest
from access_requests.services import deny_request
from accounts.models import User
from password_reset.models import PasswordResetToken


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the cache before each test to ensure clean rate limit state."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def student_user(db):
    """Create a student user for testing."""
    return User.objects.create_user(
        email='student@pampangastateu.edu.ph',
        password='SecurePassword123',
        first_name='Test',
        last_name='Student',
        role='student',
        is_active=True,
    )


# ---------------------------------------------------------------------------
# POST /forgot-password rate limits
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestForgotPasswordRateLimit:
    """Test per-email rate limiting for forgot-password (3 per hour)."""

    def test_three_requests_allowed(self, client):
        """WHEN 3 forgot-password requests are made for the same email,
        THEN all 3 should return 200 (not rate limited yet)."""
        for i in range(3):
            response = client.post(
                '/api/v1/auth/forgot-password/',
                data={'email': 'student@pampangastateu.edu.ph'},
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

    def test_fourth_request_rate_limited(self, client):
        """WHEN 4 forgot-password requests are made for the same email,
        THEN the 4th should return 429 RATE_LIMITED_FORGOT_PASSWORD."""
        # First 3 requests
        for _ in range(3):
            response = client.post(
                '/api/v1/auth/forgot-password/',
                data={'email': 'student@pampangastateu.edu.ph'},
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.post(
            '/api/v1/auth/forgot-password/',
            data={'email': 'student@pampangastateu.edu.ph'},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_FORGOT_PASSWORD'
        assert body['error']['message'] == 'Too many requests. Please try again later.'
        assert 'Retry-After' in response

    def test_different_emails_have_separate_budgets(self, client):
        """WHEN requests are made for different emails,
        THEN each email has its own separate rate limit budget."""
        # Exhaust budget for first email
        for _ in range(3):
            client.post(
                '/api/v1/auth/forgot-password/',
                data={'email': 'user1@pampangastateu.edu.ph'},
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # Different email should still work
        response = client.post(
            '/api/v1/auth/forgot-password/',
            data={'email': 'user2@pampangastateu.edu.ph'},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /request-access rate limits
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRequestAccessPerIPRateLimit:
    """Test per-IP rate limiting for request-access (5 per hour)."""

    def test_five_requests_allowed(self, client):
        """WHEN 5 request-access submissions are made from the same IP,
        THEN all 5 should be processed (not rate limited yet)."""
        for i in range(5):
            response = client.post(
                '/api/v1/auth/request-access/',
                data={
                    'email': f'user{i}@pampangastateu.edu.ph',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'requested_role': 'student',
                    'justification': 'Need access for research',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 201, f"Request {i+1} should succeed"

    def test_sixth_request_rate_limited(self, client):
        """WHEN 6 request-access submissions are made from the same IP,
        THEN the 6th should return 429 RATE_LIMITED_REQUEST_ACCESS."""
        # First 5 requests
        for i in range(5):
            client.post(
                '/api/v1/auth/request-access/',
                data={
                    'email': f'user{i}@pampangastateu.edu.ph',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'requested_role': 'student',
                    'justification': 'Need access for research',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # 6th request should be rate limited
        response = client.post(
            '/api/v1/auth/request-access/',
            data={
                'email': 'user5@pampangastateu.edu.ph',
                'first_name': 'Test',
                'last_name': 'User',
                'requested_role': 'student',
                'justification': 'Need access for research',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_REQUEST_ACCESS'
        assert 'Retry-After' in response


def _submit_access_request(client, email='student@pampangastateu.edu.ph'):
    return client.post(
        '/api/v1/auth/request-access/',
        data={
            'email': email,
            'first_name': 'Test',
            'last_name': 'User',
            'requested_role': 'student',
            'justification': 'Need access for research',
        },
        content_type='application/json',
        HTTP_ORIGIN='http://localhost:5173',
    )


def _id_check_rejects_pending():
    """What the identity worker does to a rejected ID: denied, no reviewer."""
    AccessRequest.objects.filter(status='pending').update(status='denied')


def _admin_denies_pending(reviewer):
    for req in AccessRequest.objects.filter(status='pending'):
        deny_request(req, reviewer=reviewer, reason='Not eligible.')


def _being_checked(count, email='student@pampangastateu.edu.ph'):
    """Requests the ID check hasn't decided yet (any may still send an email)."""
    for _ in range(count):
        AccessRequest.objects.create(
            email=email, first_name='Test', last_name='User',
            requested_role='student', status='processing',
        )


@pytest.fixture
def reviewer(db):
    return User.objects.create_superuser(
        email='reviewer@pampangastateu.edu.ph', first_name='Re', last_name='Viewer',
        password='Str0ng!Passw0rd!2026',
    )


@pytest.mark.django_db
class TestRequestAccessPerEmailRateLimit:
    """Per-email limit for request-access: 3 per day, counting only requests
    that were not rejected by the ID check."""

    def test_rejected_tries_do_not_count(self, client):
        """WHEN the ID check rejects 3 submissions for the same email,
        THEN a 4th submission is still accepted."""
        for i in range(3):
            assert _submit_access_request(client).status_code == 201, f"Request {i+1} should succeed"
            _id_check_rejects_pending()

        assert _submit_access_request(client).status_code == 201

    def test_duplicate_submissions_do_not_count(self, client, reviewer):
        """WHEN 2 submissions bounce off a pending request (409),
        THEN they do not use up the email's tries."""
        assert _submit_access_request(client).status_code == 201
        for i in range(2):
            response = _submit_access_request(client)
            assert response.status_code == 409, f"Request {i+2} should return 409"
        _admin_denies_pending(reviewer)

        assert _submit_access_request(client).status_code == 201

    def test_fourth_counted_request_rate_limited(self, client, reviewer):
        """WHEN 3 submissions for the same email were not rejected by the ID
        check (here: denied by an administrator),
        THEN the 4th should return 429 RATE_LIMITED_REQUEST_ACCESS."""
        for i in range(3):
            assert _submit_access_request(client).status_code == 201, f"Request {i+1} should succeed"
            _admin_denies_pending(reviewer)

        response = _submit_access_request(client)
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_REQUEST_ACCESS'
        assert 'Retry-After' in response

    def test_requests_older_than_a_day_do_not_count(self, client, reviewer):
        """WHEN an email's 3 counted requests are more than a day old,
        THEN a new submission is accepted."""
        for i in range(3):
            assert _submit_access_request(client).status_code == 201, f"Request {i+1} should succeed"
            _admin_denies_pending(reviewer)
        AccessRequest.objects.update(created_at=timezone.now() - timedelta(days=1, minutes=1))

        assert _submit_access_request(client).status_code == 201

    def test_requests_still_being_checked_count(self, client):
        """WHEN 3 submissions for the same email are still being checked,
        THEN the 4th should return 429."""
        _being_checked(3)

        assert _submit_access_request(client).status_code == 429

    def test_requests_within_a_day_still_count(self, client):
        """WHEN an email's 3 counted requests are 23 hours old,
        THEN the next submission is still rate limited."""
        _being_checked(3)
        AccessRequest.objects.update(created_at=timezone.now() - timedelta(hours=23))

        assert _submit_access_request(client).status_code == 429


# ---------------------------------------------------------------------------
# POST /reset-password rate limits
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestResetPasswordPerIPRateLimit:
    """Test per-IP rate limiting for reset-password (10 per hour)."""

    def test_ten_attempts_allowed(self, client, student_user):
        """WHEN 10 reset-password attempts are made from the same IP,
        THEN all 10 should be processed (not rate limited yet)."""
        for i in range(10):
            response = client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': f'fake-token-{i}',
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            # Should return 400 (invalid token), not 429
            assert response.status_code == 400, f"Attempt {i+1} should not be rate limited"

    def test_eleventh_attempt_rate_limited(self, client, student_user):
        """WHEN 11 reset-password attempts are made from the same IP,
        THEN the 11th should return 429 RATE_LIMITED_IP."""
        # First 10 attempts
        for i in range(10):
            client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': f'fake-token-{i}',
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # 11th attempt should be rate limited
        response = client.post(
            '/api/v1/auth/reset-password/',
            data={
                'token': 'fake-token-10',
                'new_password': 'NewSecurePassword123',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_IP'
        assert 'Retry-After' in response


@pytest.mark.django_db
class TestResetPasswordPerTokenRateLimit:
    """Test per-token rate limiting for reset-password (5 per 15 minutes)."""

    def test_five_attempts_allowed(self, client, student_user):
        """WHEN 5 reset-password attempts are made with the same token,
        THEN all 5 should be processed (not rate limited yet)."""
        token = 'same-fake-token'
        for i in range(5):
            response = client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': token,
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            # Should return 400 (invalid token), not 429
            assert response.status_code == 400, f"Attempt {i+1} should not be rate limited"

    def test_sixth_attempt_rate_limited(self, client, student_user):
        """WHEN 6 reset-password attempts are made with the same token,
        THEN the 6th should return 429 RATE_LIMITED_RESET_PASSWORD."""
        token = 'same-fake-token'
        
        # First 5 attempts
        for _ in range(5):
            client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': token,
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # 6th attempt should be rate limited
        response = client.post(
            '/api/v1/auth/reset-password/',
            data={
                'token': token,
                'new_password': 'NewSecurePassword123',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_RESET_PASSWORD'
        assert 'Retry-After' in response

    def test_different_tokens_have_separate_budgets(self, client, student_user):
        """WHEN attempts are made with different tokens,
        THEN each token has its own separate rate limit budget."""
        # Exhaust budget for first token
        token1 = 'token-1'
        for _ in range(5):
            client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': token1,
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # Different token should still work
        token2 = 'token-2'
        response = client.post(
            '/api/v1/auth/reset-password/',
            data={
                'token': token2,
                'new_password': 'NewSecurePassword123',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        # Should return 400 (invalid token), not 429
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /refresh rate limits
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRefreshPerIPRateLimit:
    """Test per-IP rate limiting for refresh (60 per minute)."""

    def test_sixty_attempts_allowed(self, client):
        """WHEN 60 refresh attempts are made from the same IP,
        THEN all 60 should be processed (not rate limited yet)."""
        for i in range(60):
            response = client.post(
                '/api/v1/auth/refresh/',
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            # Should return 401 (missing cookie), not 429
            assert response.status_code == 401, f"Attempt {i+1} should not be rate limited"

    def test_sixty_first_attempt_rate_limited(self, client):
        """WHEN 61 refresh attempts are made from the same IP,
        THEN the 61st should return 429 RATE_LIMITED_IP."""
        # First 60 attempts
        for _ in range(60):
            client.post(
                '/api/v1/auth/refresh/',
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # 61st attempt should be rate limited
        response = client.post(
            '/api/v1/auth/refresh/',
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_IP'
        assert 'Retry-After' in response


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRateLimitRetryAfterHeader:
    """Test that all rate-limited responses include Retry-After header."""

    def test_forgot_password_includes_retry_after(self, client):
        """WHEN forgot-password is rate limited,
        THEN the response includes a Retry-After header."""
        # Trigger rate limit
        for _ in range(3):
            client.post(
                '/api/v1/auth/forgot-password/',
                data={'email': 'student@pampangastateu.edu.ph'},
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/forgot-password/',
            data={'email': 'student@pampangastateu.edu.ph'},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response
        retry_after = int(response['Retry-After'])
        assert retry_after > 0
        assert retry_after <= 3600  # Should be within the 1-hour window

    def test_request_access_includes_retry_after(self, client):
        """WHEN request-access is rate limited,
        THEN the response includes a Retry-After header."""
        # Trigger per-IP rate limit
        for i in range(5):
            client.post(
                '/api/v1/auth/request-access/',
                data={
                    'email': f'user{i}@pampangastateu.edu.ph',
                    'first_name': 'Test',
                    'last_name': 'User',
                    'requested_role': 'student',
                    'justification': 'Need access',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/request-access/',
            data={
                'email': 'user5@pampangastateu.edu.ph',
                'first_name': 'Test',
                'last_name': 'User',
                'requested_role': 'student',
                'justification': 'Need access',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response

    def test_reset_password_includes_retry_after(self, client):
        """WHEN reset-password is rate limited,
        THEN the response includes a Retry-After header."""
        # Trigger per-token rate limit
        token = 'same-token'
        for _ in range(5):
            client.post(
                '/api/v1/auth/reset-password/',
                data={
                    'token': token,
                    'new_password': 'NewSecurePassword123',
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/reset-password/',
            data={
                'token': token,
                'new_password': 'NewSecurePassword123',
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response

    def test_refresh_includes_retry_after(self, client):
        """WHEN refresh is rate limited,
        THEN the response includes a Retry-After header."""
        # Trigger rate limit
        for _ in range(60):
            client.post(
                '/api/v1/auth/refresh/',
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/refresh/',
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response
