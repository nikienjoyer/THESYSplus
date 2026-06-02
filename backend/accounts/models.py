"""User model, role enum, and custom manager for the ``accounts`` app.

Per design §3.2 / §3.3:

* Roles are an enum-style varchar with a CHECK constraint, NOT a separate
  ``roles`` table. Only three values exist (student, faculty, administrator)
  and they are never user-editable.
* ``users`` is keyed by UUIDv4, the email column is ``citext`` (case-
  insensitive comparison handled by the database), and ``password_hash``
  is nullable so admin-provisioned accounts can exist before the user has
  set their first password (Requirement 5.7).
* ``last_login_at`` is the auth-module-specific login timestamp recorded
  by the login view (Requirement 1.6). Django's stock ``last_login`` field
  on ``AbstractBaseUser`` remains in place for the session machinery and
  is updated automatically by ``django.contrib.auth.login``.
"""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.fields import CIEmailField
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Canonical lowercase role identifiers shared with the JWT payload.

    Display labels are capitalized for the UI per the glossary in
    requirements.md, but the database value is always lowercase.
    """

    STUDENT = 'student', 'Student'
    FACULTY = 'faculty', 'Faculty'
    ADMINISTRATOR = 'administrator', 'Administrator'


# Roles that an unprovisioned user may request via ``/request-access``.
# Administrator is intentionally NOT self-requestable (Requirement 7.8).
# Attached after class definition because ``TextChoices`` is a true Enum
# subclass (any class-level value would be interpreted as an enum member).
Role.ALLOWED_FOR_REQUEST = ('student', 'faculty')


class UserManager(BaseUserManager):
    """Custom manager keyed on email (no ``username`` field exists)."""

    use_in_migrations = True

    def create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: str = Role.STUDENT,
        password: str | None = None,
        **extra_fields,
    ):
        """Create a regular user.

        ``password=None`` is permitted so the access-request approval flow
        can provision an account whose ``password_hash`` is NULL until the
        user completes the initial password-set step (Requirement 5.7).
        """
        if not email:
            raise ValueError('email is required')
        if not first_name:
            raise ValueError('first_name is required')
        if not last_name:
            raise ValueError('last_name is required')

        email = self.normalize_email(email).lower()
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            **extra_fields,
        )
        if password is not None:
            user.set_password(password)
        else:
            # AbstractBaseUser.set_unusable_password would write a sentinel;
            # we want a literal NULL so downstream code can detect "not yet
            # set" via ``is_password_usable`` returning False on empty input.
            user.password = None
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        **extra_fields,
    ):
        """Create an administrator account that can also log into the Django admin.

        ``role`` is forced to ``administrator``; ``is_staff`` and
        ``is_superuser`` are set to True so the standard Django admin
        permission machinery grants full access. ``is_email_verified`` is
        set to True since superusers bypass the access-request flow.
        """
        extra_fields['role'] = Role.ADMINISTRATOR
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields['is_staff'] is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields['is_superuser'] is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    """The single user table for THESYS+.

    Notes on the ``password`` field
    --------------------------------
    Django's ``AbstractBaseUser`` declares a non-nullable ``password``
    column (the database column that stores the hashed password). The auth
    module needs that column to be nullable so admin-provisioned accounts
    can exist before the user has chosen a password (Requirement 5.7); the
    field is overridden below with ``null=True, blank=True``. Django's
    ``set_password`` / ``check_password`` continue to work normally because
    they just write/read this column.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = CIEmailField(max_length=254, unique=True)

    # Override AbstractBaseUser.password so it is nullable. The on-disk
    # column name remains ``password`` (Django's convention); design §3.3
    # refers to it as ``password_hash`` semantically.
    password = models.CharField(
        _('password'),
        max_length=128,
        null=True,
        blank=True,
    )

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    # Required by Django admin's permission gating. Only superusers (created
    # via ``create_superuser``) are flagged as staff; ordinary administrator
    # accounts can still be granted staff status manually if needed.
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Distinct from AbstractBaseUser.last_login (which Django updates on
    # session login). last_login_at is the auth-module-specific timestamp
    # written by the JWT login view per Requirement 1.6.
    last_login_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        constraints = [
            models.CheckConstraint(
                check=models.Q(role__in=[r.value for r in Role]),
                name='users_role_check',
            ),
        ]
        indexes = [
            models.Index(fields=['role'], name='users_role_idx'),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.email

    def save(self, *args, **kwargs):
        # Belt-and-suspenders normalisation. citext makes the column
        # case-insensitive at compare time, but storing the lowercase form
        # keeps display consistent.
        if self.email:
            self.email = self.email.lower()
        return super().save(*args, **kwargs)
