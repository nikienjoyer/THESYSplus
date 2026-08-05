"""DRF serializers for the password_reset endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.validators import (
    INVALID_EMAIL_DOMAIN,
    WEAK_PASSWORD,
    is_institutional_email,
    validate_password_strength,
)


class ForgotPasswordSerializer(serializers.Serializer):
    """``POST /forgot-password`` request body."""

    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        normalised = value.strip().lower()
        if not is_institutional_email(normalised):
            raise serializers.ValidationError(
                'Institutional email is required (must end with pampangastateu.edu.ph).',
                code=INVALID_EMAIL_DOMAIN,
            )
        return normalised


class ResetPasswordSerializer(serializers.Serializer):
    """``POST /reset-password`` request body."""

    token = serializers.CharField(min_length=10, max_length=512, write_only=True)
    new_password = serializers.CharField(min_length=1, max_length=512, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password_strength(value)
        except DjangoValidationError as exc:
            # Surface the same WEAK_PASSWORD code through DRF's path.
            message = exc.message if hasattr(exc, 'message') else str(exc)
            raise serializers.ValidationError(
                str(message),
                code=WEAK_PASSWORD,
            )
        return value
