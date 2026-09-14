"""Django Admin configuration for Thesis model.

Review policy enforced here
---------------------------
Every status change goes through the per-object change form. There are no
bulk actions: ``actions = None`` removes the three former status actions
*and* Django's built-in ``delete_selected``, so a single admin request can
never mutate more than one manuscript. Per-object delete is untouched.

Each real status transition is stamped with review provenance and written to
the append-only audit log exactly once. The reviewer also sees an advisory
redundancy signal — computed from precomputed title embeddings, never from a
live encode on the render path.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.main import ChangeList
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from common import audit_logger

from .models import EmbeddingStatus, Thesis, ThesisStatus
from .services.redundancy import (
    LABEL_CLEAN,
    LABEL_HIGH,
    LABEL_MODERATE,
    REASON_DIMENSION_MISMATCH,
    REASON_MATH_UNAVAILABLE,
    REASON_MISSING_EMBEDDING,
    advisory_for,
    analyze_titles,
)

logger = logging.getLogger(__name__)

# Per-request stash of the current page's redundancy map, populated once by
# _RedundancyChangeList. Kept for introspection; the render path reads the
# per-instance annotation below.
_STASH_ATTR = '_thesis_redundancy'

# Per-instance annotation carrying one row's RedundancyResult.
_RESULT_ATTR = '_redundancy_result'

# Distinguishes "no batch ran" from "the batch produced None for this row".
_MISSING = object()

# Badge palette — deliberately the same values status_badge uses, so the two
# columns read as one visual language.
_OVERLAP_COLORS = {
    LABEL_HIGH: '#DC3545',      # Red
    LABEL_MODERATE: '#FFA500',  # Orange
    LABEL_CLEAN: '#28A745',     # Green
}
_NOT_COMPUTED_COLOR = '#6C757D'  # Grey

_BADGE_TEMPLATE = (
    '<span style="background-color: {}; color: white; padding: 3px 10px; '
    'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>'
)

# Human-readable form of each machine reason code. Admin-owned constants —
# no Thesis field value ever reaches these strings.
_REASON_TEXT = {
    REASON_MISSING_EMBEDDING: 'No title embedding is stored for this thesis yet.',
    REASON_DIMENSION_MISMATCH: 'The stored title embedding has an unexpected size.',
    REASON_MATH_UNAVAILABLE: 'Vector math is unavailable on the server right now.',
}
_REASON_DEFAULT = 'The title embedding could not be read.'

# Destination status → audit event type. All three are 22 characters, well
# inside AuditLog.event_type's 64-character limit.
_EVENT_FOR_STATUS = {
    ThesisStatus.APPROVED: 'thesis.review.approved',
    ThesisStatus.REJECTED: 'thesis.review.rejected',
    ThesisStatus.PENDING_REVIEW: 'thesis.review.reopened',
}

_TERMINAL_STATUSES = (ThesisStatus.APPROVED, ThesisStatus.REJECTED)


def _format_percent(score: float) -> str:
    """Render ``score`` as a percentage: one decimal, half away from zero.

    ``round()`` would use banker's rounding, so 0.85 would not always land
    where a reviewer expects. Decimal's ROUND_HALF_UP ties away from zero.
    """
    value = Decimal(str(score * 100)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    return f'{value}%'


class _RedundancyChangeList(ChangeList):
    """ChangeList that computes the rendered page's redundancy in one call.

    The hook has to be here rather than in ``get_queryset``: that runs
    *before* pagination, so computing there would analyse every filtered row
    instead of the page actually on screen.
    """

    def get_results(self, request):
        super().get_results(request)
        try:
            results = analyze_titles(self.result_list)
        except Exception as exc:  # pragma: no cover - defensive
            # The signal is advisory. A failure here must not take the
            # changelist down with it — every badge just renders grey.
            logger.warning('Page redundancy analysis failed: %s', exc)
            results = {}

        setattr(request, _STASH_ATTR, results)
        # Annotate the very instances that will be rendered. Display
        # callables receive only ``obj``, so carrying the result on the
        # object is what lets overlap_badge read the batch instead of
        # re-analysing per row. Shared ModelAdmin state would be racy here;
        # per-instance attributes are not.
        for obj in self.result_list:
            setattr(obj, _RESULT_ATTR, results.get(obj.id))


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    """Admin interface for managing thesis submissions."""

    # No bulk mutation. This must stay None rather than an empty list —
    # Django re-adds the site-wide ``delete_selected`` default to any
    # non-None sequence, so `actions = []` would leave bulk delete in place.
    actions = None

    list_display = (
        'title_short',
        'program',
        'year',
        'status_badge',
        'overlap_badge',
        'uploaded_by_name',
        'embedding_status',
        'preview_link',
        'created_at',
    )

    list_filter = (
        'status',
        'program',
        'year',
        'embedding_status',
        'file_type',
        'created_at',
    )

    search_fields = (
        'title',
        'abstract',
        'authors',
        'keywords',
        'uploaded_by__email',
        'uploaded_by__first_name',
        'uploaded_by__last_name',
    )

    readonly_fields = (
        'id',
        'sha256',
        'uploaded_file',
        'file_type',
        'extracted_text_preview',
        'embedding_vector_info',
        'uploaded_by',
        'created_at',
        'updated_at',
        'redundancy_analysis',
        # Provenance is written only by save_model, never by the form.
        'reviewed_by',
        'reviewed_at',
    )

    fieldsets = (
        ('Thesis Information', {
            'fields': (
                'title',
                'abstract',
                'authors',
                'keywords',
                'program',
                'year',
                'adviser',
            )
        }),
        ('File Information', {
            'fields': (
                'uploaded_file',
                'file_type',
                'sha256',
                'extracted_text_preview',
            )
        }),
        ('Review Status', {
            'fields': (
                'status',
                'rejection_reason',
                'redundancy_analysis',
                'reviewed_by',
                'reviewed_at',
            )
        }),
        ('AI/Semantic Search', {
            'fields': (
                'embedding_status',
                'embedding_model',
                'embedding_generated_at',
                'embedding_vector_info',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': (
                'id',
                'uploaded_by',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )

    # ── Querying ────────────────────────────────────────────────────────

    def get_changelist(self, request, **kwargs):
        return _RedundancyChangeList

    def get_queryset(self, request):
        # select_related removes the N+1 that uploaded_by_name would
        # otherwise cause once per row, and covers the reviewer FK too.
        setattr(request, _STASH_ATTR, {})
        return (
            super().get_queryset(request)
            .select_related('uploaded_by', 'reviewed_by')
        )

    # ── Display callables ───────────────────────────────────────────────

    def title_short(self, obj):
        """Display truncated title."""
        if len(obj.title) > 60:
            return f"{obj.title[:60]}..."
        return obj.title
    title_short.short_description = 'Title'

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            ThesisStatus.PENDING_REVIEW: '#FFA500',  # Orange
            ThesisStatus.APPROVED: '#28A745',        # Green
            ThesisStatus.REJECTED: '#DC3545',        # Red
        }
        color = colors.get(obj.status, '#6C757D')
        return format_html(
            _BADGE_TEMPLATE,
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def overlap_badge(self, obj):
        """Advisory redundancy badge for one changelist row.

        Reads the map stashed once per page. The single-probe fallback covers
        being rendered outside a changelist render.

        No ``admin_order_field``: the score is computed per render, not
        stored, so offering a sort header would promise ordering we cannot
        deliver.
        """
        result = self._redundancy_for(obj)

        if result is None or not result.computed:
            return format_html(_BADGE_TEMPLATE, _NOT_COMPUTED_COLOR, 'Not computed')

        color = _OVERLAP_COLORS.get(result.label, _NOT_COMPUTED_COLOR)
        # Label comes from the unrounded score, so a percentage that displays
        # as 60.0% can still legitimately read "Clean".
        return format_html(
            _BADGE_TEMPLATE,
            color,
            f'{result.label} {_format_percent(result.score)}',
        )
    overlap_badge.short_description = 'Overlap'

    def preview_link(self, obj):
        """Open the frontend preview for this thesis in a new tab.

        ``rel="noopener"`` matters: without it the opened page receives a live
        ``window.opener`` handle on the admin tab and can navigate it.
        ``noreferrer`` additionally withholds the admin URL.
        """
        url = f'{self._frontend_base_url()}/theses/{obj.id}/preview'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Preview</a>',
            url,
        )
    preview_link.short_description = 'Preview'

    def uploaded_by_name(self, obj):
        """Display uploader's full name and email."""
        user = obj.uploaded_by
        name = f"{user.first_name} {user.last_name}".strip()
        if name:
            return f"{name} ({user.email})"
        return user.email
    uploaded_by_name.short_description = 'Uploaded By'

    def extracted_text_preview(self, obj):
        """Display preview of extracted text."""
        if not obj.extracted_text:
            return format_html('<em style="color: #999;">{}</em>', 'No text extracted')
        preview = obj.extracted_text[:500]
        if len(obj.extracted_text) > 500:
            preview += '...'
        return format_html('<pre style="white-space: pre-wrap; font-size: 11px;">{}</pre>', preview)
    extracted_text_preview.short_description = 'Extracted Text Preview'

    def embedding_vector_info(self, obj):
        """Display embedding vector information."""
        if not obj.embedding_vector:
            return format_html('<em style="color: #999;">{}</em>', 'No embedding generated')
        vector_len = len(obj.embedding_vector) if isinstance(obj.embedding_vector, list) else 0
        return format_html(
            '<strong>Dimensions:</strong> {}<br>'
            '<strong>Model:</strong> {}<br>'
            '<strong>Generated:</strong> {}',
            vector_len,
            obj.embedding_model or 'N/A',
            obj.embedding_generated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.embedding_generated_at else 'N/A'
        )
    embedding_vector_info.short_description = 'Embedding Info'

    def redundancy_analysis(self, obj):
        """Read-only redundancy panel on the change form.

        Renders the closest approved match and a link to it. Every
        user-supplied value — including the *other* thesis's title, which the
        current reviewer never typed — arrives as a format_html placeholder
        argument, never interpolated into the format string.
        """
        # ``pk is None`` is NOT a usable "unsaved" test here: Thesis.id is a
        # UUIDField with default=uuid.uuid4, so a brand-new instance already
        # carries a primary key. ``_state.adding`` is the reliable signal.
        if obj is None or obj._state.adding or obj.pk is None:
            return format_html(
                '<em>{}</em>',
                'Redundancy analysis is available after the thesis is saved.',
            )

        result = self._redundancy_for(obj)

        if result is None or not result.computed:
            reason_text = (
                _REASON_TEXT.get(result.reason, _REASON_DEFAULT)
                if result is not None else _REASON_DEFAULT
            )
            return format_html(
                '<span style="color: {};">{}</span><br>'
                '<small>{} Backfill with: {}</small>',
                _NOT_COMPUTED_COLOR,
                'Not computed',
                reason_text,
                'manage.py embed_theses --titles-only',
            )

        color = _OVERLAP_COLORS.get(result.label, _NOT_COMPUTED_COLOR)

        if result.matched_thesis_id is None:
            return format_html(
                '<strong style="color: {};">{}</strong> &nbsp; {}<br>'
                '<small>{}</small>',
                color,
                result.label,
                _format_percent(result.score),
                'No other approved thesis was available to compare against.',
            )

        match_url = reverse('admin:theses_thesis_change', args=[result.matched_thesis_id])
        noun = 'thesis' if result.corpus_size == 1 else 'theses'

        return format_html(
            '<strong style="color: {};">{}</strong> &nbsp; {}<br>'
            'Closest approved match: <a href="{}">{}</a><br>'
            '<small>Compared against {} approved {}. {}</small>',
            color,
            result.label,
            _format_percent(result.score),
            match_url,
            result.matched_title,
            result.corpus_size,
            noun,
            advisory_for(result.label),
        )
    redundancy_analysis.short_description = 'Redundancy analysis'

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _frontend_base_url() -> str:
        """Resolve the frontend origin, without a trailing slash.

        ``FRONTEND_URL`` is not defined in settings today — the project reads
        a ``FRONTEND_ORIGIN`` env var into ``CORS_ALLOWED_ORIGINS`` — so the
        fallback chain is what actually produces the value in practice.
        """
        base = getattr(settings, 'FRONTEND_URL', None)
        if not base:
            origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', None) or []
            base = origins[0] if origins else 'http://localhost:5173'
        return str(base).rstrip('/')

    @staticmethod
    def _redundancy_for(obj):
        """Return the RedundancyResult for ``obj``, or None if unavailable.

        Prefers the batch result annotated by _RedundancyChangeList, so a
        changelist render costs one ``analyze_titles`` call for the whole page
        rather than one per row. Falls back to a single-probe call when
        rendered outside a changelist — the change form, for instance.
        """
        annotated = getattr(obj, _RESULT_ATTR, _MISSING)
        if annotated is not _MISSING:
            # Present but None is a real answer (the batch could not measure
            # this row); it must not trigger a second analysis.
            return annotated
        try:
            return analyze_titles([obj]).get(obj.id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Redundancy analysis failed for thesis %s: %s', obj.id, exc)
            return None

    def _retry_embedding_if_needed(self, request, thesis) -> None:
        """Repair a missing embedding on a thesis that has just been approved.

        Extracted from the removed ``approve_theses`` bulk action. Without
        this, a thesis whose SBERT encode failed at upload can be approved and
        then sit in the repository permanently invisible to semantic search
        and title similarity, with nothing surfacing the problem.

        Best-effort by design: a failure here never rolls back the approval.
        The review decision and the embedding are independent concerns — but
        the reviewer is told, on the page, when the thesis is not searchable.
        """
        if thesis.embedding_status == EmbeddingStatus.READY:
            return

        from .services.semantic_search import (
            generate_thesis_embedding,
            generate_title_embedding,
        )

        try:
            generate_thesis_embedding(thesis)
            generate_title_embedding(thesis)
            self.message_user(
                request,
                'Embedding regenerated for this thesis.',
                level=messages.INFO,
            )
        except Exception as exc:
            logger.warning('Embedding retry failed for thesis %s: %s', thesis.id, exc)
            self.message_user(
                request,
                'This thesis could not be embedded — semantic search and '
                'redundancy analysis will not cover it. Check server logs.',
                level=messages.WARNING,
            )

    # ── Save path ───────────────────────────────────────────────────────

    def save_model(self, request, obj, form, change):
        """Persist the thesis, stamping provenance and auditing real transitions.

        The pre-save status is re-read from the database rather than taken
        from ``form.changed_data`` / ``form.initial``. Those compare against
        values captured when the page was rendered, so a concurrent reviewer's
        change makes them stale in both directions — they can report a
        transition that did not happen, or miss one that did.
        """
        previous_status = None
        if change and obj.pk is not None:
            previous_status = (
                Thesis.objects
                .filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )

        new_status = obj.status
        is_transition = previous_status != new_status

        # Two rules generate the whole transition matrix: a terminal status
        # stamps the reviewer and timestamp; returning to pending clears both.
        if is_transition:
            if new_status in _TERMINAL_STATUSES:
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
            elif new_status == ThesisStatus.PENDING_REVIEW:
                obj.reviewed_by = None
                obj.reviewed_at = None

        super().save_model(request, obj, form, change)

        if not is_transition:
            # Nothing was decided, so there is nothing to audit and no
            # provenance to touch.
            return

        if new_status == ThesisStatus.APPROVED:
            self._retry_embedding_if_needed(request, obj)

        metadata = {
            'thesis_id': str(obj.id),
            'title': (obj.title or '')[:200],
            'previous_status': previous_status,
            'new_status': new_status,
            'program': obj.program,
            'year': obj.year,
            'created': not change,
        }
        if new_status == ThesisStatus.REJECTED:
            metadata['rejection_reason'] = (obj.rejection_reason or '')[:500]

        # After the save, never before: a failed write must not leave an
        # "approved" row in the audit trail. No try/except needed —
        # audit_logger.write swallows and logs its own failures, so a log
        # outage degrades to a missing audit row rather than a broken review.
        audit_logger.write(
            _EVENT_FOR_STATUS.get(new_status, 'thesis.review.reopened'),
            actor=request.user,
            target=obj.uploaded_by,
            success=True,
            metadata=metadata,
            request=request,
        )
