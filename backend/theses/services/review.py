"""Thesis review decisions, shared by the Django admin and the review API.

Both paths record a status change the same way: stamp who decided and when,
repair a missing embedding on approval, write one audit row, and email the
uploader. Keeping it here means the admin change form and
``POST /theses/<id>/review/`` cannot drift apart.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common import audit_logger
from common.email_backend import default_email_backend

from ..models import EmbeddingStatus, Thesis, ThesisStatus

logger = logging.getLogger(__name__)

# Destination status → audit event type.
EVENT_FOR_STATUS = {
    ThesisStatus.APPROVED: 'thesis.review.approved',
    ThesisStatus.REJECTED: 'thesis.review.rejected',
    ThesisStatus.PENDING_REVIEW: 'thesis.review.reopened',
}

TERMINAL_STATUSES = (ThesisStatus.APPROVED, ThesisStatus.REJECTED)


class ThesisNotPending(Exception):
    """The thesis was already decided, so the API will not review it again."""


def stamp_reviewer(thesis: Thesis, previous_status, reviewer) -> None:
    """Set or clear review provenance for a status change, before saving.

    A terminal status stamps the reviewer and time; returning to pending
    clears both. No change in status touches nothing.
    """
    if thesis.status == previous_status:
        return
    if thesis.status in TERMINAL_STATUSES:
        thesis.reviewed_by = reviewer
        thesis.reviewed_at = timezone.now()
    elif thesis.status == ThesisStatus.PENDING_REVIEW:
        thesis.reviewed_by = None
        thesis.reviewed_at = None


def record_transition(thesis: Thesis, previous_status, *, actor, request=None, created=False):
    """Follow up a saved status change.

    Returns the embedding repair outcome so the caller can tell the reviewer:
    ``None`` when no repair was needed, ``True`` when it succeeded, ``False``
    when it failed. Neither a failed repair nor a failed email undoes the
    decision; both are independent of it.
    """
    embedded = None
    if thesis.status == ThesisStatus.APPROVED and thesis.embedding_status != EmbeddingStatus.READY:
        embedded = _repair_embedding(thesis)

    metadata = {
        'thesis_id': str(thesis.id),
        'title': (thesis.title or '')[:200],
        'previous_status': previous_status,
        'new_status': thesis.status,
        'program': thesis.program,
        'year': thesis.year,
        'created': created,
    }
    if thesis.status == ThesisStatus.REJECTED:
        metadata['rejection_reason'] = (thesis.rejection_reason or '')[:500]

    # audit_logger.write swallows and logs its own failures.
    audit_logger.write(
        EVENT_FOR_STATUS.get(thesis.status, 'thesis.review.reopened'),
        actor=actor,
        target=thesis.uploaded_by,
        success=True,
        metadata=metadata,
        request=request,
    )

    # A record an administrator creates already decided is not a submission
    # anyone is waiting on, so only an existing thesis's decision is emailed.
    if not created:
        _notify_uploader(thesis)
    return embedded


def review_pending_thesis(thesis_id, *, decision: str, reason: str, actor, request=None):
    """Approve or reject a pending thesis for the review API.

    Raises ``Thesis.DoesNotExist`` for an unknown id and ``ThesisNotPending``
    when the thesis was already decided. Returns ``(thesis, embedded)``.
    """
    with transaction.atomic():
        thesis = Thesis.objects.select_for_update().get(pk=thesis_id)
        if thesis.status != ThesisStatus.PENDING_REVIEW:
            raise ThesisNotPending(thesis.status)
        previous_status = thesis.status
        if decision == 'approve':
            thesis.status = ThesisStatus.APPROVED
            thesis.rejection_reason = ''
        else:
            thesis.status = ThesisStatus.REJECTED
            thesis.rejection_reason = reason
        stamp_reviewer(thesis, previous_status, actor)
        thesis.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])

    embedded = record_transition(thesis, previous_status, actor=actor, request=request)
    return thesis, embedded


def _repair_embedding(thesis: Thesis) -> bool:
    """Regenerate a missing embedding so an approved thesis is searchable."""
    from .semantic_search import generate_thesis_embedding, generate_title_embedding

    try:
        generate_thesis_embedding(thesis)
        generate_title_embedding(thesis)
        return True
    except Exception as exc:
        logger.warning('Embedding retry failed for thesis %s: %s', thesis.id, exc)
        return False


def _notify_uploader(thesis: Thesis) -> None:
    """Email the uploader an approval or a rejection with its reason."""
    if thesis.status not in TERMINAL_STATUSES:
        return
    uploader = thesis.uploaded_by
    if not uploader or not uploader.email:
        return

    approved = thesis.status == ThesisStatus.APPROVED
    base = settings.FRONTEND_BASE_URL.rstrip('/')
    try:
        default_email_backend().send(
            to=uploader.email,
            subject='Your thesis was approved' if approved else 'Your thesis was not approved',
            template_name='thesis_approved' if approved else 'thesis_rejected',
            context={
                'first_name': uploader.first_name,
                'title': thesis.title,
                'reason': thesis.rejection_reason,
                'thesis_url': f'{base}/repository/{thesis.id}',
            },
        )
    except Exception as exc:
        logger.error('Thesis decision email failed for %s: %s', uploader.email, exc)
