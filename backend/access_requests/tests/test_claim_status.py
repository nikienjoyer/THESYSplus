"""Tests for the access-request claim stub and GET /auth/request-access/status/.

The claim stub lets the tab that SUBMITTED a request discover that the email
was later verified, and obtain a password-setup token, without that tab ever
having held the emailed verification link.

The central constraint these tests encode: setup tokens are stored HASHED, so
the plaintext issued during email verification is unrecoverable afterwards.
The status endpoint therefore MINTS A FRESH token on the verified branch rather
than returning an existing one — which is also why polling twice legitimately
yields two tokens, with the later one being the valid one.
"""

from __future__ import annotations

import datetime as _dt

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from access_requests.email_verification import (
    consume_email_verification_token,
    issue_email_verification_token,
)
from access_requests.models import CLAIM_TTL_SECONDS, AccessRequest
from accounts.models import User
from common.tokens.opaque import sha256

SUBMIT_URL_NAME = 'access-request-submit'
STATUS_URL_NAME = 'access-request-status'
VERIFY_URL_NAME = 'access-request-verify-email'
SETUP_URL_NAME = 'auth-setup-password'

STRONG_PASSWORD = 'Str0ng!Passw0rd!2026'


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """Rate-limit buckets live in LocMemCache and leak between tests."""
    cache.clear()
    yield
    cache.clear()


def _submit(client, email='claimant@pampangastateu.edu.ph'):
    """Submit via the legacy justification flow and return (response, body)."""
    response = client.post(
        reverse(SUBMIT_URL_NAME),
        data={
            'email': email,
            'first_name': 'Claim',
            'last_name': 'Ant',
            'requested_role': 'student',
            'justification': 'I am a student and require repository access for my thesis.',
        },
        content_type='application/json',
        HTTP_ORIGIN='http://localhost:5173',
    )
    return response, response.json()


def _status(client, claim):
    return client.get(reverse(STATUS_URL_NAME), {'claim': claim})


def _verify_email_for(req, *, client=None):
    """Drive the request through email verification, as the emailed link does."""
    plaintext = issue_email_verification_token(req)
    req.refresh_from_db()
    if client is not None:
        return client.get(reverse(VERIFY_URL_NAME), {'token': plaintext})
    return consume_email_verification_token(plaintext)


# ---------------------------------------------------------------------------
# Submission returns the claim
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSubmissionReturnsClaim:
    def test_submission_returns_a_claim_and_absolute_expiry(self, client):
        response, body = _submit(client)

        assert response.status_code == 201
        assert body['claim']
        assert isinstance(body['claim'], str)
        assert body['claim_expires_at']

    def test_expiry_is_an_absolute_timestamp_not_a_duration(self, client):
        """The frontend polls until a wall-clock moment.

        Publishing the instant (rather than "1800 seconds") means
        CLAIM_TTL_SECONDS can change server-side without the frontend
        drifting out of sync, so no response may carry a bare duration.
        """
        _, body = _submit(client)

        parsed = _dt.datetime.fromisoformat(body['claim_expires_at'])
        assert parsed.tzinfo is not None, 'expiry must be timezone-aware'

        expected = timezone.now() + _dt.timedelta(seconds=CLAIM_TTL_SECONDS)
        assert abs((parsed - expected).total_seconds()) < 60

        # No field may leak the raw TTL as a number the frontend could hardcode.
        assert CLAIM_TTL_SECONDS not in body.values()
        assert 'claim_ttl' not in body
        assert 'expires_in' not in body

    def test_existing_response_fields_are_preserved(self, client):
        """This commit is additive — the old contract must not shift."""
        _, body = _submit(client)

        assert body['status'] == 'pending'
        assert body['submitted_at']

    def test_claim_is_unique_per_submission(self, client):
        _, first = _submit(client, 'one@pampangastateu.edu.ph')
        _, second = _submit(client, 'two@pampangastateu.edu.ph')

        assert first['claim'] != second['claim']


