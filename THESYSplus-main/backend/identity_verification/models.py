"""Models for identity verification.

Per design §3.3 and Requirements 13.1, 13.2, 13.3, 13.6, 16.2.

VerificationDocument stores uploaded Student ID/COR files with SHA256 hash
for anti-replay detection. VerificationResult stores OCR extraction results,
validation outcomes, and decision reasoning.

MVP scope: No SBERT/TF-IDF scores (deferred to post-MVP).
"""

from __future__ import annotations

import uuid

from django.db import models


class VerificationDocument(models.Model):
    """Uploaded verification document (Student ID or COR).
    
    Stores file metadata and SHA256 hash for anti-replay detection.
    Files are stored in private storage (not publicly accessible).
    
    Per Requirements 13.1, 13.3, 16.2.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Foreign key to AccessRequest (one-to-one relationship)
    access_request = models.OneToOneField(
        'access_requests.AccessRequest',
        on_delete=models.CASCADE,
        related_name='verification_document',
        db_column='access_request_id',
    )
    
    # File storage metadata
    file_path = models.TextField(null=True, blank=True)
    mime_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64, db_index=True)
    size_bytes = models.IntegerField()
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Retention management (deferred to post-MVP)
    retention_purge_at = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'verification_document'
        indexes = [
            models.Index(fields=['sha256'], name='ver_doc_sha256_idx'),
            models.Index(
                fields=['retention_purge_at'],
                name='ver_doc_retention_idx',
            ),
        ]
    
    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'VerificationDocument({self.access_request.email}, {self.sha256[:8]})'


class VerificationResult(models.Model):
    """Verification processing result and decision.
    
    Stores OCR extraction, validation outcomes, and auto-approval decision.
    
    MVP scope: OCR + rule-based validation only. No SBERT/TF-IDF scores.
    
    Per Requirements 13.2, 13.6, 7.5, 7.6.
    """
    
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('auto_approved', 'Auto Approved'),
        ('pending_manual_review', 'Pending Manual Review'),
        ('rejected', 'Rejected'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Foreign key to AccessRequest (one-to-one relationship)
    access_request = models.OneToOneField(
        'access_requests.AccessRequest',
        on_delete=models.CASCADE,
        related_name='verification_result',
        db_column='access_request_id',
    )
    
    # Decision status
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default='processing',
    )
    
    # OCR extraction results
    extracted_fields = models.JSONField(default=dict)
    ocr_raw_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(null=True, blank=True)
    
    # Decision reasoning
    decision_reason = models.TextField(blank=True)
    flagged_reasons = models.JSONField(default=list)
    
    # Rule validation failures (added in Task 4.7)
    rule_failures = models.JSONField(default=list, null=True, blank=True)
    
    # Processing metadata
    processed_at = models.DateTimeField(auto_now_add=True)
    processor_version = models.CharField(max_length=100, default='mvp-1.0')
    
    class Meta:
        db_table = 'verification_result'
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    status__in=[
                        'processing',
                        'auto_approved',
                        'pending_manual_review',
                        'rejected',
                        'error',
                    ]
                ),
                name='ver_result_status_check',
            ),
        ]
    
    def __str__(self) -> str:  # pragma: no cover - trivial
        return f'VerificationResult({self.access_request.email}, {self.status})'
