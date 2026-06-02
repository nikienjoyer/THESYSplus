"""DRF serializers for the auth_service endpoints.

Validates ``/login`` payload shape and the institutional email domain.
Real password verification happens in the view (the serializer doesn't
touch the database) so that response codes are uniform per Requirement
1.3 (no enumeration leak).
"""

from __future__ import annotations

from rest_framework import serializers

from common.validators import (
    INVALID_EMAIL_DOMAIN,
    is_institutional_email,
)


class LoginSerializer(serializers.Serializer):
    """``POST /login`` request body."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, allow_blank=False, max_length=512)
    remember_me = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value: str) -> str:
        normalised = value.strip().lower()
        if not is_institutional_email(normalised):
            raise serializers.ValidationError(
                'Institutional email is required (must end with pampangastateu.edu.ph).',
                code=INVALID_EMAIL_DOMAIN,
            )
        return normalised
