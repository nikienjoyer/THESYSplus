"""Django Admin registration for the audit app.

Per design §9.3, the AuditLog model is registered as read-only (append-only
enforcement). Administrators can view audit entries but cannot modify or
delete them through the admin interface.
"""

from __future__ import annotations

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only admin for audit log entries."""

    list_display = ['id', 'event_type', 'actor_user', 'target_user', 'success', 'created_at']
    list_filter = ['event_type', 'success', 'created_at']
    search_fields = ['event_type', 'actor_user__email', 'target_user__email']
    readonly_fields = [
        'id',
        'actor_user',
        'event_type',
        'target_user',
        'ip_address',
        'user_agent',
        'success',
        'metadata',
        'created_at',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        """Audit log entries are created programmatically only."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit log is append-only — no updates allowed."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit log is append-only — no deletes allowed."""
        return False
