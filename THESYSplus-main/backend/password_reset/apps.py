"""AppConfig for the ``password_reset`` app.

The ``password_reset`` app will own ``/forgot-password`` and
``/reset-password``, plus reset-token issuance and validation per design
§2.2. Models, views, and serializers are intentionally NOT defined in
the Foundation Phase; only the package shell is created so the project
can boot with this app registered.
"""

from django.apps import AppConfig


class PasswordResetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'password_reset'
