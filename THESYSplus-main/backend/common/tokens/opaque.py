"""Opaque refresh token helpers.

``generate_opaque_token()`` produces a URL-safe random string with at
least 256 bits of entropy (``secrets.token_urlsafe(32)``).
``sha256(token)`` returns the lowercase hex digest used as the persisted
``token_hash`` column per Requirement 2.8.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_opaque_token() -> str:
    """Generate a URL-safe random token with ≥256 bits of entropy."""
    # ``token_urlsafe(32)`` returns 32 random bytes, base64-url-encoded
    # (≥256 bits of entropy, ≥43 characters).
    return secrets.token_urlsafe(32)


def sha256(token: str) -> str:
    """Return the lowercase hex SHA-256 digest of ``token``.

    Idempotent: ``sha256(s) == sha256(s)`` for any ``s``. The output is
    always exactly 64 lowercase hex characters.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
