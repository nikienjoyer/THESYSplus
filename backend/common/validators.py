"""Shared validators for the Auth_Service.

Provides ``is_institutional_email``, ``is_student_number_email``, and
``validate_password_strength`` per design §11.5 and Requirements 1.2 / 1.4 / 5.5.

``is_student_number_email`` enforces the stricter format required for
access requests: ``<digits>@pampangastateu.edu.ph`` (student ID number
followed by the apex domain only — no subdomains accepted for self-service
registration).

Error code constants are exported for use by serializers and views so the
unified error envelope (``common.errors``) can return stable codes.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


# Error codes returned to clients via the unified error envelope.
INVALID_EMAIL_DOMAIN = 'INVALID_EMAIL_DOMAIN'
WEAK_PASSWORD = 'WEAK_PASSWORD'


# Case-insensitive match against the apex ``pampangastateu.edu.ph`` AND
# any subdomain. Used for general auth token operations where the full
# institution email range is valid.
_INSTITUTIONAL_EMAIL_RE = re.compile(
    r'^[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)*pampangastateu\.edu\.ph$',
    flags=re.IGNORECASE,
)

# Stricter format for self-service access requests:
# local part must be digits only (student ID number), apex domain only.
# Valid:   2023123456@pampangastateu.edu.ph
# Invalid: kurt@pampangastateu.edu.ph
# Invalid: 2023123456@student.pampangastateu.edu.ph
_STUDENT_NUMBER_EMAIL_RE = re.compile(
    r'^[0-9]+@pampangastateu\.edu\.ph$',
    flags=re.IGNORECASE,
)


def is_institutional_email(s: str) -> bool:
    """Return True iff ``s`` is a syntactically valid institutional email.

    Both the apex domain (``pampangastateu.edu.ph``) and any subdomain are
    accepted; comparison is case-insensitive. Whitespace and surrounding
    quotes are NOT stripped — callers should normalise input first.
    """
    if not isinstance(s, str):
        return False
    return bool(_INSTITUTIONAL_EMAIL_RE.match(s))


def is_student_number_email(s: str) -> bool:
    """Return True iff ``s`` is a student-number PSU email.

    Format: ``<digits_only>@pampangastateu.edu.ph``
    - Local part must contain only digits (the PSU student ID number).
    - Domain must be the apex ``pampangastateu.edu.ph`` exactly (no subdomains).

    This is the required format for self-service access requests so that
    the system can associate the request with a specific enrolled student.
    """
    if not isinstance(s, str):
        return False
    return bool(_STUDENT_NUMBER_EMAIL_RE.match(s))


_LETTER_RE = re.compile(r'[A-Za-z]')
_DIGIT_RE = re.compile(r'[0-9]')


def validate_password_strength(s: str) -> None:
    """Raise ``ValidationError(code=WEAK_PASSWORD)`` if ``s`` fails strength rules.

    Strength rules per Requirement 5.5:
    * Length ≥ 12.
    * At least one letter (A-Z, a-z).
    * At least one digit (0-9).
    """
    if (
        not isinstance(s, str)
        or len(s) < 12
        or not _LETTER_RE.search(s)
        or not _DIGIT_RE.search(s)
    ):
        raise ValidationError(
            'Password must be at least 12 characters and include both letters and digits.',
            code=WEAK_PASSWORD,
        )
