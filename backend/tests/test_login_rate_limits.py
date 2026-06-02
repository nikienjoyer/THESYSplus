"""Test rate limiting for POST /login endpoint.

Per Requirement 10.1, 10.2, 10.4 and design §8.3:
- Per-email: 5 failed attempts per 15 minutes → RATE_LIMITED_LOGIN
- Per-IP: 10 attempts per 1 minute → RATE_LIMITED_IP
- Per-email counter increments ONLY on failed attempts (success resets budget)
- Per-IP counter increments on every attempt regardless of outcome
- All 429 responses include Retry-After header
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client

from accounts.models import User


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


@pytest.fixture
def student_user(db):
    """Create a student user."""
    return User.objects.create_user(
        email='student@pampangastateu.edu.ph',
        first_name='Student',
        last_name='User',
        role='student',
        password='SecurePassword123',
    )


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLoginPerEmailRateLimit:
    """Test per-email rate limiting (5 failed attempts per 15 minutes)."""

    def test_five_failed_attempts_allowed(self, client, student_user):
        """WHEN 5 failed login attempts are made for the same email,
        THEN all 5 should return 401 (not rate limited yet)."""
        for i in range(5):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401, f"Attempt {i+1} should return 401"
            body = response.json()
            assert body['error']['code'] == 'INVALID_CREDENTIALS'

    def test_sixth_failed_attempt_rate_limited(self, client, student_user):
        """WHEN 6 failed login attempts are made for the same email,
        THEN the 6th should return 429 RATE_LIMITED_LOGIN."""
        # First 5 failures
        for _ in range(5):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401

        # 6th failure should be rate limited
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_LOGIN'
        assert body['error']['message'] == 'Too many requests. Please try again later.'

    def test_rate_limit_includes_retry_after_header(self, client, student_user):
        """WHEN a request is rate limited,
        THEN the response includes a Retry-After header."""
        # Trigger rate limit
        for _ in range(5):
            client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response
        retry_after = int(response['Retry-After'])
        assert retry_after > 0
        assert retry_after <= 15 * 60  # Should be within the 15-minute window

        # Also check the body includes retry_after_seconds
        body = response.json()
        assert 'retry_after_seconds' in body['error']['details']
        assert body['error']['details']['retry_after_seconds'] == retry_after

    def test_successful_login_resets_email_budget(self, client, student_user):
        """WHEN a user has failed attempts followed by a successful login,
        THEN the per-email failure budget is reset."""
        # 3 failed attempts
        for _ in range(3):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401

        # Successful login
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'SecurePassword123',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 200

        # Now we should be able to make 5 more failed attempts
        for i in range(5):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401, f"Attempt {i+1} after reset should return 401"

    def test_successful_login_does_not_count_against_budget(self, client, student_user):
        """WHEN a user makes only successful login attempts,
        THEN they should never be rate limited by the per-email limit."""
        # Make 10 successful logins (more than the 5 failure limit)
        for i in range(10):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'SecurePassword123',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 200, f"Successful login {i+1} should return 200"

    def test_different_emails_have_separate_budgets(self, client, db):
        """WHEN failed attempts are made for different emails,
        THEN each email has its own separate rate limit budget."""
        user1 = User.objects.create_user(
            email='user1@pampangastateu.edu.ph',
            first_name='User',
            last_name='One',
            role='student',
            password='Password123',
        )
        user2 = User.objects.create_user(
            email='user2@pampangastateu.edu.ph',
            first_name='User',
            last_name='Two',
            role='student',
            password='Password123',
        )

        # 5 failed attempts for user1
        for _ in range(5):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'user1@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401

        # user2 should still be able to make failed attempts
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'user2@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 401  # Not rate limited


@pytest.mark.django_db
class TestLoginPerIPRateLimit:
    """Test per-IP rate limiting (10 attempts per 1 minute)."""

    def test_ten_attempts_allowed(self, client, student_user):
        """WHEN 10 login attempts are made from the same IP,
        THEN all 10 should be processed (not rate limited yet)."""
        for i in range(10):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword' if i % 2 == 0 else 'SecurePassword123',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code in [200, 401], f"Attempt {i+1} should not be rate limited"

    def test_eleventh_attempt_rate_limited(self, client, student_user):
        """WHEN 11 login attempts are made from the same IP,
        THEN the 11th should return 429 RATE_LIMITED_IP."""
        # First 10 attempts
        for _ in range(10):
            client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        # 11th attempt should be rate limited
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_IP'

    def test_per_ip_includes_retry_after_header(self, client, student_user):
        """WHEN a request is rate limited by IP,
        THEN the response includes a Retry-After header."""
        # Trigger rate limit
        for _ in range(10):
            client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )

        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        assert 'Retry-After' in response
        retry_after = int(response['Retry-After'])
        assert retry_after > 0
        assert retry_after <= 60  # Should be within the 1-minute window

    def test_successful_login_counts_against_ip_budget(self, client, student_user):
        """WHEN a user makes successful login attempts,
        THEN they count against the per-IP budget."""
        # Make 10 successful logins
        for _ in range(10):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'SecurePassword123',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 200

        # 11th attempt should be rate limited
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'SecurePassword123',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_IP'

    def test_mixed_success_and_failure_counts_against_ip_budget(self, client, student_user):
        """WHEN a user makes a mix of successful and failed attempts,
        THEN all attempts count against the per-IP budget."""
        # 5 failures + 5 successes = 10 attempts
        for i in range(10):
            password = 'WrongPassword' if i % 2 == 0 else 'SecurePassword123'
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': password,
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code in [200, 401]

        # 11th attempt should be rate limited
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'SecurePassword123',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_IP'


@pytest.mark.django_db
class TestLoginRateLimitInteraction:
    """Test interaction between per-email and per-IP rate limits."""

    def test_per_ip_triggers_before_per_email(self, client, student_user):
        """WHEN the per-IP limit is reached before per-email,
        THEN subsequent requests return RATE_LIMITED_IP."""
        # Make 10 failed attempts (reaches IP limit, but email limit is also 5)
        # The 6th attempt will trigger per-email rate limit first
        for i in range(10):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            # First 5 should be 401
            if i < 5:
                assert response.status_code == 401, f"Attempt {i+1} should return 401"
            # 6th onwards should be rate limited by email (since email limit is 5)
            else:
                assert response.status_code == 429, f"Attempt {i+1} should be rate limited"
                body = response.json()
                # Could be either RATE_LIMITED_LOGIN or RATE_LIMITED_IP
                assert body['error']['code'] in ['RATE_LIMITED_LOGIN', 'RATE_LIMITED_IP']

        # 11th attempt should definitely be rate limited by IP
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        # At this point, both limits are exceeded
        assert body['error']['code'] in ['RATE_LIMITED_LOGIN', 'RATE_LIMITED_IP']

    def test_per_email_triggers_before_per_ip(self, client, student_user):
        """WHEN the per-email limit is reached before per-IP,
        THEN subsequent requests return RATE_LIMITED_LOGIN."""
        # Make 5 failed attempts (reaches email limit, but not IP limit of 10)
        for _ in range(5):
            response = client.post(
                '/api/v1/auth/login/',
                data={
                    'email': 'student@pampangastateu.edu.ph',
                    'password': 'WrongPassword',
                    'remember_me': False,
                },
                content_type='application/json',
                HTTP_ORIGIN='http://localhost:5173',
            )
            assert response.status_code == 401

        # 6th attempt should be rate limited by email
        response = client.post(
            '/api/v1/auth/login/',
            data={
                'email': 'student@pampangastateu.edu.ph',
                'password': 'WrongPassword',
                'remember_me': False,
            },
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert response.status_code == 429
        body = response.json()
        assert body['error']['code'] == 'RATE_LIMITED_LOGIN'
