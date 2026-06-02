"""DRF JWT authentication class for the THESYS+ Auth_Service.

Reads ``Authorization: Bearer <jwt>`` and validates via
``common.tokens.jwt.verify_access_token``. Maps ``AccessTokenExpired`` to
``AccessTokenExpiredException`` (which the unified error envelope renders
with ``code='ACCESS_TOKEN_EXPIRED'``) so the frontend's axios refresh
interceptor (Wave A9) can detect and recover from expired tokens.

Imports of ``common.errors`` and ``accounts.models`` are intentionally
performed inside ``authenticate`` (rather than at module top) to avoid a
circular import: DRF lazily resolves ``DEFAULT_AUTHENTICATION_CLASSES``
during ``rest_framework.schemas`` init while ``rest_framework.views`` is
still loading, and ``common.errors`` imports from ``rest_framework.views``.
"""

from __future__ import annotations

from rest_framework import authentication
from rest_framework import exceptions as drf_exceptions


class JWTAuthentication(authentication.BaseAuthentication):
    """Bearer-token authentication backed by ``common.tokens.jwt``."""

    keyword = 'Bearer'

    def authenticate(self, request):
        # Lazy imports — see module docstring for the circular-import note.
        from accounts.models import User
        from common.errors import AccessTokenExpiredException
        from common.tokens.jwt import (
            AccessTokenExpired,
            AccessTokenInvalid,
            verify_access_token,
        )

        header = authentication.get_authorization_header(request).decode('iso-8859-1')
        if not header:
            return None  # No header → leave unauthenticated; IsAuthenticated will reject.

        parts = header.split()
        if not parts or parts[0].lower() != self.keyword.lower():
            return None  # Not a Bearer token; let other auth classes try.
        if len(parts) == 1:
            raise drf_exceptions.AuthenticationFailed('Invalid Authorization header: missing token.')
        if len(parts) > 2:
            raise drf_exceptions.AuthenticationFailed('Invalid Authorization header: too many segments.')

        raw_token = parts[1]
        try:
            payload = verify_access_token(raw_token)
        except AccessTokenExpired as exc:
            raise AccessTokenExpiredException() from exc
        except AccessTokenInvalid as exc:
            raise drf_exceptions.AuthenticationFailed(str(exc) or 'Invalid access token.')

        user = User.objects.filter(pk=payload['sub']).first()
        if user is None or not user.is_active:
            raise drf_exceptions.AuthenticationFailed('User not found or inactive.')
        return (user, payload)

    def authenticate_header(self, request):
        return self.keyword
