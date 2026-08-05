"""URL configuration for the ``auth_service`` app.

Mounts ``/login``, ``/logout``, ``/refresh``, ``/me``, and the SSO stubs.
Per Requirement 6.5 the SSO routes live in their own module so swapping
in a real provider doesn't touch the login/token surface.
"""

from django.urls import path

from .sso import InitiateSsoView, SsoCallbackView
from .views import LoginView, LogoutView, MeView, RefreshView


urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('refresh/', RefreshView.as_view(), name='auth-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('sso/initiate/', InitiateSsoView.as_view(), name='auth-sso-initiate'),
    path('sso/callback/', SsoCallbackView.as_view(), name='auth-sso-callback'),
]
