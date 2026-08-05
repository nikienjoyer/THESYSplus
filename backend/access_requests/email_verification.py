"""Email verification helpers for the access request flow.

After a clean auto-approved document verification, instead of immediately
creating the user account we:

1. Set AccessRequest.status = 'pending_email_verification'.
2. Issue an EmailVerificationToken (single-use, 24 h TTL).
3. Send a verification email with a link to the frontend.

When the applicant clicks the link the frontend calls:

    GET /api/v1/auth/verify-email/?token=<plaintext>

Which calls ``consume_email_verification_token``, creating the user and
issuing (but NOT emailing) a setup-password token. The plaintext is
returned all the way up to ``VerifyEmailView`` so the frontend can let
the user set their password inline on the same page — no second email.
"""

from __future__ import annotations

import datetime as _dt
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.audit_logger import write as audit_write
from common.email_backend import default_email_backend
from common.tokens.opaque import generate_opaque_token, sha256

from .models import AccessRequest, EmailVerificationToken, EMAIL_VERIFICATION_TTL_SECONDS
from .services import (
    approve_request,
    AccessRequestEmailCollision,
    AccessRequestNotPending,
)

logger = logging.getLogger('access_requests')


class EmailVerificationTokenInvalid(Exception):
    """Raised when the token is missing, expired, or already used."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _build_verify_url(plaintext: str) -> str:
    """Build the frontend email-verification URL."""
    base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173').rstrip('/')
    return f'{base}/verify-email?token={plaintext}'


def issue_email_verification_token(
    req: AccessRequest,
    *,
    request=None,
) -> str:
    """Issue a single-use email verification token for ``req`` and send the email.

    Sets ``req.status = 'pending_email_verification'`` and creates an
    ``EmailVerificationToken``.  The plaintext token is included in the
    email; only the SHA-256 hash is persisted.

    Returns the plaintext token (useful for testing / console output).
    """
    plaintext = generate_opaque_token()
    expires_at = timezone.now() + _dt.timedelta(seconds=EMAIL_VERIFICATION_TTL_SECONDS)

    with transaction.atomic():
        req.status = 'pending_email_verification'
        req.save(update_fields=['status'])

        EmailVerificationToken.objects.create(
            access_request=req,
            token_hash=sha256(plaintext),
            expires_at=expires_at,
        )

    verify_url = _build_verify_url(plaintext)
    backend = default_email_backend()
    delivered = backend.send(
        to=req.email,
        subject='Verify your THESYS+ email address',
        template_name='email_verification',
        context={
            'first_name': req.first_name,
            'last_name': req.last_name,
            'email': req.email,
            'verify_url': verify_url,
            'expiry_hours': EMAIL_VERIFICATION_TTL_SECONDS // 3600,
        },
    )

    if not delivered:
        audit_write(
            'auth.email.failure',
            actor=None,
            target=None,
            success=False,
            metadata={
                'template': 'email_verification',
                'reason': 'email_backend_send_returned_false',
                'access_request_id': str(req.id),
            },
            request=request,
        )

    audit_write(
        'auth.access_request.email_verification_sent',
        actor=None,
        target=None,
        success=True,
        metadata={
            'access_request_id': str(req.id),
            'email': req.email,
        },
        request=request,
    )

    return plaintext


def consume_email_verification_token(plaintext: str, *, request=None):
    """Validate a verification token and activate the user account.

    Steps:
    1. Look up token by sha256(plaintext); raise EmailVerificationTokenInvalid
       for missing / expired / already-used token.
    2. Call ``approve_request(..., send_email=False)`` — creates the User
       and issues a setup-password token without emailing it.
    3. Mark the token as used.

    Returns the ``ApprovalOutcome`` from ``approve_request`` — its
    ``reset_token_plaintext`` field carries the setup-password token the
    caller should return to the browser.

    Raises:
        EmailVerificationTokenInvalid: token missing / expired / used
        AccessRequestEmailCollision: email already registered
    """
    presented_hash = sha256(plaintext)
    now = timezone.now()

    with transaction.atomic():
        try:
            token_row = (
                EmailVerificationToken.objects
                .select_for_update()
                .select_related('access_request')
                .get(token_hash=presented_hash)
            )
        except EmailVerificationToken.DoesNotExist:
            raise EmailVerificationTokenInvalid('not_found')

        if token_row.used_at is not None:
            raise EmailVerificationTokenInvalid('already_used')

        if token_row.expires_at <= now:
            raise EmailVerificationTokenInvalid('expired')

        req = token_row.access_request

        # Allow both 'pending_email_verification' (normal) and 'processing'
        # (fallback if the status update raced).
        if req.status not in ('pending_email_verification', 'processing'):
            raise EmailVerificationTokenInvalid('request_not_awaiting_verification')

        # Temporarily set status to 'processing' so approve_request accepts it.
        if req.status == 'pending_email_verification':
            req.status = 'processing'
            req.save(update_fields=['status'])

        # Approve — creates the User and issues the setup-password token,
        # but does NOT email it: the caller (VerifyEmailView) hands the
        # plaintext straight back to this same browser so it can set the
        # password inline, without a second "Set Up Your Account" email.
        try:
            outcome = approve_request(
                req,
                reviewer=None,
                note='Account activated via email verification.',
                request=request,
                send_email=False,
            )
        except AccessRequestNotPending:
            raise EmailVerificationTokenInvalid('request_not_awaiting_verification')

        # Mark token as used.
        token_row.used_at = now
        token_row.save(update_fields=['used_at'])

    audit_write(
        'auth.access_request.email_verified',
        actor=None,
        target=outcome.user,
        success=True,
        metadata={
            'access_request_id': str(req.id),
            'email': req.email,
            'user_id': str(outcome.user.id),
        },
        request=request,
    )

    return outcome
