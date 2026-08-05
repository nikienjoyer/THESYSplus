"""Pytest configuration shared across the THESYS+ backend test suite.

Fixtures:
    fake_user       — in-memory User-like objects for pure property tests.
    clear_rate_limit_cache — clears the Django cache before every test so that
                      per-IP / per-email rate-limit counters accumulated by one
                      test cannot bleed into the next. LocMemCache is
                      process-wide; without this teardown the IP counter for
                      127.0.0.1 accumulates across the full suite and trips the
                      DEBUG-mode 20-req/min limit before the audit tests run.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Callable

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """Clear the cache before (and after) every test.

    Prevents rate-limit counter bleed between tests that hit
    ``/api/v1/auth/login/`` or any other rate-limited endpoint.
    All requests in the Django test client originate from 127.0.0.1, so a
    shared LocMemCache would accumulate counts across the entire test session
    without this reset.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fake_user() -> Callable[..., SimpleNamespace]:
    """Return a factory producing in-memory User-like objects.

    The factory accepts ``role`` and optional ``id`` overrides. The result
    duck-types as a User for the purposes of ``issue_access_token`` and
    ``verify_access_token`` (it only reads ``id`` and ``role``).
    """

    def _make(role: str = 'student', id: uuid.UUID | None = None) -> SimpleNamespace:
        return SimpleNamespace(id=id or uuid.uuid4(), role=role)

    return _make
