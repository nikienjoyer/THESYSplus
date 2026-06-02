"""Django Admin configuration for Thesis model."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import Thesis, ThesisStatus


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    """Admin interface for managing thesis submissions."""

    list_display = (
        'title_short',
        'program',
        'year',
        'status_badge',
        'uploaded_by_name',
        'embedding_status',
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
    
    actions = ['approve_theses', 'reject_theses', 'mark_pending_review']
    
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
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
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
            return format_html('<em style="color: #999;">No text extracted</em>')
        preview = obj.extracted_text[:500]
        if len(obj.extracted_text) > 500:
            preview += '...'
        return format_html('<pre style="white-space: pre-wrap; font-size: 11px;">{}</pre>', preview)
    extracted_text_preview.short_description = 'Extracted Text Preview'
    
    def embedding_vector_info(self, obj):
        """Display embedding vector information."""
        if not obj.embedding_vector:
            return format_html('<em style="color: #999;">No embedding generated</em>')
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
    
    def approve_theses(self, request, queryset):
        """Bulk action to approve selected theses."""
        updated = queryset.filter(status=ThesisStatus.PENDING_REVIEW).update(
            status=ThesisStatus.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            rejection_reason='',
        )
        self.message_user(request, f'{updated} thesis(es) approved successfully.')
    approve_theses.short_description = 'Approve selected theses'
    
    def reject_theses(self, request, queryset):
        """Bulk action to reject selected theses."""
        updated = queryset.filter(status=ThesisStatus.PENDING_REVIEW).update(
            status=ThesisStatus.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{updated} thesis(es) rejected. Please add rejection reasons individually.')
    reject_theses.short_description = 'Reject selected theses'
    
    def mark_pending_review(self, request, queryset):
        """Bulk action to mark theses as pending review."""
        updated = queryset.update(
            status=ThesisStatus.PENDING_REVIEW,
            reviewed_by=None,
            reviewed_at=None,
            rejection_reason='',
        )
        self.message_user(request, f'{updated} thesis(es) marked as pending review.')
    mark_pending_review.short_description = 'Mark as pending review'
    
    def save_model(self, request, obj, form, change):
        """Auto-set reviewed_by and reviewed_at when status changes to approved/rejected."""
        if change and 'status' in form.changed_data:
            if obj.status in (ThesisStatus.APPROVED, ThesisStatus.REJECTED):
                if not obj.reviewed_by:
                    obj.reviewed_by = request.user
                if not obj.reviewed_at:
                    obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

