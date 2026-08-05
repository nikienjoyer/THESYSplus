"""URL configuration for the ``password_reset`` app.

Mounts ``/forgot-password/``, ``/reset-password/``, and
``/setup-password/`` under the shared ``/api/v1/auth/`` prefix (see
``thesys/urls.py``). ``/setup-password/`` and ``/reset-password/`` share
the same token-validation logic (``consume_reset_token``) but expose
distinct routes/response shapes for the account-setup vs. recovery flows.
"""

from django.urls import path

from .views import ForgotPasswordView, ResetPasswordView, SetupPasswordView


urlpatterns = [
    path('forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='auth-reset-password'),
    path('setup-password/', SetupPasswordView.as_view(), name='auth-setup-password'),
]