@pytest.mark.django_db
class TestOnlyTheHashIsPersisted:
    def test_plaintext_appears_nowhere_in_the_row(self, client):
        _, body = _submit(client)
        claim = body['claim']

        req = AccessRequest.objects.get()

        assert req.claim_token_hash == sha256(claim)
        assert req.claim_token_hash != claim
        assert claim not in str(req.__dict__.values())

    def test_no_row_in_the_table_contains_the_plaintext(self, client):
        """Scan every text column, not just the one we expect."""
        _, body = _submit(client)
        claim = body['claim']

        for req in AccessRequest.objects.all():
            for value in (
                req.email, req.first_name, req.last_name, req.requested_role,
                req.justification or '', req.status, req.review_note or '',
                req.claim_token_hash or '',
            ):
                assert claim not in str(value)

    def test_hash_is_a_64_char_hex_digest(self, client):
        _submit(client)
        req = AccessRequest.objects.get()

        assert len(req.claim_token_hash) == 64
        assert all(c in '0123456789abcdef' for c in req.claim_token_hash)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPendingVerification:
    def test_before_verification_reports_pending(self, client):
        _, body = _submit(client)

        response = _status(client, body['claim'])

        assert response.status_code == 200
        assert response.json() == {'status': 'pending_verification'}

    def test_pending_response_carries_no_token(self, client):
        _, body = _submit(client)

        assert 'setup_token' not in _status(client, body['claim']).json()


@pytest.mark.django_db
class TestVerified:
    def test_after_verification_reports_verified_with_a_token(self, client):
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())

        response = _status(client, body['claim'])

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'verified'
        assert payload['setup_token']

    def test_the_returned_token_actually_works_against_setup_password(self, client):
        """The whole point — a token that doesn't work is worse than none."""
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())

        setup_token = _status(client, body['claim']).json()['setup_token']

        response = client.post(
            reverse(SETUP_URL_NAME),
            data={'token': setup_token, 'new_password': STRONG_PASSWORD},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )

        assert response.status_code == 200, response.content

        user = User.objects.get(email='claimant@pampangastateu.edu.ph')
        assert user.password
        assert user.check_password(STRONG_PASSWORD)

    def test_polling_twice_returns_a_token_both_times(self, client):
        """Makes a browser reload survivable.

        A reloaded tab loses the first token from memory; it must be able to
        poll again and get a working one rather than being stranded.
        """
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())

        first = _status(client, body['claim']).json()
        second = _status(client, body['claim']).json()

        assert first['status'] == 'verified'
        assert second['status'] == 'verified'
        assert first['setup_token']
        assert second['setup_token']
        assert first['setup_token'] != second['setup_token']

    def test_the_later_token_is_the_valid_one(self, client):
        """Fresh tokens are minted per poll; the newest is what the UI holds."""
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())

        _status(client, body['claim']).json()['setup_token']
        later = _status(client, body['claim']).json()['setup_token']

        response = client.post(
            reverse(SETUP_URL_NAME),
            data={'token': later, 'new_password': STRONG_PASSWORD},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )

        assert response.status_code == 200, response.content

    def test_no_second_email_is_dispatched_when_minting(self, client, mailoutbox):
        """send_email=False — the claim hands the token to an open tab."""
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())
        before = len(mailoutbox)

        _status(client, body['claim'])

        assert len(mailoutbox) == before


