"""Password reset token model — single-use, time-limited.

Per design §3.3 and Requirements 5.2 / 5.3 / 5.4. Only the SHA-256 digest
of the token is stored; the plaintext is delivered to the user via email.
``used_at`` enforces single-use semantics; the validation flow updates this
column atomically before allowing the reset to proceed.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        db_column='user_id',
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'password_reset_tokens'
        indexes = [
            models.Index(fields=['user'], name='password_reset_tokens_user_idx'),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'PasswordResetToken({self.id})'
