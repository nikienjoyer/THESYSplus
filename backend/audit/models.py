"""Append-only audit log for the auth_service.

Per design §3.3, §9 and Requirements 11.1 / 11.2. Application code only
ever INSERTs rows — UPDATE and DELETE are reserved for ops-level retention
maintenance. The four indexes (created_at DESC, event_type, actor, target)
support the admin event timeline and per-user audit views.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        db_column='actor_user_id',
    )
    event_type = models.CharField(max_length=64)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        db_column='target_user_id',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    success = models.BooleanField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        indexes = [
            models.Index(fields=['-created_at'], name='audit_log_created_at_idx'),
            models.Index(fields=['event_type'], name='audit_log_event_type_idx'),
            models.Index(fields=['actor_user'], name='audit_log_actor_idx'),
            models.Index(fields=['target_user'], name='audit_log_target_idx'),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'AuditLog({self.id}, {self.event_type})'
