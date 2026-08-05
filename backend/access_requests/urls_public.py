"""Public URL configuration for the ``access_requests`` app.

Mounted at ``/api/v1/auth/`` by the root URLConf so the public submission
sits next to login / logout / refresh / forgot-password / reset-password.
"""

from django.urls import path

from .views import RequestAccessView, VerifyEmailView


urlpatterns = [
    path('request-access/', RequestAccessView.as_view(), name='access-request-submit'),
    path('verify-email/', VerifyEmailView.as_view(), name='access-request-verify-email'),
]
