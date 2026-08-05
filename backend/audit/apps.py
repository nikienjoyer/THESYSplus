"""AppConfig for the ``audit`` app.

The ``audit`` app will own the append-only audit log writer and admin
read endpoints per design §2.2. Models, views, and serializers are
intentionally NOT defined in the Foundation Phase; only the package
shell is created so the project can boot with this app registered.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
