"""Minimal admin registration for the custom User model.

Lets administrators be bootstrapped via ``manage.py createsuperuser`` and
inspected through the standard Django admin. The fieldset surface mirrors
design §3.3 — id and the audit timestamps are read-only.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


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
