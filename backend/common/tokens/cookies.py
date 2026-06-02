"""Refresh-cookie helpers.

Apply the project-wide refresh-cookie attributes per Requirements 4.2 /
4.3 / 4.5 / 4.6 / 9.1: ``HttpOnly``, ``Secure`` (gated on dev mode),
``SameSite=Lax``, ``Path=/api/v1/auth``, and ``Max-Age`` derived from
``remember_me``.
"""

from __future__ import annotations

import os

from django.conf import settings


def _secure_flag() -> bool:
    """Return True unless DJANGO_ENV=development.

    Per Requirement 27 / design §5.1, the dev cookie is NOT marked Secure
    so contributors hitting ``http://localhost`` can still receive it.
    """
    return os.environ.get('DJANGO_ENV', 'development').lower() != 'development'


def set_refresh_cookie(response, token: str, *, remember_me: bool) -> None:
    """Set the refresh-token cookie on ``response`` with project-wide attrs.

    ``remember_me=True`` sets ``Max-Age = REFRESH_TOKEN_REMEMBER_ME_TTL_SECONDS`` (30 days).
    ``remember_me=False`` sets a session cookie (no Max-Age) so the cookie
    expires when the browser closes per Requirement 4.5.
    """
    max_age = settings.REFRESH_TOKEN_REMEMBER_ME_TTL_SECONDS if remember_me else None
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        path=settings.REFRESH_COOKIE_PATH,
        secure=_secure_flag(),
        httponly=True,
        samesite='Lax',
    )


def clear_refresh_cookie(response) -> None:
    """Clear the refresh-token cookie. Used by logout and reset flows."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite='Lax',
    )
