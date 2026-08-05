"""Unified error envelope renderer and DRF exception handler.

Centralizes the ``{"error": {"code", "message", "details"}}`` response
shape (design §14.1) so every Auth_Service endpoint returns errors in the
same format. Also exposes ``set_retry_after`` for 429 responses so the
Retry-After header and the JSON ``details.retry_after_seconds`` stay in
sync.
"""

from __future__ import annotations

from typing import Any

from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def make_error_response(
    *,
    code: str,
    message: str,
    status: int,
    details: dict[str, Any] | None = None,
    retry_after_seconds: int | None = None,
) -> Response:
    """Build a DRF Response carrying the unified error envelope."""
    body: dict[str, Any] = {'error': {'code': code, 'message': message}}
    if details:
        body['error']['details'] = dict(details)
    if retry_after_seconds is not None:
        body['error'].setdefault('details', {})
        body['error']['details']['retry_after_seconds'] = int(retry_after_seconds)

    response = Response(body, status=status)
    if retry_after_seconds is not None:
        response['Retry-After'] = str(int(retry_after_seconds))
    return response


def set_retry_after(response: Response, seconds: int) -> Response:
    """Annotate a 429 response with the ``Retry-After`` header and details."""
    response['Retry-After'] = str(int(seconds))
    if isinstance(response.data, dict):
        err = response.data.setdefault('error', {})
        details = err.setdefault('details', {})
        details['retry_after_seconds'] = int(seconds)
    return response


# ---------------------------------------------------------------------------
# Custom exceptions for the auth flow
# ---------------------------------------------------------------------------


class RefreshTokenExpired(drf_exceptions.AuthenticationFailed):
    default_code = 'REFRESH_TOKEN_EXPIRED'
    default_detail = 'Refresh token has expired.'


class RefreshTokenRevoked(drf_exceptions.AuthenticationFailed):
    default_code = 'REFRESH_TOKEN_REVOKED'
    default_detail = 'Refresh token has been revoked.'


class RefreshReuseDetected(drf_exceptions.AuthenticationFailed):
    default_code = 'REFRESH_TOKEN_REUSE_DETECTED'
    default_detail = 'Refresh token reuse detected; the entire session family has been revoked.'


class AccessTokenExpiredException(drf_exceptions.AuthenticationFailed):
    default_code = 'ACCESS_TOKEN_EXPIRED'
    default_detail = 'Access token has expired.'


class OriginNotAllowed(drf_exceptions.PermissionDenied):
    default_code = 'ORIGIN_NOT_ALLOWED'
    default_detail = 'Request origin is not allowed.'


class CsrfFailure(drf_exceptions.PermissionDenied):
    default_code = 'CSRF_FAILURE'
    default_detail = 'CSRF check failed.'


class InsufficientRole(drf_exceptions.PermissionDenied):
    default_code = 'INSUFFICIENT_ROLE'
    default_detail = 'Administrator role required.'


# ---------------------------------------------------------------------------
# DRF exception handler
# ---------------------------------------------------------------------------
#
# We delegate first to DRF's stock handler to honour status code mapping for
# DRF/Django exceptions, then reshape the response body into the unified
# envelope. Non-DRF exceptions fall through to Django's default 500 page.

# Map of DRF default codes / class names to our canonical envelope codes.
# Anything not listed here uses the exception's ``default_code`` (DRF's
# convention) or the literal exception class name as a fallback.
_CODE_OVERRIDES: dict[type, str] = {
    drf_exceptions.NotAuthenticated: 'NOT_AUTHENTICATED',
    drf_exceptions.AuthenticationFailed: 'AUTHENTICATION_FAILED',
    drf_exceptions.PermissionDenied: 'PERMISSION_DENIED',
    drf_exceptions.NotFound: 'NOT_FOUND',
    drf_exceptions.MethodNotAllowed: 'METHOD_NOT_ALLOWED',
    drf_exceptions.UnsupportedMediaType: 'UNSUPPORTED_MEDIA_TYPE',
    drf_exceptions.Throttled: 'THROTTLED',
    drf_exceptions.ValidationError: 'VALIDATION_ERROR',
}


def _resolve_code(exc: Exception) -> str:
    """Pick the canonical error code for ``exc``."""
    # Custom auth exceptions above carry an explicit ``default_code``.
    code = getattr(exc, 'default_code', None) or getattr(exc, 'code', None)
    if code:
        return str(code)
    return _CODE_OVERRIDES.get(type(exc), type(exc).__name__.upper())


def _resolve_message(exc: Exception, response_data: Any) -> str:
    """Pick a single human-readable message for ``exc``."""
    if isinstance(response_data, dict):
        # DRF often nests under 'detail' or per-field arrays.
        if 'detail' in response_data:
            return str(response_data['detail'])
        # Per-field errors — surface the first one.
        for key, value in response_data.items():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
    if isinstance(response_data, list) and response_data:
        return str(response_data[0])
    return str(exc) if str(exc) else 'Request failed.'


def _resolve_details(response_data: Any) -> dict[str, Any] | None:
    """Build the optional ``details`` field — per-field validation errors etc."""
    if isinstance(response_data, dict) and 'detail' not in response_data:
        # Per-field validation errors live in a dict; copy as-is.
        return dict(response_data)
    return None


def unified_exception_handler(exc, context):
    """DRF EXCEPTION_HANDLER that returns the unified envelope."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = _resolve_code(exc)
    message = _resolve_message(exc, response.data)
    details = _resolve_details(response.data)

    body: dict[str, Any] = {'error': {'code': code, 'message': message}}
    if details:
        body['error']['details'] = details

    # Throttled exceptions carry ``wait`` (seconds). Hoist it into the
    # standard envelope + Retry-After header.
    if isinstance(exc, drf_exceptions.Throttled) and exc.wait is not None:
        seconds = int(exc.wait)
        body['error'].setdefault('details', {})
        body['error']['details']['retry_after_seconds'] = seconds
        response['Retry-After'] = str(seconds)

    response.data = body
    return response
