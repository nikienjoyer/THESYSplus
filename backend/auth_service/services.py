"""Public token service functions for the auth_service app.

Exposes the four primitives the login / refresh / logout / password-reset
flows need:

* ``issue_token_pair(user, request, remember_me)`` — at-login issuance.
* ``rotate_refresh(plaintext, request)``           — at-refresh rotation.
* ``revoke_family(family_id, reason)``             — full-family revoke.
* ``revoke_all_for_user(user, reason)``            — used by password reset.
* ``revoke_one(plaintext)``                        — used by /logout.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.errors import (
    RefreshReuseDetected,
    RefreshTokenExpired,
    RefreshTokenRevoked,
)
from common.tokens.jwt import issue_access_token
from common.tokens.opaque import generate_opaque_token, sha256

from .models import RefreshToken


REVOKED_REASON_ROTATED = 'rotated'
REVOKED_REASON_LOGOUT = 'logout'
REVOKED_REASON_REUSE = 'reuse_detected'
REVOKED_REASON_PASSWORD_RESET = 'password_reset'
REVOKED_REASON_ADMIN_REVOKE = 'admin_revoke'


@dataclass
class IssuedTokenPair:
    """Tuple returned by login + refresh endpoints."""

    access_token: str
    refresh_plaintext: str
    refresh_row: RefreshToken


def _ttl_for(remember_me: bool) -> int:
    return (
        settings.REFRESH_TOKEN_REMEMBER_ME_TTL_SECONDS
        if remember_me
        else settings.REFRESH_TOKEN_TTL_SECONDS
    )


def _client_ip(request):
    if request is None or not hasattr(request, 'META'):
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _user_agent(request):
    if request is None or not hasattr(request, 'META'):
        return None
    ua = request.META.get('HTTP_USER_AGENT')
    return ua[:255] if isinstance(ua, str) else None


def issue_token_pair(user, request, *, remember_me: bool) -> IssuedTokenPair:
    """Issue a fresh access JWT + opaque refresh token at login."""
    access_token = issue_access_token(user)
    plaintext = generate_opaque_token()
    expires_at = timezone.now() + _dt.timedelta(seconds=_ttl_for(remember_me))

    refresh_row = RefreshToken.objects.create(
        user=user,
        token_hash=sha256(plaintext),
        family_id=uuid.uuid4(),
        parent=None,
        remember_me=remember_me,
        expires_at=expires_at,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return IssuedTokenPair(access_token=access_token, refresh_plaintext=plaintext, refresh_row=refresh_row)


def revoke_family(family_id, reason: str) -> int:
    """Atomically revoke every still-active token in ``family_id``."""
    return RefreshToken.objects.filter(
        family_id=family_id, revoked_at__isnull=True,
    ).update(revoked_at=timezone.now(), revoked_reason=reason)


def revoke_all_for_user(user, reason: str) -> int:
    """Revoke every still-active refresh token for ``user``."""
    return RefreshToken.objects.filter(
        user=user, revoked_at__isnull=True,
    ).update(revoked_at=timezone.now(), revoked_reason=reason)


def rotate_refresh(plaintext: str, request) -> IssuedTokenPair:
    """Exchange a valid refresh token for a new pair, with rotation + reuse detection.

    Branches per design §5.3:
    * Not found            → raise RefreshTokenRevoked.
    * Expired              → raise RefreshTokenExpired.
    * Already revoked      → revoke entire family + raise RefreshReuseDetected.
    * Active               → atomic rotate: revoke old, issue new (inheriting family_id and remember_me).

    The reuse-detection branch records ``family_id`` and exits the
    ``transaction.atomic()`` block cleanly before issuing the family-wide
    revoke; otherwise the revoke would be rolled back along with the
    raised exception.
    """
    presented_hash = sha256(plaintext)
    now = timezone.now()

    reuse_family_id = None

    with transaction.atomic():
        try:
            row = RefreshToken.objects.select_for_update().get(token_hash=presented_hash)
        except RefreshToken.DoesNotExist as exc:
            raise RefreshTokenRevoked() from exc

        if row.expires_at <= now:
            raise RefreshTokenExpired()

        if row.revoked_at is not None:
            # Distinguish reuse (a rotated row replayed by the legitimate
            # client or an attacker) from a row already revoked for any
            # other reason (family-wide kill, logout, password reset,
            # admin revoke). Only the rotated-replay branch triggers a
            # family-wide revocation per design §5.3.
            if row.revoked_reason == REVOKED_REASON_ROTATED:
                reuse_family_id = row.family_id
            else:
                raise RefreshTokenRevoked()
        else:
            # Active: rotate.
            row.revoked_at = now
            row.revoked_reason = REVOKED_REASON_ROTATED
            row.save(update_fields=['revoked_at', 'revoked_reason'])

            new_plaintext = generate_opaque_token()
            expires_at = now + _dt.timedelta(seconds=_ttl_for(row.remember_me))

            new_row = RefreshToken.objects.create(
                user=row.user,
                token_hash=sha256(new_plaintext),
                family_id=row.family_id,
                parent=row,
                remember_me=row.remember_me,
                expires_at=expires_at,
                ip_address=_client_ip(request),
                user_agent=_user_agent(request),
            )
            access_token = issue_access_token(row.user)
            return IssuedTokenPair(
                access_token=access_token,
                refresh_plaintext=new_plaintext,
                refresh_row=new_row,
            )

    # Atomic block exited normally on the reuse path — commit the
    # family-wide revoke (its own UPDATE auto-commits) and surface the
    # error to the caller.
    revoke_family(reuse_family_id, reason=REVOKED_REASON_REUSE)
    raise RefreshReuseDetected()


def revoke_one(plaintext: str) -> bool:
    """Revoke a single refresh row by plaintext (used by /logout).

    Returns True if a row was revoked. Tolerant — does NOT raise for
    missing/expired/already-revoked rows per Requirements 9.4 / 9.5 / 9.6.
    Family is preserved — only this single row is marked revoked.
    """
    presented_hash = sha256(plaintext)
    now = timezone.now()
    return (
        RefreshToken.objects.filter(token_hash=presented_hash, revoked_at__isnull=True).update(
            revoked_at=now, revoked_reason=REVOKED_REASON_LOGOUT,
        )
        > 0
    )
