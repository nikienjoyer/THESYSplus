"""Add EmailVerificationToken model and pending_email_verification status.

- EmailVerificationToken table for single-use email verification links.
- AccessRequest status constraint updated to include 'pending_email_verification'.
"""

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('access_requests', '0004_extend_accessrequest_for_verification'),
    ]

    operations = [
        # 1. Drop old status check constraint (includes the old set of statuses).
        migrations.RemoveConstraint(
            model_name='accessrequest',
            name='access_requests_status_check',
        ),

        # 2. Add new status check constraint with 'pending_email_verification'.
        migrations.AddConstraint(
            model_name='accessrequest',
            constraint=models.CheckConstraint(
                check=models.Q(
                    status__in=[
                        'pending',
                        'approved',
                        'denied',
                        'processing',
                        'auto_approved',
                        'pending_manual_review',
                        'pending_email_verification',
                    ]
                ),
                name='access_requests_status_check',
            ),
        ),

        # 3. Create EmailVerificationToken table.
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True,
                    default=__import__('uuid').uuid4,
                    editable=False,
                )),
                ('access_request', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='email_verification_token',
                    to='access_requests.accessrequest',
                )),
                ('token_hash', models.CharField(
                    db_index=True, max_length=64, unique=True,
                )),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'email_verification_tokens',
                'indexes': [
                    models.Index(
                        fields=['token_hash'],
                        name='email_ver_token_hash_idx',
                    ),
                ],
            },
        ),
    ]
