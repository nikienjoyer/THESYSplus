"""Rate limiting decorators for the Auth_Service.

Per Requirement 10 / design §8: enforce per-email and per-IP request
budgets backed by ``django.core.cache``. On exceed return 429 with the
unified error envelope and a ``Retry-After`` header.

Development Mode:
When DEBUG=True, rate limits are relaxed for local testing:
- Per-IP limits: 20 requests/minute (instead of production limits)
- Per-email limits: 20 requests/minute (instead of production limits)
Production limits remain unchanged when DEBUG=False.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from django.conf import settings
from django.core.cache import cache

from common.errors import make_error_response


def _get_debug_limits(limit: int, window_seconds: int) -> tuple[int, int]:
    """Adjust rate limits for development mode.
    
    When DEBUG=True, use more permissive limits for local testing:
    - 20 requests per minute (60 seconds)
    
    Production limits (DEBUG=False) remain unchanged.
    
    Args:
        limit: Production request limit
        window_seconds: Production window in seconds
        
    Returns:
        Tuple of (adjusted_limit, adjusted_window_seconds)
    """
    if getattr(settings, 'DEBUG', False):
        # Development mode: 20 requests per minute
        return 20, 60
    # Production mode: use original limits
    return limit, window_seconds


def _client_ip(request) -> str:
    """Extract the client IP, honouring X-Forwarded-For when present."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # Take the FIRST entry (client) per RFC 7239 / common LB convention.
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _email_from_request(request) -> str | None:
    """Pull the lowercased email from an authenticated payload (DRF) or POST."""
    data = getattr(request, 'data', None) or {}
    email = data.get('email') if isinstance(data, dict) else None
    if not email and request.method == 'POST':
        email = request.POST.get('email')
    if not email:
        return None
    return str(email).strip().lower()


def _hit_and_check(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Increment the counter for ``key``; return (allowed, retry_after_seconds).

    Uses ``cache.add`` to seed the bucket so the TTL window is anchored at
    the first hit. Subsequent hits ``incr`` the same key — the TTL is
    preserved.
    """
    seeded = cache.add(key, 1, timeout=window_seconds)
    if seeded:
        return True, window_seconds

    try:
        count = cache.incr(key)
    except ValueError:
        # Key expired between ``add`` and ``incr`` — treat as a fresh window.
        cache.set(key, 1, timeout=window_seconds)
        return True, window_seconds

    if count > limit:
        # Best-effort retry hint — exact remaining TTL isn't always
        # exposed by the cache backend; window_seconds is an upper bound.
        return False, window_seconds
    return True, window_seconds


def rate_limit_per_email(limit: int, window_seconds: int, error_code: str) -> Callable:
    """Limit to ``limit`` calls per ``window_seconds`` per email.

    Pulls the email from ``request.data`` / ``request.POST``. Requests
    without an email passthrough untouched.
    
    In DEBUG mode, uses relaxed limits (20/minute) for local testing.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request_or_self, *args, **kwargs):
            # Handle both direct method decoration and @method_decorator
            if hasattr(request_or_self, 'META'):
                # request_or_self is the request
                request = request_or_self
            else:
                # request_or_self is self, request is first in args
                request = args[0] if args else kwargs.get('request')
                if not request:
                    return view_func(request_or_self, *args, **kwargs)
            
            email = _email_from_request(request)
            if email:
                # Adjust limits for DEBUG mode
                actual_limit, actual_window = _get_debug_limits(limit, window_seconds)
                
                key = f'ratelimit:email:{view_func.__qualname__}:{email}'
                allowed, retry = _hit_and_check(key, actual_limit, actual_window)
                if not allowed:
                    return make_error_response(
                        code=error_code,
                        message='Too many requests. Please try again later.',
                        status=429,
                        retry_after_seconds=retry,
                    )
            return view_func(request_or_self, *args, **kwargs)

        return _wrapped

    return decorator


