"""Django admin configuration for identity verification models."""

import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html

from accounts.models import Role

from .constants import MAGIC_SIGNATURES
from .models import VerificationDocument, VerificationResult


def _staff_administrator(request):
    user = request.user
    return bool(user.is_authenticated and user.is_active and user.is_staff
                and user.role == Role.ADMINISTRATOR)


def _verified_file(document):
    """Resolve only the recorded document in private or legacy private storage."""
    if document.purged_at or not document.file_path:
        return None
    mime_suffixes = {
        'image/jpeg': {'.jpg', '.jpeg'},
        'image/png': {'.png'},
        'application/pdf': {'.pdf'},
    }
    allowed = mime_suffixes.get(document.mime_type)
    if not allowed:
        return None
    path_value = Path(document.file_path)
    if path_value.suffix.lower() not in allowed or path_value.stem.lower() != document.sha256.lower():
        return None
    roots = (
        Path(settings.PRIVATE_STORAGE_ROOT) / settings.VERIFICATION_DOCS_PATH,
        Path(settings.MEDIA_ROOT) / 'private' / 'verification_docs',
    )
    try:
        path_value = path_value.resolve(strict=True)
        if not path_value.is_file() or not any(
            path_value.parent == (root / str(document.access_request_id)).resolve()
            for root in roots
        ):
            return None
        digest = hashlib.sha256()
        with path_value.open('rb') as stream:
            if not stream.read(len(MAGIC_SIGNATURES[document.mime_type])).startswith(
                MAGIC_SIGNATURES[document.mime_type]
            ):
                return None
            stream.seek(0)
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(chunk)
                digest.update(chunk)
        if size != document.size_bytes or digest.hexdigest() != document.sha256.lower():
            return None
    except (OSError, ValueError):
        return None
    return path_value


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
        'document_preview',
        'mime_type',
        'sha256',
        'size_bytes',
        'uploaded_at',
        'retention_purge_at',
        'purged_at',
    ]

    def has_module_permission(self, request):
        return _staff_administrator(request)

    def has_view_permission(self, request, obj=None):
        return _staff_administrator(request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        custom = [path(
            '<uuid:object_id>/preview/',
            self.admin_site.admin_view(self.preview_view),
            name='identity_verification_verificationdocument_preview',
        )]
        return custom + super().get_urls()

    @admin.display(description='Document preview')
    def document_preview(self, obj):
        if not _verified_file(obj):
            return 'File unavailable'
        url = reverse('admin:identity_verification_verificationdocument_preview', args=(obj.pk,))
        if obj.mime_type == 'application/pdf':
            return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">Open PDF</a>', url)
        return format_html(
            '<img src="{}" alt="Uploaded verification document" '
            'style="display:block;max-width:480px;max-height:360px;width:auto;height:auto;object-fit:contain">',
            url,
        )

    def preview_view(self, request, object_id):
        if not _staff_administrator(request) or not self.has_view_permission(request):
            raise PermissionDenied
        if request.method != 'GET':
            raise Http404
        document = self.get_queryset(request).filter(pk=object_id).first()
        if document is None:
            raise Http404
        file_path = _verified_file(document)
        if file_path is None:
            raise Http404
        response = FileResponse(file_path.open('rb'), content_type=document.mime_type)
        response['Content-Disposition'] = f'inline; filename="verification-document{file_path.suffix.lower()}"'
        response['Cache-Control'] = 'private, no-store, max-age=0'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'no-referrer'
        return response
    
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
