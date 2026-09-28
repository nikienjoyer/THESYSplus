from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


SUBJECTS = [
    ('EDU', 'Education and learning', 'Teaching, learning, assessment, and educational content.'),
    ('ACA', 'Academic services and research', 'University administration, student services, and research discovery.'),
    ('AGR', 'Agriculture and growing systems', 'Farm production, crops, growing conditions, and irrigation.'),
    ('HEA', 'Health and medicine', 'Care, patient records, medication, prevention, and health information.'),
    ('PUB', 'Public and community services', 'Local government, social welfare, civic administration, and community welfare.'),
    ('COM', 'Commerce and marketplaces', 'Retail transactions and marketplaces connecting sellers and buyers.'),
    ('HOU', 'Housing and accommodation', 'Finding, booking, managing, and matching accommodation.'),
    ('TRA', 'Transportation and mobility', 'Passenger transport, vehicle rental, tracking, booking, and operations.'),
    ('SEC', 'Safety and security', 'Personal protection, abuse reporting, access control, and grievance safety.'),
    ('ACC', 'Accessibility and assistive technology', 'Technology designed to overcome disability-related barriers.'),
    ('WOR', 'Careers and placements', 'Career guidance, job matching, and practical training placements.'),
    ('PER', 'Everyday life and productivity', 'Personal relationships, individual task planning, and general project productivity.'),
]


def seed_subjects(apps, schema_editor):
    Subject = apps.get_model('theses', 'ResearchSubject')
    for order, (code, name, definition) in enumerate(SUBJECTS, start=1):
        Subject.objects.using(schema_editor.connection.alias).update_or_create(
            code=code,
            defaults={'name': name, 'definition': definition, 'sort_order': order},
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('theses', '0003_thesis_title_embedding'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResearchSubject',
            fields=[
                ('code', models.CharField(max_length=8, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=96, unique=True)),
                ('definition', models.TextField()),
                ('sort_order', models.PositiveSmallIntegerField(unique=True)),
            ],
            options={'db_table': 'research_subjects', 'ordering': ['sort_order']},
        ),
        migrations.AddField(
            model_name='thesis', name='primary_subject',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='theses', to='theses.researchsubject'),
        ),
        migrations.AddField(
            model_name='thesis', name='subject_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='thesis', name='subject_reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subject_reviewed_theses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='thesis',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(primary_subject__isnull=True, subject_reviewed_at__isnull=True)
                    | models.Q(primary_subject__isnull=False, subject_reviewed_at__isnull=False)
                ),
                name='theses_subject_review_pair_check',
            ),
        ),
        migrations.RunPython(seed_subjects, migrations.RunPython.noop),
    ]