def rate_limit_per_ip(limit: int, window_seconds: int, error_code: str) -> Callable:
    """Limit to ``limit`` calls per ``window_seconds`` per source IP.
    
    In DEBUG mode, uses relaxed limits (20/minute) for local testing.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request_or_self, *args, **kwargs):
            # Handle both direct method decoration and @method_decorator
            if hasattr(request_or_self, 'META'):
                # request_or_self is the request
                request = request_or_self
            else:
                # request_or_self is self, request is first in args
                request = args[0] if args else kwargs.get('request')
                if not request:
                    return view_func(request_or_self, *args, **kwargs)
            
            # Adjust limits for DEBUG mode
            actual_limit, actual_window = _get_debug_limits(limit, window_seconds)
            
            ip = _client_ip(request)
            key = f'ratelimit:ip:{view_func.__qualname__}:{ip}'
            allowed, retry = _hit_and_check(key, actual_limit, actual_window)
            if not allowed:
                return make_error_response(
                    code=error_code,
                    message='Too many requests. Please try again later.',
                    status=429,
                    retry_after_seconds=retry,
                )
            return view_func(request_or_self, *args, **kwargs)

        return _wrapped

    return decorator


def rate_limit_per_email_on_failure(
    limit: int, window_seconds: int, error_code: str
) -> Callable:
    """Limit to ``limit`` failed attempts per ``window_seconds`` per email.

    This decorator increments the counter ONLY when the view returns a 401
    response (failed login). Successful logins do not count against the budget.
    Per design §8.3, this prevents successful logins from consuming the
    failure budget.

    Pulls the email from ``request.data`` / ``request.POST``. Requests
    without an email passthrough untouched.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            email = _email_from_request(request)
            if not email:
                return view_func(request, *args, **kwargs)

            key = f'ratelimit:email:{view_func.__qualname__}:{email}'

            # Check if already rate limited (without incrementing)
            current = cache.get(key, 0)
            if current > limit:
                # Already exceeded, return 429
                return make_error_response(
                    code=error_code,
                    message='Too many requests. Please try again later.',
                    status=429,
                    retry_after_seconds=window_seconds,
                )

            # Execute the view
            response = view_func(request, *args, **kwargs)

            # Increment counter ONLY on failure (401 status)
            if response.status_code == 401:
                allowed, retry = _hit_and_check(key, limit, window_seconds)
                if not allowed:
                    # Now exceeded after this failure
                    return make_error_response(
                        code=error_code,
                        message='Too many requests. Please try again later.',
                        status=429,
                        retry_after_seconds=retry,
                    )

            # On success (200), reset the budget by deleting the key
            elif response.status_code == 200:
                cache.delete(key)

            return response

        return _wrapped

    return decorator


def rate_limit_per_token(limit: int, window_seconds: int, error_code: str) -> Callable:
    """Limit to ``limit`` calls per ``window_seconds`` per token.

    Pulls the token from ``request.data['token']``. Requests without a token
    passthrough untouched. This is used for reset-password endpoints where
    we want to limit attempts per specific reset token.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request_or_self, *args, **kwargs):
            # Handle both direct method decoration and @method_decorator
            if hasattr(request_or_self, 'META'):
                # request_or_self is the request
                request = request_or_self
            else:
                # request_or_self is self, request is first in args
                request = args[0] if args else kwargs.get('request')
                if not request:
                    return view_func(request_or_self, *args, **kwargs)
            
            data = getattr(request, 'data', None) or {}
            token = data.get('token') if isinstance(data, dict) else None
            if not token and request.method == 'POST':
                token = request.POST.get('token')
            if not token:
                return view_func(request_or_self, *args, **kwargs)

            # Use a hash of the token for the key to avoid storing plaintext
            import hashlib
            token_hash = hashlib.sha256(str(token).encode()).hexdigest()[:16]
            key = f'ratelimit:token:{view_func.__qualname__}:{token_hash}'
            allowed, retry = _hit_and_check(key, limit, window_seconds)
            if not allowed:
                return make_error_response(
                    code=error_code,
                    message='Too many requests. Please try again later.',
                    status=429,
                    retry_after_seconds=retry,
                )
            return view_func(request_or_self, *args, **kwargs)

        return _wrapped

    return decorator
