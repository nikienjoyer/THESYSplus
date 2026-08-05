"""DRF serializers for the access_requests endpoints.

The public ``RequestAccessSerializer`` enforces institutional email
domain (Requirement 7.3) and rejects ``administrator`` as a requested
role at validation time (Requirement 7.8). DB-level enforcement of
``EMAIL_ALREADY_REGISTERED`` and ``DUPLICATE_REQUEST_PENDING`` lives in
the view per design §6.4 because they require model lookups.

The admin serializers shape the list / approve / deny responses.
"""

from __future__ import annotations

from rest_framework import serializers

from accounts.models import Role
from common.validators import (
    INVALID_EMAIL_DOMAIN,
    is_institutional_email,
    is_student_number_email,
)

from .models import AccessRequest


# ---------------------------------------------------------------------------
# Public submission
# ---------------------------------------------------------------------------

class RequestAccessSerializer(serializers.Serializer):
    """``POST /api/v1/auth/request-access`` request body.

    Rejects unknown fields per Requirement 18.2 (the view performs the
    actual extra-key check; this serializer is tight on its own field
    set).
    
    MVP-2: Supports both legacy (justification) and new (document upload) flows.
    """

    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=80, allow_blank=False)
    last_name = serializers.CharField(max_length=80, allow_blank=False)
    requested_role = serializers.CharField(max_length=16)
    
    # Legacy flow: justification field (now optional for backward compatibility)
    justification = serializers.CharField(
        min_length=10,
        max_length=2000,
        allow_blank=False,
        required=False,
    )
    
    # New flow: document upload (Student ID or COR)
    document = serializers.FileField(required=False)

    def validate_email(self, value: str) -> str:
        normalised = value.strip().lower()
        # Document-upload flow: require strict student-number format.
        # Legacy justification flow: accept any institutional email.
        # We check which flow based on the presence of the 'document' field
        # in initial_data (serializer not yet fully validated at this point).
        has_document = bool(self.initial_data.get('document'))
        if has_document:
            if not is_student_number_email(normalised):
                raise serializers.ValidationError(
                    'Use your PampangaStateU institutional email in the format '
                    'studentnumber@pampangastateu.edu.ph '
                    '(e.g. 2023123456@pampangastateu.edu.ph).',
                    code=INVALID_EMAIL_DOMAIN,
                )
        else:
            if not is_institutional_email(normalised):
                raise serializers.ValidationError(
                    'Institutional email is required (must end with pampangastateu.edu.ph).',
                    code=INVALID_EMAIL_DOMAIN,
                )
        return normalised

    def validate_requested_role(self, value: str) -> str:
        # The administrator role is intentionally NOT self-requestable
        # per Requirement 7.8; only student / faculty are valid.
        if value not in Role.ALLOWED_FOR_REQUEST:
            raise serializers.ValidationError(
                'Requested role must be student or faculty.',
                code='INVALID_REQUESTED_ROLE',
            )
        return value
    
    def validate_document(self, value):
        """Validate uploaded document (early checks before FileValidator)."""
        if not value:
            return value
        
        # Import here to avoid circular dependency
        from django.conf import settings
        
        # Check file size
        max_size = settings.IDENTITY_VERIFICATION['MAX_FILE_SIZE_MB'] * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File size must not exceed {settings.IDENTITY_VERIFICATION["MAX_FILE_SIZE_MB"]}MB.',
                code='FILE_TOO_LARGE',
            )
        
        # Check file extension
        from pathlib import Path
        ext = Path(value.name).suffix.lstrip('.').lower()
        allowed_exts = settings.IDENTITY_VERIFICATION['ALLOWED_EXTENSIONS']
        if ext not in allowed_exts:
            raise serializers.ValidationError(
                f'File type not allowed. Allowed types: {", ".join(allowed_exts)}.',
                code='FILE_TYPE_NOT_ALLOWED',
            )
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation: require either justification OR document."""
        justification = attrs.get('justification')
        document = attrs.get('document')
        
        # Must provide either justification (legacy) or document (new)
        if not justification and not document:
            raise serializers.ValidationError(
                'Either justification or document must be provided.',
                code='MISSING_REQUIRED_FIELD',
            )
        
        # Cannot provide both
        if justification and document:
            raise serializers.ValidationError(
                'Cannot provide both justification and document. Use document upload for new requests.',
                code='CONFLICTING_FIELDS',
            )
        
        return attrs


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------

class AccessRequestListItemSerializer(serializers.ModelSerializer):
    """Read-only shape returned by the admin list endpoint."""

    class Meta:
        model = AccessRequest
        fields = (
            'id', 'email', 'first_name', 'last_name', 'requested_role',
            'justification', 'status', 'review_note', 'reviewed_by',
            'reviewed_at', 'created_at',
        )
        read_only_fields = fields


class AdminApproveSerializer(serializers.Serializer):
    """``POST /admin/access-requests/{id}/approve`` body.

    The note is optional; when present it lands in ``review_note`` for
    audit purposes.
    """

    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')


class AdminDenySerializer(serializers.Serializer):
    """``POST /admin/access-requests/{id}/deny`` body.

    A reason is required so the denial email has actionable content for
    the requester.
    """

    reason = serializers.CharField(min_length=1, max_length=2000, allow_blank=False)
