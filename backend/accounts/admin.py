"""Minimal admin registration for the custom User model.

Lets administrators be bootstrapped via ``manage.py createsuperuser`` and
inspected through the standard Django admin. The fieldset surface mirrors
design §3.3 — id and the audit timestamps are read-only.
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.utils import get_deleted_objects
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db import transaction

from access_requests.models import AccessRequest

from .models import User


def _verification_folders(requests):
    return [
        root / str(pk)
        for pk in requests.values_list('pk', flat=True)
        for root in (
            Path(settings.PRIVATE_STORAGE_ROOT) / settings.VERIFICATION_DOCS_PATH,
            Path(settings.MEDIA_ROOT) / 'private' / 'verification_docs',
        )
    ]


def _delete_verification_for(emails):
    """Delete the access requests for ``emails`` and their uploaded ID folders.

    Access requests are linked to a user by email, not by foreign key, so a
    plain user delete would leave the request, its verification document and
    OCR result (which cascade from the request) and the file behind.
    """
    requests = AccessRequest.objects.filter(email__in=list(emails))
    folders = _verification_folders(requests)
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

    def get_deleted_objects(self, objs, request):
        """Also list what ``_delete_verification_for`` removes on the confirm page."""
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        requests = AccessRequest.objects.filter(email__in=[obj.email for obj in objs])
        if not requests.exists():
            return to_delete, model_count, perms_needed, protected
        # The access request and verification admins refuse direct deletes, so
        # the permissions this reports are deliberately not merged in.
        extra, extra_count, _, _ = get_deleted_objects(requests, request, self.admin_site)
        to_delete += extra
        for name, count in extra_count.items():
            model_count[name] = model_count.get(name, 0) + count
        files = [
            path.relative_to(folder.parent.parent).as_posix()
            for folder in _verification_folders(requests)
            if folder.is_dir()
            for path in sorted(folder.rglob('*'))
            if path.is_file()
        ]
        if files:
            to_delete += ['ID files', files]
            model_count['ID files'] = len(files)
        return to_delete, model_count, perms_needed, protected

    def delete_model(self, request, obj):
        with transaction.atomic():
            _delete_verification_for([obj.email])
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            _delete_verification_for(queryset.values_list('email', flat=True))
            super().delete_queryset(request, queryset)
