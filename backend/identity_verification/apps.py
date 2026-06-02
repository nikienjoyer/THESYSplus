"""AppConfig for the ``identity_verification`` app.

Handles AI-assisted identity verification for access request automation.
"""

from django.apps import AppConfig


class IdentityVerificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'identity_verification'
    verbose_name = 'Identity Verification'
