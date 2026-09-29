"""Durable, private-file backed work queue for slow document operations."""

import datetime as dt
import logging
import os
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ProcessingJob


MAX_ATTEMPTS = 3
LEASE = dt.timedelta(minutes=2)
RETENTION = dt.timedelta(days=2)
logger = logging.getLogger(__name__)


def _job_file(job):
    root = (Path(settings.PRIVATE_STORAGE_ROOT) / 'processing_jobs').resolve()
    suffix = job.payload.get('extension', '')
    if suffix not in ('.pdf', '.docx'):
        raise ValueError('Unsupported job file extension')
    path = (root / str(job.id) / f'upload{suffix}').resolve()
    if not path.is_relative_to(root):
        raise ValueError('Invalid private job path')
    return path


def enqueue_file(kind, uploaded, *, owner=None, payload=None, access_request_id=None):
    """Copy a validated upload to private storage before acknowledging it."""
    clean_payload = dict(payload or {})
    clean_payload['extension'] = Path(uploaded.name).suffix.lower()
    job = ProcessingJob(
        kind=kind, owner=owner, payload=clean_payload,
        access_request_id=access_request_id,
        expires_at=timezone.now() + RETENTION,
    )
    path = _job_file(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    try:
        with path.open('xb') as dest:
            uploaded.seek(0)
            for chunk in uploaded.chunks():
                dest.write(chunk)
        os.chmod(path, 0o600)
        job.private_file_path = str(path)
        job.save(force_insert=True)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return job


def enqueue_identity(access_request_id):
    job = ProcessingJob.objects.create(
        kind=ProcessingJob.Kind.IDENTITY,
        access_request_id=access_request_id,
        expires_at=timezone.now() + RETENTION,
    )
    return job


def claim_next():
    """Atomically claim queued or expired work across worker restarts."""
    now = timezone.now()
    with transaction.atomic():
        exhausted = list(ProcessingJob.objects.select_for_update(skip_locked=True).filter(
            state=ProcessingJob.State.RUNNING,
            lease_until__lt=now,
            attempts__gte=MAX_ATTEMPTS,
        ))
        for stale in exhausted:
            stale.state = ProcessingJob.State.FAILED
            stale.lease_until = None
            stale.error = {'status': 500, 'error': {
                'code': 'PROCESSING_FAILED',
                'message': 'Processing failed. Please try again.',
            }}
            stale.save(update_fields=['state', 'lease_until', 'error', 'updated_at'])
            if stale.kind == ProcessingJob.Kind.IDENTITY and stale.access_request_id:
                from access_requests.models import AccessRequest
                AccessRequest.objects.filter(
                    id=stale.access_request_id, status='processing',
                ).update(status='pending')
            transaction.on_commit(lambda item=stale: cleanup_terminal(item))
        job = (ProcessingJob.objects.select_for_update(skip_locked=True)
               .filter(attempts__lt=MAX_ATTEMPTS)
               .filter(state=ProcessingJob.State.QUEUED)
               .order_by('created_at').first())
        if job is None:
            job = (ProcessingJob.objects.select_for_update(skip_locked=True)
                   .filter(state=ProcessingJob.State.RUNNING, lease_until__lt=now,
                           attempts__lt=MAX_ATTEMPTS)
                   .order_by('lease_until').first())
        if job is None:
            return None
        job.state = ProcessingJob.State.RUNNING
        job.attempts += 1
        job.lease_until = now + LEASE
        job.save(update_fields=['state', 'attempts', 'lease_until', 'updated_at'])
        return job


def remove_job_file(job):
    if not job.private_file_path:
        return
    expected = _job_file(job)
    if Path(job.private_file_path).resolve() != expected:
        raise ValueError('Job file escaped private storage')
    expected.unlink(missing_ok=True)
    try:
        expected.parent.rmdir()
    except OSError:
        pass


def remove_uncommitted_thesis_file(job):
    """Remove a deterministic upload path only when no thesis owns it."""
    if job.kind != ProcessingJob.Kind.THESIS:
        return
    from django.core.files.storage import default_storage
    from theses.models import Thesis

    if Thesis.objects.filter(processing_job_id=job.id).exists():
        return
    extension = job.payload.get('extension', '')
    year = job.payload.get('storage_year')
    if extension not in ('.pdf', '.docx') or not isinstance(year, int):
        return
    default_storage.delete(f'theses/{year}/{job.id}{extension}')


def cleanup_terminal(job):
    try:
        remove_uncommitted_thesis_file(job)
        remove_job_file(job)
    except Exception:
        logger.exception('Could not clean terminal processing job %s', job.id)
