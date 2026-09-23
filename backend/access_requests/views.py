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
from common.ratelimit import (
    _client_ip,
    _hit_and_check,
    rate_limit_per_email,
    rate_limit_per_ip,
)
from common.tokens.opaque import sha256

logger = logging.getLogger(__name__)

from .email_verification import (
    EmailVerificationTokenInvalid,
    consume_email_verification_token,
    issue_email_verification_token,
)
from password_reset.services import issue_reset_token

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


# ---------------------------------------------------------------------------
# Rate limiting for the claim-status poll
# ---------------------------------------------------------------------------
#
# WHY THESE ARE LOCAL instead of common.ratelimit's decorators:
#
#   1. `rate_limit_per_token` reads the token from `request.data['token']` /
#      `request.POST`. The claim arrives as a QUERY PARAM on a GET, so that
#      decorator would pass through without limiting anything at all.
#
#   2. More importantly, `common.ratelimit._get_debug_limits` clamps EVERY
#      requested limit down to 20 requests/60s whenever `settings.DEBUG` is
#      true — and DEBUG is true in dev AND under pytest. This endpoint is
#      polled ~15x/minute by design, so a 20/min ceiling would leave almost
#      no headroom locally and would throttle the feature the moment a user
#      had two tabs open or reloaded the page.
#
# The cache bucket semantics are NOT reimplemented: `_hit_and_check` is reused
# verbatim, so the TTL-anchoring, `cache.add`/`incr` race handling and backend
# are identical to every other limiter in the codebase. Only the DEBUG clamp
# is skipped, deliberately.
#
# CHOSEN LIMITS
#
#   Per claim — 60 / 60s. The frontend polls every ~4s (15/min) for up to
#   CLAIM_TTL_SECONDS. 60/min is 4x that cadence, which absorbs a reload, a
#   second tab, or a later decision to tighten the poll interval, while still
#   capping a single claim at one request/second. A naive reset-password-style
#   5-per-15-minutes would break the feature on its 6th poll, ~20 seconds in.
#
#   Per IP — 300 / 60s. Guards against enumeration across many guessed claims
#   and against one host hammering the DB. Deliberately well above the
#   per-claim limit: a shared campus NAT can legitimately carry several
#   applicants polling at once, and throttling them collectively would be a
#   self-inflicted outage. (Guessing a claim is infeasible regardless — it is
#   a 256-bit opaque token — so this limit is about load, not secrecy.)

CLAIM_STATUS_PER_CLAIM_LIMIT = 60
CLAIM_STATUS_PER_CLAIM_WINDOW = 60
CLAIM_STATUS_PER_IP_LIMIT = 300
CLAIM_STATUS_PER_IP_WINDOW = 60


