"""Move legacy verification uploads out of the development media tree.

Run without flags to audit; --apply copies, reconciles and then removes legacy
copies. Back up the database and source files before applying this command.
"""

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identity_verification.models import VerificationDocument


SUFFIXES = {
    'image/jpeg': {'.jpg', '.jpeg'},
    'image/png': {'.png'},
    'application/pdf': {'.pdf'},
}


def checked_file(path, document, root):
    """Reject paths outside this document's directory and mismatched bytes."""
    expected_parent = (root / str(document.access_request_id)).resolve()
    try:
        resolved = path.resolve(strict=True)
        if (resolved.parent != expected_parent or not resolved.is_file()
                or resolved.is_symlink() or resolved.suffix.lower() not in SUFFIXES.get(document.mime_type, set())
                or resolved.stem.lower() != document.sha256.lower()):
            return False
        digest = hashlib.sha256()
        size = 0
        with resolved.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                size += len(chunk)
                digest.update(chunk)
        return size == document.size_bytes and digest.hexdigest() == document.sha256.lower()
    except (OSError, ValueError):
        return False


class Command(BaseCommand):
    help = 'Audit or migrate legacy verification files into PRIVATE_STORAGE_ROOT.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Copy and reconcile, then remove legacy copies')

    def handle(self, *args, **options):
        old_root = (Path(settings.MEDIA_ROOT) / 'private' / 'verification_docs').resolve()
        new_root = (Path(settings.PRIVATE_STORAGE_ROOT) / settings.VERIFICATION_DOCS_PATH).resolve()
        if old_root == new_root or old_root in new_root.parents or new_root in old_root.parents:
            raise CommandError('Legacy and private storage roots must be separate.')

        documents = list(VerificationDocument.objects.order_by('id'))
        moves = []
        cleanup = []
        errors = []
        for document in documents:
            if document.purged_at or not document.file_path:
                continue
            source = Path(document.file_path)
            old_candidate = old_root / str(document.access_request_id) / source.name
            new_candidate = new_root / str(document.access_request_id) / source.name
            if source == old_candidate:
                if not checked_file(source, document, old_root):
                    errors.append(f'{document.id}: legacy file path, size or SHA-256 mismatch')
                elif new_candidate.exists() and not checked_file(new_candidate, document, new_root):
                    errors.append(f'{document.id}: destination mismatch')
                else:
                    moves.append((document, source, new_candidate))
                    cleanup.append(source)
            elif source == new_candidate:
                if not checked_file(source, document, new_root):
                    errors.append(f'{document.id}: private file path, size or SHA-256 mismatch')
                else:
                    legacy_copy = old_candidate
                    if legacy_copy.exists():
                        if checked_file(legacy_copy, document, old_root):
                            cleanup.append(legacy_copy)
                        else:
                            errors.append(f'{document.id}: leftover legacy copy mismatch')
            else:
                errors.append(f'{document.id}: path is outside its expected document directory')

        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(f'Audited {len(documents)} records; {len(moves)} legacy files to migrate.')
        if not options['apply']:
            return

        for document, source, destination in moves:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not destination.exists():
                temporary = destination.with_name(destination.name + f'.{uuid.uuid4().hex}.tmp')
                try:
                    with source.open('rb') as reader, temporary.open('xb') as writer:
                        shutil.copyfileobj(reader, writer)
                        writer.flush()
                        os.fsync(writer.fileno())
                    os.chmod(temporary, 0o600)
                    # Temporary names do not match the record hash; validate bytes directly.
                    if temporary.stat().st_size != document.size_bytes or hashlib.sha256(temporary.read_bytes()).hexdigest() != document.sha256.lower():
                        raise CommandError(f'{document.id}: copied bytes failed verification')
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            if not checked_file(destination, document, new_root):
                raise CommandError(f'{document.id}: destination failed verification')
            with transaction.atomic():
                locked = VerificationDocument.objects.select_for_update().get(pk=document.pk)
                if locked.file_path != str(source):
                    raise CommandError(f'{document.id}: database path changed during migration')
                locked.file_path = str(destination)
                locked.save(update_fields=['file_path'])

        # Reconcile every recorded file before removing any legacy copy.
        for document in VerificationDocument.objects.order_by('id'):
            if document.purged_at or not document.file_path:
                continue
            path = Path(document.file_path)
            if not checked_file(path, document, new_root):
                raise CommandError(f'{document.id}: final reconciliation failed; legacy files retained')
        for source in cleanup:
            source.unlink()
        self.stdout.write(self.style.SUCCESS(f'Migrated and reconciled {len(moves)} files.'))
