"""Minimal admin registration for the custom User model.

Lets administrators be bootstrapped via ``manage.py createsuperuser`` and
inspected through the standard Django admin. The fieldset surface mirrors
design §3.3 — id and the audit timestamps are read-only.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db import transaction

from access_requests.models import AccessRequest

from .models import User


def _delete_verification_for(emails):
    """Delete the access requests for ``emails`` and their uploaded ID folders.

    Access requests are linked to a user by email, not by foreign key, so a
    plain user delete would leave the request, its verification document and
    OCR result (which cascade from the request) and the file behind.
    """
    requests = AccessRequest.objects.filter(email__in=list(emails))
    folders = [
        root / str(pk)
        for pk in requests.values_list('pk', flat=True)
        for root in (
            Path(settings.PRIVATE_STORAGE_ROOT) / settings.VERIFICATION_DOCS_PATH,
            Path(settings.MEDIA_ROOT) / 'private' / 'verification_docs',
        )
    ]
    requests.delete()
    # Files go only once the database delete has actually committed.
    transaction.on_commit(
        lambda: [shutil.rmtree(folder, ignore_errors=True) for folder in folders]
    )


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'email',
        'first_name',
        'last_name',
        'role',
        'is_active',
        'is_email_verified',
        'last_login_at',
    )
    list_filter = ('role', 'is_active', 'is_email_verified')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'last_login_at',
        'last_login',
    )
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Role', {'fields': ('role',)}),
        (
            'Status',
            {
                'fields': (
                    'is_active',
                    'is_email_verified',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        (
            'Audit',
            {'fields': ('created_at', 'updated_at', 'last_login_at', 'last_login')},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'first_name',
                    'last_name',
                    'role',
                    'password1',
                    'password2',
                ),
            },
        ),
    )

    def delete_model(self, request, obj):
        with transaction.atomic():
            _delete_verification_for([obj.email])
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            _delete_verification_for(queryset.values_list('email', flat=True))
            super().delete_queryset(request, queryset)