def _rate_limit_claim_status(request, claim: str):
    """Apply the per-claim and per-IP budgets. Returns a 429 response or None."""
    ip = _client_ip(request)
    ip_key = f'ratelimit:ip:claim-status:{ip}'
    allowed, retry = _hit_and_check(
        ip_key, CLAIM_STATUS_PER_IP_LIMIT, CLAIM_STATUS_PER_IP_WINDOW,
    )
    if not allowed:
        return make_error_response(
            code='RATE_LIMITED_CLAIM_STATUS',
            message='Too many requests. Please try again later.',
            status=429,
            retry_after_seconds=retry,
        )

    if claim:
        # Key on the hash, never the plaintext — the cache is not a secret store.
        claim_key = f'ratelimit:claim:claim-status:{sha256(claim)[:32]}'
        allowed, retry = _hit_and_check(
            claim_key, CLAIM_STATUS_PER_CLAIM_LIMIT, CLAIM_STATUS_PER_CLAIM_WINDOW,
        )
        if not allowed:
            return make_error_response(
                code='RATE_LIMITED_CLAIM_STATUS',
                message='Too many requests. Please try again later.',
                status=429,
                retry_after_seconds=retry,
            )
    return None


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
        
        req = AccessRequest(
            email=email,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            requested_role=validated_data['requested_role'],
            justification=validated_data['justification'],
            status='pending',
        )
        # Minted before the INSERT so the hash lands in the same write.
        claim_plaintext = req.issue_claim_token()
        try:
            req.save()
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
                # Additive. The claim plaintext is returned here and NOWHERE
                # else, ever — only its hash is stored. Expiry is an absolute
                # timestamp, not a duration, so CLAIM_TTL_SECONDS can change
                # server-side without the frontend drifting out of sync.
                'claim': claim_plaintext,
                'claim_expires_at': req.claim_expires_at.isoformat(),
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
        req = AccessRequest(
            email=email,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            requested_role=validated_data['requested_role'],
            justification=None,  # No justification for document flow
            status='processing',
        )
        # Minted before the INSERT so the hash lands in the same write. This is
        # the flow the claim actually matters for: it can reach
        # 'pending_email_verification', which is what polling waits on.
        claim_plaintext = req.issue_claim_token()
        try:
            req.save()
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
                    # Additive — see the legacy branch for the full rationale.
                    'claim': claim_plaintext,
                    'claim_expires_at': req.claim_expires_at.isoformat(),
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
    ``approve_request(..., send_email=False)`` creates the User and marks the
    request approved.

    This endpoint is a CONFIRMATION RECEIPT ONLY. It does not hand back a
    password-setup credential, because the tab holding the emailed link is not
    the tab that sets the password:

      * The tab that SUBMITTED the request polls
        ``GET /auth/request-access/status/`` and hosts the password form. That
        endpoint mints its own fresh setup token when it reports ``verified``.
      * Anyone without that tab open uses ``POST /auth/forgot-password/``,
        which issues a working setup link for a verified user whose password
        is still NULL.

    SECURITY NOTE — why ``setup_token`` was removed from this response: a
    password-setup credential no longer travels to a tab that has no use for
    it. The emailed link proves control of the address; that is all it needs
    to do. Narrowing its blast radius means a leaked or shoulder-surfed
    verification URL cannot itself be redeemed for a password.

    ``approve_request`` still issues a reset token internally — it is simply
    not surfaced here. That is deliberate and not worth refactoring.
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

        # No ``setup_token`` here — see the class docstring. The polling status
        # endpoint mints its own, and forgot-password covers everyone else.
        # ``message`` is updated to match: telling this tab to "set your
        # password" would be a false instruction, since it no longer can.
        return Response(
            {
                'verified': True,
                'email': outcome.user.email,
                'message': (
                    'Email verified. Return to the tab where you started to '
                    'set your password.'
                ),
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Claim status — GET /api/v1/auth/request-access/status/?claim=<plaintext>
# ---------------------------------------------------------------------------

class RequestAccessStatusView(APIView):
    """Report whether a submitted request's email has been verified yet.

    Polled by the tab that SUBMITTED the request, which holds the claim
    plaintext in memory. That tab never sees the emailed link, so it has no
    other way to learn the outcome.

    WHY THIS MINTS A FRESH TOKEN RATHER THAN RETURNING AN EXISTING ONE
    ------------------------------------------------------------------
    Password-setup tokens are stored as SHA-256 hashes. The plaintext issued
    during email verification exists only in memory during that one request
    and is handed to the verifying tab. It is unrecoverable afterwards — so
    "look up the token that was already issued and return it" is not a thing
    that can be built. On the ``verified`` branch this endpoint therefore
    mints a NEW setup token, via the same
    ``password_reset.services.issue_reset_token`` that forgot-password and
    ``approve_request`` already call.

    Consequence, and it is intentional: polling twice yields two valid tokens,
    and the LATEST one is the one the frontend should use. That is what makes
    a browser reload survivable — the reloaded tab simply polls again and gets
    a working token instead of being stranded.

    Responses (all 200 unless noted):
        {"status": "pending_verification"}            not yet verified
        {"status": "verified", "setup_token": "..."}   verified, password unset
        {"status": "already_active"}                   password already set
        {"status": "expired"}                          claim window closed
        404                                            unknown / malformed claim
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        claim = (request.query_params.get('claim') or '').strip()

        limited = _rate_limit_claim_status(request, claim)
        if limited is not None:
            return limited

        if not claim:
            return self._not_found()

        try:
            req = AccessRequest.objects.get(claim_token_hash=sha256(claim))
        except AccessRequest.DoesNotExist:
            # Same response whether the claim never existed, was malformed, or
            # was issued and later purged. Distinguishing them would confirm to
            # an attacker that a given claim was once real.
            return self._not_found()

        if req.claim_is_expired():
            # No token is minted on this branch — an expired claim must not be
            # able to produce password-setup credentials.
            return Response({'status': 'expired'}, status=status.HTTP_200_OK)

        # 'approved' is the terminal state that email verification drives the
        # request to (via consume_email_verification_token -> approve_request).
        # Anything else means the applicant has not clicked the link yet.
        if req.status != 'approved':
            return Response(
                {'status': 'pending_verification'}, status=status.HTTP_200_OK,
            )

        user = User.objects.filter(email=req.email).first()
        if user is None:
            # Defensive: 'approved' without a User should be impossible, since
            # approve_request creates both in one transaction. Report it as
            # not-yet-verified rather than 500ing at a polling client.
            logger.warning(
                'Access request %s is approved but has no user row; '
                'reporting pending_verification to the claim poller.',
                req.id,
            )
            return Response(
                {'status': 'pending_verification'}, status=status.HTTP_200_OK,
            )

        # THE STUB'S EXPIRY IN PRACTICE: once a password exists the account is
        # live, so this refuses to mint. Chosen over expiring the stub inside
        # the setup-password path because it keeps the whole mechanism inside
        # this app — password_reset has no knowledge of claims and shouldn't
        # acquire any. A stale tab left open past signup gets 'already_active'
        # and the frontend sends that user to sign-in.
        if user.password:
            return Response(
                {'status': 'already_active'}, status=status.HTTP_200_OK,
            )

        issued = issue_reset_token(
            user,
            template='account_activation',
            request=request,
            send_email=False,
        )

        audit_write(
            'auth.access_request.claim_setup_token_issued',
            actor=None,
            target=user,
            success=True,
            metadata={
                'access_request_id': str(req.id),
                'reset_token_id': str(issued.row.id),
            },
            request=request,
        )

        return Response(
            {'status': 'verified', 'setup_token': issued.plaintext},
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _not_found():
        return make_error_response(
            code='CLAIM_NOT_FOUND',
            message='This claim is not valid.',
            status=status.HTTP_404_NOT_FOUND,
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
