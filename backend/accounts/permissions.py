"""Permission registry and DRF permission classes for the accounts app.

The ``PermissionRegistry`` is a process-local dict mapping role → permission
keys. Downstream modules call ``register(role, *keys)`` from their
``AppConfig.ready()`` to extend it without modifying ``auth_service``.
``GET /me`` reads from this registry per Requirement 3.3.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from common.errors import InsufficientRole

from .models import Role


class PermissionRegistry:
    """Process-local map: role (str) → set of permission keys."""

    _by_role: dict[str, set[str]] = {}

    @classmethod
    def register(cls, role: str, *keys: str) -> None:
        """Add ``keys`` to the permission set for ``role`` (idempotent)."""
        cls._by_role.setdefault(str(role), set()).update(keys)

    @classmethod
    def for_role(cls, role: str) -> list[str]:
        """Return the sorted permission keys for ``role`` (empty when none)."""
        return sorted(cls._by_role.get(str(role), set()))

    @classmethod
    def clear(cls) -> None:
        """Reset the registry — used by tests."""
        cls._by_role = {}


class IsAdministrator(BasePermission):
    """Allow only authenticated users whose role == administrator.

    For unauthenticated callers we return ``False`` so DRF surfaces a 401
    ``NOT_AUTHENTICATED``. For authenticated callers with the wrong
    role we raise ``InsufficientRole`` directly so the unified error
    envelope uses the canonical code ``INSUFFICIENT_ROLE`` (DRF's stock
    handler would otherwise emit ``permission_denied`` because
    ``PermissionDenied.default_code`` shadows the per-permission code in
    ``common.errors._resolve_code``).
    """

    message = 'Administrator role required.'
    code = 'INSUFFICIENT_ROLE'

    def has_permission(self, request, view) -> bool:
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'role', None) != Role.ADMINISTRATOR:
            raise InsufficientRole()
        return True
