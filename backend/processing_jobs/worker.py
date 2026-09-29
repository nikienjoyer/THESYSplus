"""Single-process worker. Start separately from the web server."""

import logging
from pathlib import Path
from types import SimpleNamespace
from threading import Event, Thread

from django.core.files import File
from django.db import close_old_connections
from django.utils import timezone as django_timezone
from common.performance import timed_stage, trace_id

from access_requests.models import AccessRequest
from access_requests.email_verification import issue_email_verification_token
from identity_verification.models import VerificationResult
from identity_verification.services.orchestrator import VerificationOrchestrator
from theses.views import ThesisExtractMetadataView, ThesisExtractTitleView, ThesisUploadView

from .models import ProcessingJob
from .services import LEASE, MAX_ATTEMPTS, _job_file, cleanup_terminal


logger = logging.getLogger(__name__)


def _identity_result(job):
    req = AccessRequest.objects.get(id=job.access_request_id)
    # A restarted worker must not re-run OCR/decisions or send an email after
    # the orchestrator has already completed the request.
    if req.status == 'processing':
        prior = VerificationResult.objects.filter(access_request=req).first()
        outcome = prior if prior and prior.status == 'auto_approved' else (
            VerificationOrchestrator().verify_request(str(req.id))
        )
        req.refresh_from_db()
        if outcome.status == 'auto_approved' and req.status == 'processing':
            try:
                issue_email_verification_token(req)
            except Exception:
                logger.exception('Verification email failed for request %s', req.id)
                req.status = 'pending'
                req.save(update_fields=['status'])
    return {'status': req.status, 'decision': {
        'pending_email_verification': 'pending_email_verification',
        'pending': 'pending_manual_review',
        'denied': 'rejected',
        'approved': 'approved',
    }.get(req.status, 'processing')}


def execute(job):
    if job.kind == ProcessingJob.Kind.IDENTITY:
        return _identity_result(job), 200

    path = _job_file(job)
    if Path(job.private_file_path).resolve() != path or not path.is_file():
        raise FileNotFoundError('Private working file unavailable')
    if job.kind == ProcessingJob.Kind.TITLE:
        response = ThesisExtractTitleView()._extract_and_respond(str(path))
    elif job.kind == ProcessingJob.Kind.METADATA:
        response = ThesisExtractMetadataView()._extract_and_respond(str(path))
    elif job.kind == ProcessingJob.Kind.THESIS:
        payload = {key: value for key, value in job.payload.items()
                   if key not in ('file_name', 'extension', 'sha256', 'storage_year')}
        with path.open('rb') as stream:
            uploaded = File(stream, name=job.payload['file_name'])
            request = SimpleNamespace(
                FILES={'file': uploaded}, data=payload,
                user=job.owner, processing_job_id=job.id,
                storage_year=job.payload['storage_year'],
            )
            response = ThesisUploadView()._process_synchronous(request)
    else:
        raise ValueError('Unknown job kind')
    return response.data, response.status_code


def run_one(job):
    close_old_connections()
    stop_heartbeat = Event()

    def heartbeat():
        while not stop_heartbeat.wait(20):
            close_old_connections()
            ProcessingJob.objects.filter(
                id=job.id, state=ProcessingJob.State.RUNNING,
                attempts=job.attempts,
            ).update(lease_until=django_timezone.now() + LEASE)
            close_old_connections()

    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        with trace_id(str(job.id)), timed_stage(f'job_{job.kind}'):
            result, code = execute(job)
        if 200 <= code < 300:
            job.result = result
            job.error = {}
            job.state = ProcessingJob.State.SUCCEEDED
        else:
            # Preserve the endpoint's response body and HTTP status for UI
            # handling. A document-gate failure is terminal, not retryable.
            job.error = {'status': code, **result}
            job.state = ProcessingJob.State.FAILED
        job.lease_until = None
        job.save(update_fields=['state', 'result', 'error', 'lease_until', 'updated_at'])
    except Exception:
        logger.exception('Processing job %s failed on attempt %s', job.id, job.attempts)
        if job.attempts >= MAX_ATTEMPTS:
            job.state = ProcessingJob.State.FAILED
            job.error = {'status': 500, 'error': {
                'code': 'PROCESSING_FAILED',
                'message': 'Processing failed. Please try again.',
            }}
            job.lease_until = None
            if job.kind == ProcessingJob.Kind.IDENTITY:
                AccessRequest.objects.filter(
                    id=job.access_request_id, status='processing',
                ).update(status='pending')
        else:
            job.state = ProcessingJob.State.QUEUED
            job.lease_until = None
        job.save(update_fields=['state', 'error', 'lease_until', 'updated_at'])
    finally:
        stop_heartbeat.set()
        thread.join(timeout=2)
        if job.state in (ProcessingJob.State.SUCCEEDED, ProcessingJob.State.FAILED):
            cleanup_terminal(job)
        close_old_connections()
