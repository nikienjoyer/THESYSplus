"""Append-only audit log writer for the Auth_Service.

``write(event_type, ...)`` inserts one ``AuditLog`` row, never raises
back to the caller. Failures are logged via the standard logging
facility per design §9.4 so a transient DB hiccup can't break the auth
flow that the audit entry was supposed to record.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('audit')


def _client_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR') if hasattr(request, 'META') else None
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None


def _user_agent(request) -> str | None:
    if request is None or not hasattr(request, 'META'):
        return None
    ua = request.META.get('HTTP_USER_AGENT')
    return (ua[:255] if isinstance(ua, str) else None)


def write(
    event_type: str,
    *,
    actor=None,
    target=None,
    success: bool,
    metadata: dict[str, Any] | None = None,
    request=None,
) -> None:
    """Persist a single audit row.

    ``actor`` and ``target`` may be ``User`` instances OR raw user ids
    (UUID/str). Any failure is swallowed and logged — the caller MUST be
    able to assume this returns normally.
    """
    # Lazy import so this module loads without Django being configured
    # (e.g., during static analysis).
    try:
        from audit.models import AuditLog
        from accounts.models import User
    except Exception as exc:
        logger.error('audit_logger import failure: %s', exc)
        return

    def _resolve(ref):
        if ref is None:
            return None
        if hasattr(ref, '_meta'):  # already a model instance
            return ref
        # Treat as PK; fall back to None on miss so audit never raises.
        try:
            return User.objects.filter(pk=ref).first()
        except Exception:
            return None

    try:
        AuditLog.objects.create(
            event_type=event_type,
            actor_user=_resolve(actor),
            target_user=_resolve(target),
            success=bool(success),
            metadata=dict(metadata or {}),
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:
        logger.error(
            'audit log write failed event=%s success=%s: %s',
            event_type, success, exc,
        )
