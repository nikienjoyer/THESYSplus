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

# Verification email link expires in 24 hours.
EMAIL_VERIFICATION_TTL_SECONDS = 24 * 60 * 60


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

    class Meta:
        db_table = 'access_requests'
        indexes = [
            models.Index(
                fields=['status', '-created_at'],
                name='access_requests_status_idx',
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
      2. Call ``approve_request()`` to create the User and send the
         activation/set-password email.
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
