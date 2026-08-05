"""Origin/Referer CSRF check decorator for cookie-bearing endpoints.

Per Requirement 9.4 / design §5.7: cookie-bearing endpoints that don't
carry a session cookie (login, refresh, logout, forgot-password,
reset-password, request-access) cannot use Django's session-bound CSRF
token. Instead they require the request's ``Origin`` header (falling back
to ``Referer``) to match an entry in ``settings.CORS_ALLOWED_ORIGINS``.
"""

from __future__ import annotations

from functools import wraps
from urllib.parse import urlsplit

from django.conf import settings

from common.errors import CsrfFailure, OriginNotAllowed


def _allowed_origins() -> set[str]:
    """Return the configured set of allowed origins, lower-cased."""
    return {origin.rstrip('/').lower() for origin in settings.CORS_ALLOWED_ORIGINS}


def _normalise_origin(value: str) -> str | None:
    """Reduce a URL or origin to ``scheme://host[:port]`` (lower-case)."""
    if not value:
        return None
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return None
    return f'{parts.scheme}://{parts.netloc}'.lower()


def require_origin_match(view_func):
    """Reject requests whose Origin (or Referer) doesn't match an allowed origin.

    GET / HEAD / OPTIONS pass through unguarded (no state change).
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return view_func(request, *args, **kwargs)

        origin = request.META.get('HTTP_ORIGIN', '')
        referer = request.META.get('HTTP_REFERER', '')

        candidate = _normalise_origin(origin) or _normalise_origin(referer)
        if not candidate:
            raise CsrfFailure(
                detail='Missing Origin and Referer; cannot verify request source.',
            )

        if candidate not in _allowed_origins():
            raise OriginNotAllowed(detail=f'Request origin {candidate!r} is not allowed.')

        return view_func(request, *args, **kwargs)

    return _wrapped
