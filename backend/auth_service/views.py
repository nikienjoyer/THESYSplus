"""Auth API views: login, refresh, logout, me.

Per design §4 / §5 and Requirements 1, 2, 3, 4, 9. Each view delegates
the heavy lifting to ``auth_service/services.py`` (token issuance/
rotation) or ``accounts/services.py`` (password verification). The CSRF
Origin guard sits on every cookie-bearing endpoint per Requirement 9.4.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import PermissionRegistry
from accounts.services import set_password as accounts_set_password
from accounts.services import verify_password as accounts_verify_password
from common.audit_logger import write as audit_write
from common.csrf import require_origin_match
from common.errors import (
    RefreshReuseDetected,
    RefreshTokenExpired,
    RefreshTokenRevoked,
    make_error_response,
)
from common.ratelimit import rate_limit_per_email_on_failure, rate_limit_per_ip
from common.tokens.cookies import clear_refresh_cookie, set_refresh_cookie

from .serializers import LoginSerializer
from .services import issue_token_pair, revoke_one, rotate_refresh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reject_unknown_fields(request, allowed: set):
    """Return a 400 UNKNOWN_FIELD response when extra keys are present, else None."""
    if not isinstance(request.data, dict):
        return None
    extra = set(request.data.keys()) - allowed
    if extra:
        return make_error_response(
            code='UNKNOWN_FIELD',
            message=f'Unknown field(s): {sorted(extra)}',
            status=status.HTTP_400_BAD_REQUEST,
            details={'unknown': sorted(extra)},
        )
    return None


def _user_payload(user) -> dict:
    return {
        'id': str(user.id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
    }


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
@method_decorator(rate_limit_per_ip(10, 60, 'RATE_LIMITED_IP'), name='post')
@method_decorator(rate_limit_per_email_on_failure(5, 15*60, 'RATE_LIMITED_LOGIN'), name='post')
class LoginView(APIView):
    """Authenticate with institutional email + password.

    On success: issues access JWT + refresh cookie, audits ``auth.login.success``.
    On failure: returns 401 INVALID_CREDENTIALS, audits ``auth.login.failure``
    with the attempted email and source IP per Requirement 1.7.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'email', 'password', 'remember_me'})
        if unknown is not None:
            return unknown

        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'email' in errors:
                first = errors['email'][0]
                code = getattr(first, 'code', 'VALIDATION_ERROR')
                return make_error_response(
                    code=str(code).upper(),
                    message=str(first),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return make_error_response(
                code='VALIDATION_ERROR',
                message='Login payload is invalid.',
                status=status.HTTP_400_BAD_REQUEST,
                details=dict(errors),
            )

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        remember_me = serializer.validated_data['remember_me']

        user = User.objects.filter(email=email).first()
        ok, needs_rehash = (False, False)
        if user is not None and user.is_active:
            ok, needs_rehash = accounts_verify_password(user, password)

        if not ok:
            audit_write(
                'auth.login.failure',
                actor=None,
                target=user if user else None,
                success=False,
                metadata={
                    'email_attempted': email,
                    'reason': ('not_found' if user is None else 'bad_password'),
                },
                request=request,
            )
            return make_error_response(
                code='INVALID_CREDENTIALS',
                message='Email or password is incorrect.',
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if needs_rehash:
            accounts_set_password(user, password)

        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at', 'updated_at'])

        pair = issue_token_pair(user, request, remember_me=remember_me)

        body = {
            'access_token': pair.access_token,
            'token_type': 'Bearer',
            'expires_in': settings.JWT_ACCESS_TTL_SECONDS,
            'user': _user_payload(user),
        }
        response = Response(body, status=status.HTTP_200_OK)
        set_refresh_cookie(response, pair.refresh_plaintext, remember_me=remember_me)

        audit_write(
            'auth.login.success',
            actor=user,
            target=user,
            success=True,
            metadata={'remember_me': remember_me, 'family_id': str(pair.refresh_row.family_id)},
            request=request,
        )
        return response


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
@method_decorator(rate_limit_per_ip(60, 60, 'RATE_LIMITED_IP'), name='post')
class RefreshView(APIView):
    """Rotate the refresh token; reuse detection revokes the entire family."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        plaintext = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not plaintext:
            return make_error_response(
                code='REFRESH_TOKEN_REVOKED',
                message='Refresh token cookie is missing.',
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            pair = rotate_refresh(plaintext, request)
        except RefreshTokenExpired:
            audit_write('auth.refresh.expired', success=False, metadata={}, request=request)
            return make_error_response(
                code='REFRESH_TOKEN_EXPIRED',
                message='Refresh token has expired.',
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except RefreshReuseDetected:
            audit_write('auth.refresh.reuse_detected', success=False, metadata={}, request=request)
            return make_error_response(
                code='REFRESH_TOKEN_REUSE_DETECTED',
                message='Refresh token reuse detected; the entire session family has been revoked.',
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except RefreshTokenRevoked:
            audit_write('auth.refresh.revoked', success=False, metadata={}, request=request)
            return make_error_response(
                code='REFRESH_TOKEN_REVOKED',
                message='Refresh token has been revoked.',
                status=status.HTTP_401_UNAUTHORIZED,
            )

        body = {
            'access_token': pair.access_token,
            'token_type': 'Bearer',
            'expires_in': settings.JWT_ACCESS_TTL_SECONDS,
        }
        response = Response(body, status=status.HTTP_200_OK)
        set_refresh_cookie(response, pair.refresh_plaintext, remember_me=pair.refresh_row.remember_me)
        return response


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
class LogoutView(APIView):
    """Tolerant logout — clears the refresh cookie and revokes only the presented row."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        plaintext = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        revoked = False
        if plaintext:
            revoked = revoke_one(plaintext)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)

        if revoked:
            audit_write('auth.logout', success=True, metadata={}, request=request)
        return response


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

class MeView(APIView):
    """Return the authenticated user's profile + permissions registry view."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        body = {
            **_user_payload(user),
            'permissions': PermissionRegistry.for_role(user.role),
        }
        return Response(body, status=status.HTTP_200_OK)
