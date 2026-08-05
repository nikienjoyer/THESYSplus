"""Password set/reset views — unified for first-set and recovery (Requirement 5.7)."""

from __future__ import annotations

import logging

from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.audit_logger import write as audit_write
from common.csrf import require_origin_match
from common.errors import make_error_response
from common.ratelimit import rate_limit_per_email, rate_limit_per_ip, rate_limit_per_token

from .serializers import ForgotPasswordSerializer, ResetPasswordSerializer
from .services import ResetTokenInvalid, consume_reset_token, issue_reset_token

logger = logging.getLogger('emails')


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


# ---------------------------------------------------------------------------
# POST /forgot-password
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
class ForgotPasswordView(APIView):
    """Initiate password reset — always returns 200 to prevent enumeration.

    Domain validation still runs (returns 400 INVALID_EMAIL_DOMAIN for typos)
    because the institutional domain is public knowledge per design §4.4.6.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @rate_limit_per_email(limit=3, window_seconds=3600, error_code='RATE_LIMITED_FORGOT_PASSWORD')
    def post(self, request, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'email'})
        if unknown is not None:
            return unknown

        serializer = ForgotPasswordSerializer(data=request.data)
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
                message='Forgot-password payload is invalid.',
                status=status.HTTP_400_BAD_REQUEST,
                details=dict(errors),
            )

        email = serializer.validated_data['email']

        # Always audit the REQUEST (whether or not the email matches a row).
        audit_write(
            'auth.password.reset_requested',
            actor=None,
            success=True,
            metadata={'email': email},
            request=request,
        )

        # Look up the user; on miss, do nothing — but always return 200.
        user = User.objects.filter(email=email, is_active=True).first()
        if user is not None:
            issue_reset_token(user, template='password_reset', request=request)
            logger.info('[EMAIL] Password reset email sent to %s', email)
        else:
            logger.info(
                '[EMAIL] Password reset requested for unknown/inactive account: %s',
                email,
            )

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# POST /reset-password
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
class ResetPasswordView(APIView):
    """Complete password reset — works for both first-set and recovery flows.

    Per Requirement 5.7 the endpoint is identical regardless of whether
    the user previously had a password.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @rate_limit_per_ip(limit=10, window_seconds=3600, error_code='RATE_LIMITED_IP')
    @rate_limit_per_token(limit=5, window_seconds=900, error_code='RATE_LIMITED_RESET_PASSWORD')
    def post(self, request, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'token', 'new_password'})
        if unknown is not None:
            return unknown

        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'new_password' in errors:
                first = errors['new_password'][0]
                code = getattr(first, 'code', 'VALIDATION_ERROR')
                return make_error_response(
                    code=str(code).upper(),
                    message=str(first),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'token' in errors:
                return make_error_response(
                    code='INVALID_RESET_TOKEN',
                    message='Reset token is missing or malformed.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return make_error_response(
                code='VALIDATION_ERROR',
                message='Reset-password payload is invalid.',
                status=status.HTTP_400_BAD_REQUEST,
                details=dict(errors),
            )

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            outcome = consume_reset_token(token, new_password, request=request)
        except ResetTokenInvalid:
            audit_write(
                'auth.password.reset_failed',
                actor=None,
                success=False,
                metadata={'reason': 'invalid_or_expired_token'},
                request=request,
            )
            return make_error_response(
                code='INVALID_RESET_TOKEN',
                message='Reset link is invalid or expired.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        del outcome  # outcome metadata already audited inside consume_reset_token
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# POST /setup-password — single-email account-activation flow
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
class SetupPasswordView(APIView):
    """Complete first-time account setup from the "Set Up Your Account" email.

    Shares ``consume_reset_token`` with ``ResetPasswordView`` (the token
    row, validation, and password-set logic are identical) but is exposed
    on its own route/response shape so the frontend's setup-account page
    doesn't have to reason about the recovery flow's wording.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @rate_limit_per_ip(limit=10, window_seconds=3600, error_code='RATE_LIMITED_IP')
    @rate_limit_per_token(limit=5, window_seconds=900, error_code='RATE_LIMITED_RESET_PASSWORD')
    def post(self, request, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'token', 'new_password'})
        if unknown is not None:
            return unknown

        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'new_password' in errors:
                first = errors['new_password'][0]
                code = getattr(first, 'code', 'VALIDATION_ERROR')
                return make_error_response(
                    code=str(code).upper(),
                    message=str(first),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'token' in errors:
                return make_error_response(
                    code='INVALID_RESET_TOKEN',
                    message='Setup token is missing or malformed.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return make_error_response(
                code='VALIDATION_ERROR',
                message='Setup-password payload is invalid.',
                status=status.HTTP_400_BAD_REQUEST,
                details=dict(errors),
            )

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            outcome = consume_reset_token(token, new_password, request=request)
        except ResetTokenInvalid:
            audit_write(
                'auth.password.reset_failed',
                actor=None,
                success=False,
                metadata={'reason': 'invalid_or_expired_token', 'flow': 'account_setup'},
                request=request,
            )
            return make_error_response(
                code='INVALID_RESET_TOKEN',
                message='Setup link is invalid or expired.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        del outcome  # outcome metadata already audited inside consume_reset_token
        return Response(
            {'message': 'Account activated successfully. You can now sign in.'},
            status=status.HTTP_200_OK,
        )
