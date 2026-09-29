"""Privacy-safe timing for the expensive upload and search stages."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging
import time
import uuid
from functools import wraps

_request_id = ContextVar('performance_request_id', default='background')
logger = logging.getLogger('thesys.performance')


@contextmanager
def trace_id(value):
    token = _request_id.set(value)
    try:
        yield
    finally:
        _request_id.reset(token)


@contextmanager
def timed_stage(name):
    started = time.perf_counter()
    try:
        yield
    finally:
        logger.info('stage=%s request_id=%s elapsed_ms=%.1f',
                    name, _request_id.get(), (time.perf_counter() - started) * 1000)


def timed(name):
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            with timed_stage(name):
                return function(*args, **kwargs)
        return wrapper
    return decorate


class RequestTimingMiddleware:
    """Log total route time without URLs, query strings, bodies, or user data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = uuid.uuid4().hex[:16]
        token = _request_id.set(request_id)
        started = time.perf_counter()
        try:
            response = self.get_response(request)
            route = getattr(getattr(request, 'resolver_match', None), 'view_name', None) or 'unmatched'
            logger.info('stage=http route=%s request_id=%s status=%s elapsed_ms=%.1f',
                        route, request_id, response.status_code,
                        (time.perf_counter() - started) * 1000)
            response['X-Request-ID'] = request_id
            return response
        finally:
            _request_id.reset(token)
