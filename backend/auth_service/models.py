"""Refresh token model for the ``auth_service`` app.

Implements opaque refresh tokens with rotation, family-wide reuse detection,
and remember-me lifetime per design §5.1 / §5.3 and Requirements 2.8, 2.9,
4.4, 9.6, 9.8.

The plaintext refresh token is NEVER stored. Only the SHA-256 hex digest
lives in the ``token_hash`` column. Rotation creates a new row whose
``parent_id`` points at the previous row and whose ``family_id`` is
inherited; on detected reuse the entire family is revoked in one UPDATE.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class RefreshToken(models.Model):
    REVOKED_REASON_CHOICES = [
        ('rotated', 'Rotated'),
        ('logout', 'Logout'),
        ('reuse_detected', 'Reuse Detected'),
        ('password_reset', 'Password Reset'),
        ('admin_revoke', 'Admin Revoke'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        db_column='user_id',
    )
    token_hash = models.CharField(max_length=64, unique=True)
    family_id = models.UUIDField(db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        db_column='parent_id',
    )
    remember_me = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(
        max_length=40,
        choices=REVOKED_REASON_CHOICES,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'refresh_tokens'
        indexes = [
            # Partial active index — used to count/list a user's live
            # sessions without scanning revoked rows.
            models.Index(
                fields=['user'],
                name='refresh_tokens_user_active_idx',
                condition=models.Q(revoked_at__isnull=True),
            ),
            models.Index(fields=['family_id'], name='refresh_tokens_family_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        revoked_reason__in=[
                            'rotated',
                            'logout',
                            'reuse_detected',
                            'password_reset',
                            'admin_revoke',
                        ]
                    )
                    | models.Q(revoked_reason__isnull=True)
                ),
                name='refresh_tokens_revoked_reason_check',
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'RefreshToken({self.id})'
