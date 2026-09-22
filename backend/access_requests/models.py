"""Access request model — submitted by unprovisioned users, reviewed by administrators.

Per design §3.3 and Requirements 7.1, 7.2, 7.3, 7.4, 7.8.

The partial UNIQUE index on ``(email) WHERE status = 'pending'`` enforces
the ``DUPLICATE_REQUEST_PENDING`` rule at the database level so a duplicate
submission fails fast even under concurrency. ``requested_role`` is
restricted to ``student`` / ``faculty`` because the administrator role is
never self-requestable.

``EmailVerificationToken`` stores the single-use signed token sent to the
applicant after a clean auto-approval decision. Consuming the token
activates the user account without administrator intervention.
"""

from __future__ import annotations

import datetime as _dt
import uuid

from django.conf import settings
from django.contrib.postgres.fields import CIEmailField
from django.db import models
from django.utils import timezone

# Verification email link expires in 24 hours.
EMAIL_VERIFICATION_TTL_SECONDS = 24 * 60 * 60

# How long the submitting tab may poll its claim stub for, from submission.
#
# NOTE — this is DELIBERATELY SHORTER than EMAIL_VERIFICATION_TTL_SECONDS
# (30 minutes vs 24 hours). The two windows serve different things: the email
# link must survive a user who reads their mail tomorrow, whereas the claim
# only needs to outlive a browser tab someone is actively waiting at. Keeping
# a pollable stub alive for 24 hours would mean 24 hours of a token that can
# mint password-setup credentials.
#
# Consequence to be aware of: an applicant who clicks the emailed link more
# than 30 minutes after submitting still verifies successfully and still gets
# their setup token from ``VerifyEmailView`` — but the original tab's claim
# will report ``expired``, so the frontend must fall back to sign-in /
# forgot-password rather than treating that as an error state. The claim is an
# optimisation for the common case, never the only route to a password.
CLAIM_TTL_SECONDS = 30 * 60


class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        # Identity verification statuses
        ('processing', 'Processing'),
        ('auto_approved', 'Auto Approved'),
        ('pending_manual_review', 'Pending Manual Review'),
        # Email verification pending (clean auto-approval, awaiting email click)
        ('pending_email_verification', 'Pending Email Verification'),
    ]

    REQUESTED_ROLE_CHOICES = [
        ('student', 'Student'),
        ('faculty', 'Faculty'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = CIEmailField(max_length=254)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    requested_role = models.CharField(max_length=16, choices=REQUESTED_ROLE_CHOICES)
    justification = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default='pending',
    )
    review_note = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_access_requests',
        db_column='reviewed_by',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Identity verification foreign keys (nullable for backward compatibility)
    verification_document_id = models.UUIDField(null=True, blank=True)
    verification_result_id = models.UUIDField(null=True, blank=True)

    # ── Claim stub ──────────────────────────────────────────────────────
    #
    # Lets the tab that SUBMITTED this request later discover that the email
    # was verified, without that tab ever having held the emailed link. The
    # submitting tab keeps the plaintext in memory and polls
    # ``GET /auth/request-access/status/?claim=<plaintext>``.
    #
    # Only the SHA-256 hash is persisted — the plaintext is returned exactly
    # once, in the submission response, and is unrecoverable afterwards. This
    # mirrors EmailVerificationToken and auth_service's RefreshToken.
    #
    # Both are nullable so the migration applies cleanly to rows that predate
    # this column; a request without a claim simply has nothing to poll.
    claim_token_hash = models.CharField(
        max_length=64, unique=True, db_index=True, null=True, blank=True,
    )
    claim_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'access_requests'
        indexes = [
            models.Index(
                fields=['status', '-created_at'],
                name='access_requests_status_idx',
            ),
            # The lookup key on every poll — hit ~450 times per claim over a
            # 30-minute window, so it must not be a sequential scan.
            models.Index(
                fields=['claim_token_hash'],
                name='access_req_claim_hash_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    status__in=[
                        'pending',
                        'approved',
                        'denied',
                        'processing',
                        'auto_approved',
                        'pending_manual_review',
                        'pending_email_verification',
                    ]
                ),
                name='access_requests_status_check',
            ),
            models.CheckConstraint(
                check=models.Q(requested_role__in=['student', 'faculty']),
                name='access_requests_requested_role_check',
            ),
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(status='pending'),
                name='access_requests_email_pending_uidx',
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'AccessRequest({self.email}, {self.status})'

    def issue_claim_token(self) -> str:
        """Mint this request's claim stub and return the plaintext ONCE.

        Stores only ``sha256(plaintext)``. The caller must hand the returned
        string to the submitting browser immediately — it cannot be recovered
        from the database afterwards, by design.

        Uses ``common.tokens.opaque`` exactly as ``issue_email_verification_token``
        and ``auth_service.services.issue_token_pair`` do; no separate token
        scheme exists here.

        Does NOT save — the caller persists, so this can participate in the
        same INSERT that creates the row.
        """
        from common.tokens.opaque import generate_opaque_token, sha256

        plaintext = generate_opaque_token()
        self.claim_token_hash = sha256(plaintext)
        self.claim_expires_at = timezone.now() + _dt.timedelta(
            seconds=CLAIM_TTL_SECONDS,
        )
        return plaintext

    def claim_is_expired(self, *, now=None) -> bool:
        """True when the claim window has closed (or no claim was ever issued)."""
        if self.claim_expires_at is None:
            return True
        return self.claim_expires_at <= (now or timezone.now())


class EmailVerificationToken(models.Model):
    """Single-use token sent to an applicant after clean auto-approval.

    When the identity verification pipeline returns ``auto_approved`` for a
    document upload, we do NOT immediately create the user account.  Instead
    we:
      1. Set ``AccessRequest.status = 'pending_email_verification'``.
      2. Create an ``EmailVerificationToken`` pointing at the request.
      3. Email the token URL to the applicant.

    When the applicant clicks the link (``GET /auth/verify-email/?token=…``):
      1. We look up the token, check it is unused and not expired.
      2. Call ``approve_request(..., send_email=False)`` to create the
         User and issue a setup-password token without emailing it — the
         plaintext is returned to the browser so it can set the password
         inline, on this same page, instead of via a second email.
      3. Mark the token as ``used_at = now``.

    Expiry: 24 hours (``EMAIL_VERIFICATION_TTL_SECONDS``).
    Single-use: ``used_at`` is set on consumption; reuse is rejected.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_request = models.OneToOneField(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='email_verification_token',
    )
    # SHA-256 hash of the plaintext token — never store plaintext.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_verification_tokens'
        indexes = [
            models.Index(fields=['token_hash'], name='email_ver_token_hash_idx'),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f'EmailVerificationToken({self.access_request.email})'
