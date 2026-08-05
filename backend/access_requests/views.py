"""HTTP views for the ``access_requests`` app.

Public surface:
* ``POST /api/v1/auth/request-access`` — unauthenticated submission.

Administrator surface (gated by ``IsAdministrator``):
* ``GET  /api/v1/admin/access-requests/``
* ``POST /api/v1/admin/access-requests/{id}/approve/``
* ``POST /api/v1/admin/access-requests/{id}/deny/``
"""

from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdministrator
from common.audit_logger import write as audit_write
from common.csrf import require_origin_match
from common.errors import make_error_response
from common.ratelimit import rate_limit_per_email, rate_limit_per_ip

logger = logging.getLogger(__name__)

from .email_verification import (
    EmailVerificationTokenInvalid,
    consume_email_verification_token,
    issue_email_verification_token,
)
from .models import AccessRequest
from .serializers import (
    AccessRequestListItemSerializer,
    AdminApproveSerializer,
    AdminDenySerializer,
    RequestAccessSerializer,
)
from .services import (
    AccessRequestEmailCollision,
    AccessRequestNotPending,
    approve_request,
    deny_request,
)


def _reject_unknown_fields(request, allowed: set):
    if not isinstance(request.data, dict):
        return None
    extra = set(request.data.keys()) - allowed
    if extra:
        return make_error_response(
            code='UNKNOWN_FIELD',
            message=f'Unknown field(s): {sorted(extra)}',
            status=status.HTTP_400_BAD_REQUEST,
            details={'unknown': sorted(extra)},
        )
    return None


def _hoist_first_field_error(errors: dict) -> tuple[str, str]:
    """Return (code, message) for the first field-level error in DRF errors."""
    for field, errs in errors.items():
        if not errs:
            continue
        first = errs[0]
        code = getattr(first, 'code', 'VALIDATION_ERROR')
        return str(code).upper(), str(first)
    return 'VALIDATION_ERROR', 'Request payload is invalid.'


# ---------------------------------------------------------------------------
# Public submission — POST /api/v1/auth/request-access/
# ---------------------------------------------------------------------------

