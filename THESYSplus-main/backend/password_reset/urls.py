"""URL configuration for the ``password_reset`` app.

Mounts ``/forgot-password/`` and ``/reset-password/`` under the shared
``/api/v1/auth/`` prefix (see ``thesys/urls.py``). The unified reset
endpoint serves both first-password-set after Administrator approval
and ordinary forgot-password recovery per Requirement 5.7.
"""

from django.urls import path

from .views import ForgotPasswordView, ResetPasswordView


urlpatterns = [
    path('forgot-password/', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='auth-reset-password'),
]