@pytest.mark.django_db
class TestAlreadyActive:
    def _submit_verify_and_set_password(self, client):
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())
        setup_token = _status(client, body['claim']).json()['setup_token']
        client.post(
            reverse(SETUP_URL_NAME),
            data={'token': setup_token, 'new_password': STRONG_PASSWORD},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        return body['claim']

    def test_after_the_password_is_set_reports_already_active(self, client):
        claim = self._submit_verify_and_set_password(client)

        response = _status(client, claim)

        assert response.status_code == 200
        assert response.json() == {'status': 'already_active'}

    def test_already_active_returns_no_token(self, client):
        """A stale tab must not receive credentials for a live account."""
        claim = self._submit_verify_and_set_password(client)

        assert 'setup_token' not in _status(client, claim).json()

    def test_already_active_mints_nothing(self, client):
        """The stub's effective expiry: no new reset row is created."""
        from password_reset.models import PasswordResetToken

        claim = self._submit_verify_and_set_password(client)
        before = PasswordResetToken.objects.count()

        _status(client, claim)

        assert PasswordResetToken.objects.count() == before


@pytest.mark.django_db
class TestExpiry:
    def test_past_expiry_reports_expired(self, client):
        _, body = _submit(client)
        req = AccessRequest.objects.get()
        req.claim_expires_at = timezone.now() - _dt.timedelta(seconds=1)
        req.save(update_fields=['claim_expires_at'])

        response = _status(client, body['claim'])

        assert response.status_code == 200
        assert response.json() == {'status': 'expired'}

    def test_expired_returns_no_token_even_when_verified(self, client):
        """Expiry must beat verification — otherwise the window means nothing."""
        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())

        req = AccessRequest.objects.get()
        req.claim_expires_at = timezone.now() - _dt.timedelta(seconds=1)
        req.save(update_fields=['claim_expires_at'])

        payload = _status(client, body['claim']).json()

        assert payload == {'status': 'expired'}
        assert 'setup_token' not in payload

    def test_expired_mints_nothing(self, client):
        from password_reset.models import PasswordResetToken

        _, body = _submit(client)
        _verify_email_for(AccessRequest.objects.get())
        req = AccessRequest.objects.get()
        req.claim_expires_at = timezone.now() - _dt.timedelta(seconds=1)
        req.save(update_fields=['claim_expires_at'])
        before = PasswordResetToken.objects.count()

        _status(client, body['claim'])

        assert PasswordResetToken.objects.count() == before

    def test_ttl_is_thirty_minutes(self):
        assert CLAIM_TTL_SECONDS == 30 * 60


@pytest.mark.django_db
class TestUnknownClaim:
    def test_unknown_claim_returns_404(self, client):
        response = _status(client, 'this-claim-was-never-issued')

        assert response.status_code == 404
        assert response.json()['error']['code'] == 'CLAIM_NOT_FOUND'

    def test_missing_claim_param_returns_404(self, client):
        assert client.get(reverse(STATUS_URL_NAME)).status_code == 404

    def test_empty_claim_param_returns_404(self, client):
        assert _status(client, '').status_code == 404

    def test_404_does_not_distinguish_never_existed_from_purged(self, client):
        """Both must be byte-identical.

        A different body for a purged claim would confirm to an attacker that
        the claim was once real.
        """
        _, body = _submit(client)
        claim = body['claim']
        # Simulate the purge path: the row is gone, so the hash resolves to
        # nothing — exactly as for a claim that never existed.
        AccessRequest.objects.all().delete()

        purged = _status(client, claim)
        never = _status(client, 'never-issued-at-all')

        assert purged.status_code == never.status_code == 404
        assert purged.json() == never.json()

    def test_404_body_leaks_no_detail(self, client):
        payload = _status(client, 'nope').json()

        assert 'email' not in str(payload).lower()
        assert 'expired' not in str(payload).lower()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRateLimiting:
    def test_permits_at_least_thirty_requests_per_minute_for_one_claim(self, client):
        """The frontend polls ~15x/min for 30 minutes.

        A reset-password-style 5-per-15-minutes budget would break the feature
        on its 6th poll. This is the floor the cadence requires.
        """
        _, body = _submit(client)
        claim = body['claim']

        for i in range(30):
            response = _status(client, claim)
            assert response.status_code == 200, f'throttled on request {i + 1}'

    def test_eventually_throttles_one_claim(self, client):
        """Permissive is not unlimited."""
        from access_requests.views import CLAIM_STATUS_PER_CLAIM_LIMIT

        _, body = _submit(client)
        claim = body['claim']

        codes = {
            _status(client, claim).status_code
            for _ in range(CLAIM_STATUS_PER_CLAIM_LIMIT + 5)
        }

        assert 429 in codes

    def test_throttled_response_carries_retry_after(self, client):
        from access_requests.views import CLAIM_STATUS_PER_CLAIM_LIMIT

        _, body = _submit(client)
        claim = body['claim']

        last = None
        for _ in range(CLAIM_STATUS_PER_CLAIM_LIMIT + 5):
            last = _status(client, claim)

        assert last.status_code == 429
        assert last['Retry-After']

    def test_per_ip_limit_is_looser_than_per_claim(self):
        """A shared NAT can carry several applicants polling at once.

        If the per-IP budget were the tighter of the two, one busy network
        would throttle unrelated users — a self-inflicted outage.
        """
        from access_requests.views import (
            CLAIM_STATUS_PER_CLAIM_LIMIT,
            CLAIM_STATUS_PER_CLAIM_WINDOW,
            CLAIM_STATUS_PER_IP_LIMIT,
            CLAIM_STATUS_PER_IP_WINDOW,
        )

        per_claim_rate = CLAIM_STATUS_PER_CLAIM_LIMIT / CLAIM_STATUS_PER_CLAIM_WINDOW
        per_ip_rate = CLAIM_STATUS_PER_IP_LIMIT / CLAIM_STATUS_PER_IP_WINDOW

        assert per_ip_rate > per_claim_rate

    def test_per_claim_budget_comfortably_exceeds_the_poll_cadence(self):
        from access_requests.views import (
            CLAIM_STATUS_PER_CLAIM_LIMIT,
            CLAIM_STATUS_PER_CLAIM_WINDOW,
        )

        polls_per_minute = 60 / 4  # frontend polls every ~4 seconds
        budget_per_minute = (
            CLAIM_STATUS_PER_CLAIM_LIMIT * 60 / CLAIM_STATUS_PER_CLAIM_WINDOW
        )

        assert budget_per_minute >= 2 * polls_per_minute


