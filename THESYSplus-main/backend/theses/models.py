"""Thesis model — Phase 1 repository foundation.

Stores metadata + file path + extracted text for every uploaded thesis.
The ``embedding_status`` field is reserved for Phase 2 (SBERT) and
remains ``not_started`` for the entire Phase 1 lifecycle.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ThesisStatus(models.TextChoices):
    PENDING_REVIEW = 'pending_review', 'Pending Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class FileType(models.TextChoices):
    PDF = 'pdf', 'PDF'
    DOCX = 'docx', 'DOCX'


class EmbeddingStatus(models.TextChoices):
    """Reserved for Phase 2 (SBERT). Always ``not_started`` in Phase 1."""

    NOT_STARTED = 'not_started', 'Not Started'
    PROCESSING = 'processing', 'Processing'
    READY = 'ready', 'Ready'
    FAILED = 'failed', 'Failed'


class Program(models.TextChoices):
    """Canonical CCS programs that match RuleValidator."""

    BSIS = 'BS Information System', 'BS Information System'
    BSIT = 'BS Information Technology', 'BS Information Technology'
    BSCS = 'BS Computer Science', 'BS Computer Science'
    ACT = 'Associate in Computer Technology', 'Associate in Computer Technology'


class Thesis(models.Model):
    """A single thesis record.

    Authors and keywords are stored as JSON arrays (PostgreSQL JSONB) so
    we don't need separate junction tables for Phase 1. The ``sha256``
    column is unique to enforce duplicate-file protection at the DB level.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Metadata ────────────────────────────────────────────────────────
    title = models.CharField(max_length=500)
    abstract = models.TextField()
    authors = models.JSONField(default=list)        # ["Last, First", ...]
    keywords = models.JSONField(default=list)       # ["AI", "OCR", ...]
    program = models.CharField(
        max_length=64,
        choices=Program.choices,
    )
    year = models.PositiveSmallIntegerField()
    adviser = models.CharField(max_length=160, blank=True, default='')

    # ── File ────────────────────────────────────────────────────────────
    uploaded_file = models.FileField(
        upload_to='theses/%Y/',
        max_length=512,
    )
    file_type = models.CharField(max_length=8, choices=FileType.choices)
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)

    # ── AI / search support ─────────────────────────────────────────────
    extracted_text = models.TextField(blank=True, default='')
    embedding_status = models.CharField(
        max_length=16,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.NOT_STARTED,
    )
    # SBERT 384-dim float vector (all-MiniLM-L6-v2). Stored as JSON list
    # so the demo deployment doesn't require pgvector. For production
    # scale, swap to a vector index without changing service callers.
    embedding_vector = models.JSONField(null=True, blank=True)
    embedding_model = models.CharField(max_length=64, blank=True, default='')
    embedding_generated_at = models.DateTimeField(null=True, blank=True)

    # ── Workflow ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=16,
        choices=ThesisStatus.choices,
        default=ThesisStatus.PENDING_REVIEW,
    )
    rejection_reason = models.TextField(blank=True, default='')

    # ── Provenance ──────────────────────────────────────────────────────
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_theses',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_theses',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ──────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'theses'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='theses_status_created_idx'),
            models.Index(fields=['program'], name='theses_program_idx'),
            models.Index(fields=['year'], name='theses_year_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=[s.value for s in ThesisStatus]),
                name='theses_status_check',
            ),
            models.CheckConstraint(
                check=models.Q(file_type__in=[t.value for t in FileType]),
                name='theses_filetype_check',
            ),
            models.CheckConstraint(
                check=models.Q(year__gte=1980) & models.Q(year__lte=2100),
                name='theses_year_range_check',
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'Thesis({self.title[:50]}…, {self.status})'
