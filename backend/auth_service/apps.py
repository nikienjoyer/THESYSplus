"""AppConfig for the ``auth_service`` app.

The ``auth_service`` app will own ``/login``, ``/logout``, ``/refresh``,
``/me``, ``/sso/*``, JWT issuance, and refresh-cookie handling per design
§2.2. Models, views, and serializers are intentionally NOT defined in the
Foundation Phase; only the package shell is created so the project can
boot with this app registered.
"""

from django.apps import AppConfig


class AuthServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auth_service'