# ---------------------------------------------------------------------------
# Regression — the existing flow must be untouched
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestVerifyEmailUnchanged:
    def test_verify_email_still_returns_setup_token(self, client):
        """Commit 3 changes this. This commit must not."""
        _submit(client)
        req = AccessRequest.objects.get()

        response = _verify_email_for(req, client=client)

        assert response.status_code == 200
        payload = response.json()
        assert payload['verified'] is True
        assert payload['email'] == 'claimant@pampangastateu.edu.ph'
        assert payload['setup_token']
        assert payload['message']

    def test_verify_email_response_shape_is_exactly_as_before(self, client):
        _submit(client)
        response = _verify_email_for(AccessRequest.objects.get(), client=client)

        assert set(response.json()) == {
            'verified', 'email', 'setup_token', 'message',
        }

    def test_verify_email_token_still_works_end_to_end(self, client):
        """The emailed-link path stays independently sufficient.

        A user who never polls — or whose claim expired — must still be able
        to set a password from the verification tab alone.
        """
        _submit(client)
        setup_token = _verify_email_for(
            AccessRequest.objects.get(), client=client,
        ).json()['setup_token']

        response = client.post(
            reverse(SETUP_URL_NAME),
            data={'token': setup_token, 'new_password': STRONG_PASSWORD},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )

        assert response.status_code == 200, response.content

    def test_verification_works_even_after_the_claim_expired(self, client):
        """The 30-minute claim window is shorter than the 24-hour email link.

        Someone who clicks the link an hour later verifies fine; only the
        polling optimisation is lost.
        """
        _, body = _submit(client)
        req = AccessRequest.objects.get()
        req.claim_expires_at = timezone.now() - _dt.timedelta(seconds=1)
        req.save(update_fields=['claim_expires_at'])

        response = _verify_email_for(req, client=client)

        assert response.status_code == 200
        assert response.json()['setup_token']
        assert _status(client, body['claim']).json() == {'status': 'expired'}
