"""Public service functions for the ``access_requests`` app.

Encapsulates the atomic admin approve / deny pipelines per design §6.2.
The approve flow creates a User with ``password_hash=None``, issues a
reset token via the password_reset service, and sends the activation
email — all within a single transaction so a failure rolls back every
side effect on the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from common.audit_logger import write as audit_write
from common.email_backend import default_email_backend
from password_reset.services import issue_reset_token

from .models import AccessRequest

logger = logging.getLogger('access_requests')


class AccessRequestNotPending(Exception):
    """Raised when an approve/deny call targets a request whose status != pending."""


class AccessRequestEmailCollision(Exception):
    """Raised when approval can't create the user because the email already exists."""


@dataclass
class ApprovalOutcome:
    request: AccessRequest
    user: User
    reset_token_id: str


def approve_request(req: AccessRequest, *, reviewer: User | None, note: str = '', request=None) -> ApprovalOutcome:
    """Atomically approve ``req`` per design §6.2.

    Steps inside ``transaction.atomic()``:
    1. ``SELECT FOR UPDATE`` on ``req`` so concurrent approvals serialise.
    2. Assert ``status == 'pending'`` or ``status == 'processing'`` (otherwise raise AccessRequestNotPending).
    3. Create the User (``password_hash=None``, ``is_active=True``,
       ``is_email_verified=False``, role from ``req.requested_role``).
    4. Stamp ``status='approved'``, ``review_note``, ``reviewed_by``,
       ``reviewed_at``.
    5. Issue a reset token via ``password_reset.services.issue_reset_token``
       with template ``account_activation`` so the user lands on the
       set-password flow.

    Audit row is written outside the transaction so a write failure can't
    rollback the user creation.
    
    Args:
        req: AccessRequest to approve
        reviewer: User who approved (or None for system-initiated approval)
        note: Optional review note
        request: HTTP request for audit logging
    """
    with transaction.atomic():
        try:
            row = AccessRequest.objects.select_for_update().get(pk=req.pk)
        except AccessRequest.DoesNotExist:
            raise AccessRequestNotPending('not found')

        if row.status not in ('pending', 'processing'):
            raise AccessRequestNotPending(row.status)

        try:
            user = User.objects.create_user(
                email=row.email,
                first_name=row.first_name,
                last_name=row.last_name,
                role=row.requested_role,
                password=None,  # NULL until first password-set per Requirement 5.7
            )
            user.is_active = True
            user.is_email_verified = False
            user.save(update_fields=['is_active', 'is_email_verified', 'updated_at'])
        except IntegrityError as exc:
            # Race: another administrator approved a request for the same
            # email, or a user was created out-of-band between the request
            # submission and this approval.
            raise AccessRequestEmailCollision('email already registered') from exc

        row.status = 'approved'
        row.review_note = note or ''
        row.reviewed_by = reviewer
        row.reviewed_at = timezone.now()
        row.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])

        # Issue activation token + send email INSIDE the transaction so
        # a backend send failure doesn't orphan a half-provisioned user.
        # ``issue_reset_token`` is itself transactional and writes the
        # reset row; the console email backend never raises.
        issued = issue_reset_token(user, template='account_activation', request=request)

    audit_write(
        'auth.access_request.approved',
        actor=reviewer,
        target=user,
        success=True,
        metadata={
            'access_request_id': str(row.id),
            'provisioned_user_id': str(user.id),
            'reset_token_id': str(issued.row.id),
            'role': user.role,
            'approval_type': 'system_auto' if reviewer is None else 'manual',
        },
        request=request,
    )

    return ApprovalOutcome(request=row, user=user, reset_token_id=str(issued.row.id))


@dataclass
class DenialOutcome:
    request: AccessRequest


def deny_request(req: AccessRequest, *, reviewer: User, reason: str, request=None) -> DenialOutcome:
    """Atomically deny ``req`` per design §6.2.

    Steps inside ``transaction.atomic()``:
    1. ``SELECT FOR UPDATE`` on ``req``.
    2. Assert ``status == 'pending'``.
    3. Stamp ``status='denied'``, ``review_note=reason``, ``reviewed_by``,
       ``reviewed_at``.

    The denial email is sent OUTSIDE the transaction (a delivery failure
    shouldn't rollback the denial); failures are logged but never raise.
    """
    with transaction.atomic():
        try:
            row = AccessRequest.objects.select_for_update().get(pk=req.pk)
        except AccessRequest.DoesNotExist:
            raise AccessRequestNotPending('not found')

        if row.status != 'pending':
            raise AccessRequestNotPending(row.status)

        row.status = 'denied'
        row.review_note = reason
        row.reviewed_by = reviewer
        row.reviewed_at = timezone.now()
        row.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])

    # Send denial notification AFTER the row is committed.
    try:
        backend = default_email_backend()
        backend.send(
            to=row.email,
            subject='Your THESYS+ access request',
            template_name='access_request_denied',
            context={
                'first_name': row.first_name,
                'last_name': row.last_name,
                'email': row.email,
                'reason': reason,
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error('denial email failed for %s: %s', row.email, exc)

    audit_write(
        'auth.access_request.denied',
        actor=reviewer,
        target=None,
        success=True,
        metadata={
            'access_request_id': str(row.id),
            'email': row.email,
            'reason': reason[:200],
        },
        request=request,
    )

    return DenialOutcome(request=row)
