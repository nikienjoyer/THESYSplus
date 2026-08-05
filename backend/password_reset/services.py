"""Public service functions for the password_reset app.

Exposes ``issue_reset_token`` and ``consume_reset_token``. Wave A5's
access-request approval flow consumes ``issue_reset_token`` to send the
account-activation email per Requirement 7.5.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from accounts.services import set_password as accounts_set_password
from auth_service.services import revoke_all_for_user
from common.audit_logger import write as audit_write
from common.email_backend import default_email_backend
from common.tokens.opaque import generate_opaque_token, sha256

from .models import PasswordResetToken

logger = logging.getLogger('emails')


# 30 minutes per Requirement 5.2.
RESET_TOKEN_TTL_SECONDS = 30 * 60


@dataclass
class IssuedResetToken:
    plaintext: str
    row: PasswordResetToken
    reset_url: str


def _build_reset_url(plaintext: str) -> str:
    """Return the front-end URL the user clicks to land on the reset page."""
    base = settings.FRONTEND_BASE_URL.rstrip('/')
    return f'{base}/reset-password?token={plaintext}'


def issue_reset_token(user: User, *, template: str = 'password_reset', subject: str | None = None,
                      request=None) -> IssuedResetToken:
    """Generate a reset token, persist its sha256 hash, send the email.

    ``template`` selects the email template (``password_reset`` for the
    forgot-password flow, ``account_activation`` for the post-approval
    flow per Requirement 7.5). The function never raises into the caller
    on email-delivery failure — it logs an audit row and returns the
    issued token so the caller can decide whether to surface a generic
    success message.
    """
    plaintext = generate_opaque_token()
    expires_at = timezone.now() + _dt.timedelta(seconds=RESET_TOKEN_TTL_SECONDS)
    row = PasswordResetToken.objects.create(
        user=user,
        token_hash=sha256(plaintext),
        expires_at=expires_at,
    )

    reset_url = _build_reset_url(plaintext)
    backend = default_email_backend()
    default_subject = (
        'Reset your THESYS+ password'
        if template == 'password_reset'
        else 'Welcome to THESYS+ — set your password'
    )
    delivered = backend.send(
        to=user.email,
        subject=subject or default_subject,
        template_name=template,
        context={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'reset_url': reset_url,
        },
    )

    if not delivered:
        logger.error('[EMAIL] Password reset email NOT sent to %s (backend returned False)', user.email)
        audit_write(
            'auth.email.failure',
            actor=None,
            target=user,
            success=False,
            metadata={'template': template, 'reason': 'email_backend_send_returned_false'},
            request=request,
        )
    else:
        logger.info('[EMAIL] Password reset email delivered to %s via %s', user.email, type(backend).__name__)

    return IssuedResetToken(plaintext=plaintext, row=row, reset_url=reset_url)


@dataclass
class ResetOutcome:
    user: User
    revoked_refresh_count: int


class ResetTokenInvalid(Exception):
    """Raised when a reset token is missing, expired, or already used."""


def consume_reset_token(plaintext: str, new_password: str, *, request=None) -> ResetOutcome:
    """Atomically validate the reset token, set the new password, and revoke sessions.

    Per Requirement 5.3:
    1. Look up the row by sha256(plaintext).
    2. Validate ``expires_at > now AND used_at IS NULL`` under SELECT FOR UPDATE.
    3. ``users.password_hash = make_password(new_password)``.
    4. ``users.is_email_verified = True`` (a successful set proves email control).
    5. ``password_reset_tokens.used_at = now``.
    6. Revoke ALL active refresh tokens for that user via ``revoke_all_for_user``.

    Raises ``ResetTokenInvalid`` for any of the failure modes; raises
    ``django.core.exceptions.ValidationError`` if the password fails
    strength rules (caller is expected to validate beforehand, but we
    check again in case the path bypassed the serializer).
    """
    presented_hash = sha256(plaintext)
    now = timezone.now()

    with transaction.atomic():
        try:
            row = PasswordResetToken.objects.select_for_update().get(token_hash=presented_hash)
        except PasswordResetToken.DoesNotExist as exc:
            raise ResetTokenInvalid('not_found') from exc

        if row.used_at is not None:
            raise ResetTokenInvalid('already_used')
        if row.expires_at <= now:
            raise ResetTokenInvalid('expired')

        user = row.user
        # Re-load the user inside the transaction to lock the row.
        user = User.objects.select_for_update().get(pk=user.pk)

        # Set the new password (also persists ``updated_at``).
        accounts_set_password(user, new_password)
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified', 'updated_at'])

        row.used_at = now
        row.save(update_fields=['used_at'])

        revoked = revoke_all_for_user(user, reason='password_reset')

    audit_write(
        'auth.password.reset_completed',
        actor=user,
        target=user,
        success=True,
        metadata={
            'revoked_refresh_count': revoked,
            'reset_token_id': str(row.id),
        },
        request=request,
    )
    return ResetOutcome(user=user, revoked_refresh_count=revoked)
