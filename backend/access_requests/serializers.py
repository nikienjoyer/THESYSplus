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
    
    The role picks the branch: students upload a Student ID or COR and use
    a student-number email; faculty send no document and use a
    non-numeric PampangaStateU email, then wait for an administrator.
    """

    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=80, allow_blank=False)
    last_name = serializers.CharField(max_length=80, allow_blank=False)
    requested_role = serializers.CharField(max_length=16)

    # Students only (the view rejects it for faculty as an unknown field).
    document = serializers.FileField(required=False)

    def validate_email(self, value: str) -> str:
        normalised = value.strip().lower()
        # Field validators run before validate(), so read the role from the
        # raw input; an invalid role fails on its own field.
        if self.initial_data.get('requested_role') == 'faculty':
            if not is_institutional_email(normalised):
                raise serializers.ValidationError(
                    'Use your PampangaStateU email '
                    '(e.g. firstname.lastname@pampangastateu.edu.ph).',
                    code=INVALID_EMAIL_DOMAIN,
                )
            if is_student_number_email(normalised):
                raise serializers.ValidationError(
                    'This looks like a student email. Request access as a Student instead.',
                    code='FACULTY_EMAIL_LOOKS_LIKE_STUDENT',
                )
        elif not is_student_number_email(normalised):
            raise serializers.ValidationError(
                'Use your PampangaStateU institutional email in the format '
                'studentnumber@pampangastateu.edu.ph '
                '(e.g. 2024000000@pampangastateu.edu.ph).',
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
        if attrs['requested_role'] == 'student' and not attrs.get('document'):
            raise serializers.ValidationError(
                {'document': serializers.ErrorDetail(
                    'Please upload your PampangaStateU Student ID or COR.',
                    code='DOCUMENT_REQUIRED',
                )},
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
