"""AppConfig for the ``accounts`` app.

Seeds the permission registry with ``auth.read_self`` for all three roles
in ``ready()`` per Requirement 3.3 — downstream modules call
``PermissionRegistry.register`` from their own ``AppConfig.ready()`` to
add module-specific permissions.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self) -> None:
        from .models import Role
        from .permissions import PermissionRegistry

        for role in (Role.STUDENT, Role.FACULTY, Role.ADMINISTRATOR):
            PermissionRegistry.register(role, 'auth.read_self')
