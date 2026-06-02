"""Public service functions for the ``accounts`` app.

Exposes ``set_password`` and ``verify_password`` so cross-app callers
(``auth_service``, ``password_reset``) don't reach into the User model
directly. ``verify_password`` returns ``(ok, needs_rehash)`` so the login
view can re-hash with current parameters per Requirement 8.3.
"""

from __future__ import annotations

from django.contrib.auth.hashers import (
    check_password,
    get_hasher,
    identify_hasher,
    is_password_usable,
    make_password,
)

from .models import User


def set_password(user: User, plaintext: str) -> None:
    """Hash ``plaintext`` with the project's primary hasher and persist.

    The primary hasher is whichever entry sits first in
    ``settings.PASSWORD_HASHERS`` (Argon2id per Requirement 8.1).
    """
    user.password = make_password(plaintext)
    user.save(update_fields=['password', 'updated_at'])


def verify_password(user: User, plaintext: str) -> tuple[bool, bool]:
    """Verify ``plaintext`` against the user's stored hash.

    Returns ``(ok, needs_rehash)``:

    * ``ok`` is True iff the password matches.
    * ``needs_rehash`` is True iff the stored hash uses an algorithm older
      than the current primary hasher (Requirement 8.3 — re-hash on
      successful login when parameters drift).
    """
    if not is_password_usable(user.password or ''):
        return False, False

    ok = check_password(plaintext, user.password)
    if not ok:
        return False, False

    try:
        stored_hasher = identify_hasher(user.password)
        primary_hasher = get_hasher('default')
        needs_rehash = stored_hasher.algorithm != primary_hasher.algorithm
    except Exception:
        # Defensive: an unrecognised hash format is treated as stale so
        # the caller has the option to upgrade it.
        needs_rehash = True

    return True, needs_rehash
