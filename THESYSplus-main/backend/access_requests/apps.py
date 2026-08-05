"""AppConfig for the ``access_requests`` app.

The ``access_requests`` app will own ``/request-access`` and the admin
review/provisioning endpoints per design §2.2. Models, views, and
serializers are intentionally NOT defined in the Foundation Phase; only
the package shell is created so the project can boot with this app
registered.
"""

from django.apps import AppConfig


class AccessRequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access_requests'