@method_decorator(require_origin_match, name='post')
class RequestAccessView(APIView):
    """Public submission of an access request."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    
    # Add parser classes to support both JSON and multipart/form-data
    from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @rate_limit_per_ip(limit=5, window_seconds=3600, error_code='RATE_LIMITED_REQUEST_ACCESS')
    @rate_limit_per_email(limit=3, window_seconds=86400, error_code='RATE_LIMITED_REQUEST_ACCESS')
    def post(self, request, *args, **kwargs):
        # Check if this is a document upload (new flow) or justification (legacy flow)
        has_document = 'document' in request.data
        has_justification = 'justification' in request.data
        
        # Determine allowed fields based on flow
        if has_document:
            allowed_fields = {'email', 'first_name', 'last_name', 'requested_role', 'document'}
        else:
            allowed_fields = {'email', 'first_name', 'last_name', 'requested_role', 'justification'}
        
        unknown = _reject_unknown_fields(request, allowed=allowed_fields)
        if unknown is not None:
            return unknown

        serializer = RequestAccessSerializer(data=request.data)
        if not serializer.is_valid():
            code, message = _hoist_first_field_error(serializer.errors)
            return make_error_response(
                code=code, message=message, status=status.HTTP_400_BAD_REQUEST,
            )

        v = serializer.validated_data
        email = v['email']

        # Pre-check: email already belongs to an active user → 409.
        if User.objects.filter(email=email, is_active=True).exists():
            return make_error_response(
                code='EMAIL_ALREADY_REGISTERED',
                message='An account already exists for this email.',
                status=status.HTTP_409_CONFLICT,
            )

        # Pre-check: a pending request for this email already exists → 409.
        # The DB partial-unique index also enforces this at INSERT time, but
        # we surface a clean error before hitting it.
        if AccessRequest.objects.filter(email=email, status='pending').exists():
            return make_error_response(
                code='DUPLICATE_REQUEST_PENDING',
                message='A request for this email is already pending review.',
                status=status.HTTP_409_CONFLICT,
            )

        # Branch: new verification flow vs legacy justification flow
        if has_document:
            return self._handle_document_upload(request, v)
        else:
            return self._handle_legacy_justification(request, v)
    
    def _handle_legacy_justification(self, request, validated_data):
        """Handle legacy justification-based access request (unchanged)."""
        email = validated_data['email']
        
        try:
            req = AccessRequest.objects.create(
                email=email,
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                requested_role=validated_data['requested_role'],
                justification=validated_data['justification'],
                status='pending',
            )
        except IntegrityError:
            # Race: another concurrent submission won the partial-unique race.
            return make_error_response(
                code='DUPLICATE_REQUEST_PENDING',
                message='A request for this email is already pending review.',
                status=status.HTTP_409_CONFLICT,
            )

        audit_write(
            'auth.access_request.submitted',
            actor=None,
            target=None,
            success=True,
            metadata={
                'access_request_id': str(req.id),
                'email': email,
                'requested_role': req.requested_role,
                'flow': 'legacy_justification',
            },
            request=request,
        )

        return Response(
            {
                'status': 'pending',
                'submitted_at': req.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
    
    def _handle_document_upload(self, request, validated_data):
        """Handle new document upload verification flow (Tasks 5.3-5.9)."""
        import hashlib
        import os
        from pathlib import Path
        from django.conf import settings
        from identity_verification.models import VerificationDocument
        from identity_verification.services.orchestrator import VerificationOrchestrator
        from identity_verification.validators.file_validator import FileValidator
        
        email = validated_data['email']
        document = validated_data['document']
        
        # Task 5.3: Early file validation with FileValidator
        file_validator = FileValidator()
        validation_result = file_validator.validate(document)
        
        if not validation_result.is_valid:
            # Return first error
            error_msg = validation_result.errors[0] if validation_result.errors else 'File validation failed'
            return make_error_response(
                code='FILE_VALIDATION_FAILED',
                message=error_msg,
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Task 5.3: Create AccessRequest with status='processing'
        try:
            req = AccessRequest.objects.create(
                email=email,
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                requested_role=validated_data['requested_role'],
                justification=None,  # No justification for document flow
                status='processing',
            )
        except IntegrityError:
            # Race: another concurrent submission won the partial-unique race.
            return make_error_response(
                code='DUPLICATE_REQUEST_PENDING',
                message='A request for this email is already pending review.',
                status=status.HTTP_409_CONFLICT,
            )
        
        try:
            # Task 5.4: Compute SHA256 hash of file contents
            document.seek(0)  # Reset file pointer
            file_contents = document.read()
            sha256_hash = hashlib.sha256(file_contents).hexdigest()
            
            # Task 5.4: Generate file path and save to private storage
            # Path: MEDIA_ROOT/private/verification_docs/{uuid}/{sha256}.{ext}
            file_ext = Path(document.name).suffix.lstrip('.')
            if not file_ext:
                file_ext = 'bin'
            
            private_root = Path(settings.MEDIA_ROOT) / 'private' / 'verification_docs'
            request_dir = private_root / str(req.id)
            request_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = request_dir / f'{sha256_hash}.{file_ext}'
            
            # Write file to disk
            with open(file_path, 'wb') as f:
                f.write(file_contents)
            
            # Ensure directory permissions are secure (not publicly accessible)
            os.chmod(request_dir, 0o700)
            
            # Task 5.5: Create VerificationDocument row
            verification_doc = VerificationDocument.objects.create(
                access_request=req,
                file_path=str(file_path),
                mime_type=validation_result.detected_mime,
                sha256=sha256_hash,
                size_bytes=len(file_contents),
            )
            
            # Step 5.6: Run verification pipeline inline (synchronous)
            orchestrator = VerificationOrchestrator()

            try:
                verification_result = orchestrator.verify_request(str(req.id))

                # Step 5.9: Route based on decision
                if verification_result.status == 'auto_approved':
                    # CASE 1 — Clean valid request:
                    # Send email verification; do NOT create the account yet.
                    # The applicant must click the link to activate their account.
                    try:
                        issue_email_verification_token(req, request=request)
                    except Exception as email_exc:
                        logger.warning(
                            'Email verification send failed for %s: %s',
                            email, email_exc,
                        )
                        # Fall back to manual review if email sending fails
                        req.status = 'pending'
                        req.save(update_fields=['status'])

                elif verification_result.status == 'pending_manual_review':
                    # CASE 2 — Partial/unclear: already set to 'pending' by orchestrator
                    pass

                elif verification_result.status == 'rejected':
                    # CASE 3 — Invalid: already set to 'denied' by orchestrator
                    pass

            except Exception as e:
                # Pipeline error: write error result, fall back to manual review
                from identity_verification.models import VerificationResult

                verification_result, created = VerificationResult.objects.get_or_create(
                    access_request=req,
                    defaults={
                        'status': 'error',
                        'decision_reason': f'Pipeline error: {str(e)}',
                        'processor_version': 'mvp-1.0',
                    }
                )

                if not created:
                    verification_result.status = 'error'
                    verification_result.decision_reason = f'Pipeline error: {str(e)}'
                    verification_result.save()

                req.status = 'pending'
                req.save(update_fields=['status'])

                audit_write(
                    'access_request.verification.error',
                    actor=None,
                    target=None,
                    success=False,
                    metadata={
                        'access_request_id': str(req.id),
                        'email': email,
                        'error': str(e),
                        'exception_class': type(e).__name__,
                    },
                    request=request,
                )
            
            # Audit: Log submission
            audit_write(
                'auth.access_request.submitted',
                actor=None,
                target=None,
                success=True,
                metadata={
                    'access_request_id': str(req.id),
                    'email': email,
                    'requested_role': req.requested_role,
                    'flow': 'document_verification',
                    'document_sha256': sha256_hash,
                },
                request=request,
            )

            # Refresh to get latest status
            req.refresh_from_db()

            # Map internal status to a frontend-friendly decision key
            _STATUS_TO_DECISION = {
                'pending_email_verification': 'pending_email_verification',
                'pending': 'pending_manual_review',
                'denied': 'rejected',
                'approved': 'approved',
            }
            decision = _STATUS_TO_DECISION.get(req.status, 'pending_manual_review')

            return Response(
                {
                    'status': req.status,
                    'decision': decision,
                    'submitted_at': req.created_at.isoformat(),
                },
                status=status.HTTP_202_ACCEPTED,
            )
        
        except Exception as e:
            # Cleanup: delete the AccessRequest if something went wrong
            req.delete()
            raise


# ---------------------------------------------------------------------------
# Email verification — GET /api/v1/auth/verify-email/?token=<plaintext>
# ---------------------------------------------------------------------------

class VerifyEmailView(APIView):
    """Consume an email verification token and activate the user account.

    Called when the applicant clicks the link in their verification email.
    On success, ``approve_request(..., send_email=False)`` creates the User
    and issues a setup-password token WITHOUT emailing it — the plaintext
    is returned as ``setup_token`` so the frontend can let the user set
    their password inline on this same page, eliminating the second email.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        token = (request.query_params.get('token') or '').strip()
        if not token:
            return make_error_response(
                code='MISSING_TOKEN',
                message='Verification token is required.',
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outcome = consume_email_verification_token(token, request=request)
        except EmailVerificationTokenInvalid as exc:
            _reason_map = {
                'not_found':   ('TOKEN_INVALID', 'Verification link is invalid or has already been used.'),
                'already_used': ('TOKEN_ALREADY_USED', 'This verification link has already been used.'),
                'expired':     ('TOKEN_EXPIRED', 'Verification link has expired. Please submit a new access request.'),
                'request_not_awaiting_verification': (
                    'REQUEST_NOT_PENDING_VERIFICATION',
                    'This access request is not awaiting email verification.',
                ),
            }
            code, message = _reason_map.get(
                exc.reason,
                ('TOKEN_INVALID', 'Verification link is invalid.'),
            )
            return make_error_response(
                code=code, message=message, status=status.HTTP_400_BAD_REQUEST,
            )
        except AccessRequestEmailCollision:
            return make_error_response(
                code='EMAIL_ALREADY_REGISTERED',
                message='An account for this email already exists.',
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                'verified': True,
                'email': outcome.user.email,
                'setup_token': outcome.reset_token_plaintext,
                'message': 'Email verified. Set your password to activate your account.',
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Admin views — /api/v1/admin/access-requests/...
# ---------------------------------------------------------------------------

class _AdminAccessRequestPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AccessRequestListView(APIView):
    """``GET /api/v1/admin/access-requests/?status=pending&page=...&page_size=...``"""

    permission_classes = [IsAdministrator]

    def get(self, request, *args, **kwargs):
        qs = AccessRequest.objects.all().order_by('-created_at')

        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter not in ('pending', 'approved', 'denied'):
                return make_error_response(
                    code='INVALID_STATUS_FILTER',
                    message='status must be one of: pending, approved, denied.',
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)

        paginator = _AdminAccessRequestPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = AccessRequestListItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


def _resolve_request(id_str: str) -> AccessRequest:
    """Look up an AccessRequest by UUID; raise NotFound on miss."""
    try:
        uid = uuid.UUID(str(id_str))
    except (ValueError, TypeError):
        raise NotFound(detail='Access request not found.')
    try:
        return AccessRequest.objects.get(pk=uid)
    except AccessRequest.DoesNotExist:
        raise NotFound(detail='Access request not found.')


class ApproveAccessRequestView(APIView):
    """``POST /api/v1/admin/access-requests/{id}/approve/``"""

    permission_classes = [IsAdministrator]

    def post(self, request, id, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'note'})
        if unknown is not None:
            return unknown

        serializer = AdminApproveSerializer(data=request.data or {})
        is_valid = serializer.is_valid(raise_exception=False)
        note = serializer.validated_data.get('note', '') if is_valid else ''

        req = _resolve_request(id)

        try:
            outcome = approve_request(req, reviewer=request.user, note=note, request=request)
        except AccessRequestNotPending:
            return make_error_response(
                code='NOT_PENDING',
                message=f'Access request is not pending (current status: {req.status}).',
                status=status.HTTP_409_CONFLICT,
            )
        except AccessRequestEmailCollision:
            return make_error_response(
                code='EMAIL_ALREADY_REGISTERED',
                message='An account for this email already exists.',
                status=status.HTTP_409_CONFLICT,
            )

        body = AccessRequestListItemSerializer(outcome.request).data
        return Response(body, status=status.HTTP_200_OK)


class DenyAccessRequestView(APIView):
    """``POST /api/v1/admin/access-requests/{id}/deny/``"""

    permission_classes = [IsAdministrator]

    def post(self, request, id, *args, **kwargs):
        unknown = _reject_unknown_fields(request, allowed={'reason'})
        if unknown is not None:
            return unknown

        serializer = AdminDenySerializer(data=request.data or {})
        if not serializer.is_valid():
            code, message = _hoist_first_field_error(serializer.errors)
            return make_error_response(
                code=code, message=message, status=status.HTTP_400_BAD_REQUEST,
            )

        reason = serializer.validated_data['reason']
        req = _resolve_request(id)

        try:
            outcome = deny_request(req, reviewer=request.user, reason=reason, request=request)
        except AccessRequestNotPending:
            return make_error_response(
                code='NOT_PENDING',
                message=f'Access request is not pending (current status: {req.status}).',
                status=status.HTTP_409_CONFLICT,
            )

        body = AccessRequestListItemSerializer(outcome.request).data
        return Response(body, status=status.HTTP_200_OK)
