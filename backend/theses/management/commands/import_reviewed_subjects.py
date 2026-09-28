"""Guarded initial subject import. Dry-run unless --apply is supplied."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from accounts.models import Role
from theses.models import ResearchSubject, Thesis, ThesisStatus


MANIFEST = Path(__file__).resolve().parents[2] / 'data' / 'initial_subject_assignments_v1.json'


def _load_manifest():
    rows = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if len(rows) != 52:
        raise CommandError('The approved manifest must contain exactly 52 rows.')
    ids = [UUID(row['uuid']) for row in rows]
    if len(set(ids)) != len(ids):
        raise CommandError('The approved manifest contains duplicate UUIDs.')
    return {UUID(row['uuid']): row for row in rows}


def _file_hash(thesis):
    digest = hashlib.sha256()
    with thesis.uploaded_file.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = 'Verify the approved 52-file corpus and optionally import its reviewed subjects.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the mapping after all checks pass.')
        parser.add_argument('--reviewer-email', help='Administrator account credited with the import.')
        parser.add_argument('--backup-file', help='Verified PostgreSQL backup made before the import.')

    def handle(self, *args, **options):
        manifest = _load_manifest()
        subject_codes = set(ResearchSubject.objects.values_list('code', flat=True))
        if subject_codes != {row['subject_code'] for row in manifest.values()}:
            raise CommandError('Research-subject vocabulary differs from the approved manifest.')

        reviewer = None
        if options['apply']:
            backup_name = options.get('backup_file')
            backup = Path(backup_name).resolve() if backup_name else None
            if not backup or not backup.is_file() or backup.stat().st_size == 0:
                raise CommandError('A nonempty --backup-file is required before --apply.')
            email = options.get('reviewer_email')
            if not email:
                raise CommandError('--reviewer-email is required before --apply.')
            reviewer = get_user_model().objects.filter(email__iexact=email).first()
            if reviewer is None or reviewer.role != Role.ADMINISTRATOR or not reviewer.is_active:
                raise CommandError('The importing reviewer must be an active administrator.')

        with transaction.atomic():
            theses = list(
                Thesis.objects.select_for_update()
                .filter(status=ThesisStatus.APPROVED)
                .order_by('id')
            )
            actual_ids = {thesis.id for thesis in theses}
            if actual_ids != set(manifest):
                missing = sorted(str(pk) for pk in set(manifest) - actual_ids)
                added = sorted(str(pk) for pk in actual_ids - set(manifest))
                raise CommandError(f'Approved corpus changed. Missing: {missing}; additional: {added}.')

            errors = []
            for thesis in theses:
                row = manifest[thesis.id]
                if thesis.uploaded_file.name != row['file']:
                    errors.append(f'{thesis.id}: linked file changed')
                if thesis.sha256.lower() != row['sha256'].lower():
                    errors.append(f'{thesis.id}: stored SHA-256 changed')
                try:
                    current_hash = _file_hash(thesis)
                except (OSError, ValueError) as exc:
                    errors.append(f'{thesis.id}: file cannot be hashed ({exc})')
                else:
                    if current_hash.lower() != row['sha256'].lower():
                        errors.append(f'{thesis.id}: source-file SHA-256 changed')
                if thesis.primary_subject_id or thesis.subject_reviewed_at or thesis.subject_reviewed_by_id:
                    errors.append(f'{thesis.id}: subject review already exists')
            if errors:
                raise CommandError('Import stopped:\n' + '\n'.join(errors))

            if not options['apply']:
                self.stdout.write(self.style.SUCCESS('Dry-run passed: 52 approved UUIDs, linked files, stored hashes, and source-file hashes match. No subjects changed.'))
                return

            reviewed_at = timezone.now()
            for thesis in theses:
                thesis.primary_subject_id = manifest[thesis.id]['subject_code']
                thesis.subject_reviewed_by = reviewer
                thesis.subject_reviewed_at = reviewed_at
            Thesis.objects.bulk_update(
                theses,
                fields=['primary_subject', 'subject_reviewed_by', 'subject_reviewed_at'],
                batch_size=100,
            )
            reviewed = Thesis.objects.filter(
                status=ThesisStatus.APPROVED,
                subject_reviewed_at__isnull=False,
                subject_reviewed_by=reviewer,
            )
            by_subject = reviewed.values('primary_subject_id').annotate(count=Count('id'))
            if reviewed.count() != 52 or sum(row['count'] for row in by_subject) != 52:
                raise CommandError('Post-import reconciliation failed; transaction rolled back.')
        self.stdout.write(self.style.SUCCESS(f'Imported and verified 52 reviewed subjects; reviewer {reviewer.email}.'))
