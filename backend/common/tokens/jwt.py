"""JWT access token helpers.

Issues and verifies HS256 JWT access tokens with a ``kid`` JOSE header per
Requirements 2.6 / 2.7. The signing secret, ``kid``, and TTL come from
settings so a future key rotation only requires updating settings — not
code.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

import jwt as pyjwt
from django.conf import settings


class AccessTokenExpired(Exception):
    """Raised when an access token has expired (mapped to 401 ACCESS_TOKEN_EXPIRED)."""


class AccessTokenInvalid(Exception):
    """Raised when an access token fails signature/claim validation."""


def issue_access_token(user) -> str:
    """Issue an HS256 JWT for ``user``.

    Claims: ``iss``, ``sub``, ``role``, ``iat``, ``exp``, ``jti``.
    Header: ``alg=HS256``, ``kid=<settings.JWT_KID>``.
    """
    now = _dt.datetime.now(tz=_dt.timezone.utc)
    payload = {
        'iss': settings.JWT_ISSUER,
        'sub': str(user.id),
        'role': user.role,
        'iat': int(now.timestamp()),
        'exp': int((now + _dt.timedelta(seconds=settings.JWT_ACCESS_TTL_SECONDS)).timestamp()),
        'jti': uuid.uuid4().hex,
    }
    headers = {'kid': settings.JWT_KID}
    return pyjwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        headers=headers,
    )


def verify_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token.

    Returns the decoded payload dict on success. Raises
    ``AccessTokenExpired`` for expired tokens and ``AccessTokenInvalid``
    for any other failure (bad signature, missing claim, wrong issuer).
    """
    try:
        payload = pyjwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={'require': ['sub', 'role', 'iat', 'exp', 'jti']},
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise AccessTokenExpired() from exc
    except pyjwt.InvalidTokenError as exc:
        raise AccessTokenInvalid(str(exc)) from exc

    # Defence in depth: ensure role is one of the canonical values.
    if payload.get('role') not in ('student', 'faculty', 'administrator'):
        raise AccessTokenInvalid(f'invalid role claim: {payload.get("role")!r}')
    return payload
