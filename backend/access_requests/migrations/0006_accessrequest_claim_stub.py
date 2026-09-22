"""Add the claim stub to AccessRequest.

Lets the tab that submitted an access request later discover that the email
was verified, and obtain a fresh password-setup token, without that tab ever
having held the emailed verification link.

Purely additive: two nullable columns plus an index. Existing rows get NULLs
and simply have nothing to poll, so no data migration is required and the
current signup flow is unaffected.

NOTE for maintainers: ``makemigrations`` also wants to emit two unrelated
``AlterField`` operations (re-declaring ``accessrequest.status`` choices and
``emailverificationtoken.id``). Both are pre-existing model/migration drift
that predates this change, and both are state-only no-ops against PostgreSQL.
They are deliberately EXCLUDED here so this migration stays scoped to the
claim stub. They remain outstanding drift — worth a separate housekeeping
migration, not worth smuggling into this one.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('access_requests', '0005_email_verification_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessrequest',
            name='claim_token_hash',
            field=models.CharField(
                max_length=64, unique=True, db_index=True, null=True, blank=True,
            ),
        ),
        migrations.AddField(
            model_name='accessrequest',
            name='claim_expires_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddIndex(
            model_name='accessrequest',
            index=models.Index(
                fields=['claim_token_hash'], name='access_req_claim_hash_idx',
            ),
        ),
    ]
