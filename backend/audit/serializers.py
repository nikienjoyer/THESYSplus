"""Serializers for the audit app."""

from __future__ import annotations

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for audit log entries."""

    actor_user_id = serializers.UUIDField(source='actor_user.id', read_only=True, allow_null=True)
    target_user_id = serializers.UUIDField(source='target_user.id', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'actor_user_id',
            'event_type',
            'target_user_id',
            'ip_address',
            'user_agent',
            'success',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields
