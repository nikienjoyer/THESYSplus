"""Django admin configuration for identity verification models.

Admin interface for VerificationDocument and VerificationResult models.
"""

from django.contrib import admin
from .models import VerificationDocument, VerificationResult


@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    """Admin interface for VerificationDocument model."""
    
    list_display = [
        'id',
        'access_request',
        'mime_type',
        'sha256_short',
        'size_bytes',
        'uploaded_at',
    ]
    list_filter = ['mime_type', 'uploaded_at']
    search_fields = ['sha256', 'access_request__email']
    readonly_fields = [
        'id',
        'access_request',
        'file_path',
        'mime_type',
        'sha256',
        'size_bytes',
        'uploaded_at',
        'retention_purge_at',
        'purged_at',
    ]
    
    def sha256_short(self, obj):
        """Display first 8 characters of SHA256 hash."""
        return obj.sha256[:8] if obj.sha256 else ''
    sha256_short.short_description = 'SHA256 (short)'


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    """Admin interface for VerificationResult model."""
    
    list_display = [
        'id',
        'access_request',
        'status',
        'ocr_confidence',
        'decision_reason',
        'processed_at',
    ]
    list_filter = ['status', 'processed_at']
    search_fields = ['access_request__email', 'decision_reason']
    readonly_fields = [
        'id',
        'access_request',
        'status',
        'extracted_fields',
        'ocr_raw_text',
        'ocr_confidence',
        'decision_reason',
        'flagged_reasons',
        'rule_failures',
        'processed_at',
        'processor_version',
    ]
