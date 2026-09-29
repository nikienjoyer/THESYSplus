import datetime as dt
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, User
from processing_jobs.models import ProcessingJob
from processing_jobs.services import claim_next
from processing_jobs.worker import run_one
from theses.models import Thesis
from theses.tests.test_thesis_gate_integration import THESIS_LINES, COR_LINES, _pdf_from_lines
from theses.views import ThesisUploadView


@pytest.fixture(autouse=True)
def private_test_storage(settings, tmp_path):
    settings.DOCUMENT_PROCESSING_ASYNC = True
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    settings.PRIVATE_STORAGE_ROOT = str(tmp_path / 'private')


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email='async@pampangastateu.edu.ph', first_name='Async', last_name='Uploader',
        role=Role.STUDENT, password='Test12345!Test',
    )


def submit(user, source):
    request = APIRequestFactory().post('/api/v1/theses/upload/', {
        'title': 'A Mobile Health Records System for Rural Clinics',
        'abstract': 'A sufficiently long abstract for the serializer to accept.',
        'authors': '["Dela Cruz, Juan M."]',
        'keywords': '["mobile health"]',
        'program': 'BS Information Technology',
        'year': '2025',
        'file': SimpleUploadedFile('manuscript.pdf', source, content_type='application/pdf'),
    }, format='multipart')
    force_authenticate(request, user=user)
    return ThesisUploadView.as_view()(request)


@pytest.mark.django_db(transaction=True)
def test_upload_is_invisible_until_gate_and_worker_finishes(uploader, monkeypatch):
    from theses.services import semantic_search
    monkeypatch.setattr(semantic_search, 'embed_text', lambda _text: [1.0] + [0.0] * 383)
    response = submit(uploader, _pdf_from_lines(THESIS_LINES))
    assert response.status_code == 202
    assert not Thesis.objects.exists()
    job = claim_next()
    assert str(job.id) == response.data['job_id']
    from processing_jobs.worker import execute
    first, first_code = execute(job)
    replay, replay_code = execute(job)
    assert first_code == replay_code == 201
    assert first['id'] == replay['id']
    assert Thesis.objects.count() == 1
    run_one(job)
    job.refresh_from_db()
    assert job.state == ProcessingJob.State.SUCCEEDED
    assert job.result['title'] == 'A Mobile Health Records System for Rural Clinics'
    assert not __import__('pathlib').Path(job.private_file_path).exists()
    thesis = Thesis.objects.get(processing_job_id=job.id)
    assert thesis.extracted_text
    assert thesis.embedding_vector is not None
    assert Thesis.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_gate_failure_has_no_thesis_or_stored_file(uploader):
    response = submit(uploader, _pdf_from_lines(COR_LINES))
    assert response.status_code == 202
    job = claim_next()
    run_one(job)
    job.refresh_from_db()
    assert job.state == ProcessingJob.State.FAILED
    assert job.error['error']['code'] == 'NOT_A_THESIS_DOCUMENT'
    assert not Thesis.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_expired_lease_can_be_reclaimed(uploader):
    response = submit(uploader, _pdf_from_lines(THESIS_LINES))
    job = claim_next()
    assert str(job.id) == response.data['job_id']
    job.lease_until = timezone.now() - dt.timedelta(seconds=1)
    job.save(update_fields=['lease_until'])
    reclaimed = claim_next()
    assert reclaimed.id == job.id and reclaimed.attempts == 2
    reclaimed.attempts = 3
    reclaimed.lease_until = timezone.now() - dt.timedelta(seconds=1)
    reclaimed.save(update_fields=['attempts', 'lease_until'])
    assert claim_next() is None
    reclaimed.refresh_from_db()
    assert reclaimed.state == ProcessingJob.State.FAILED
    assert not __import__('pathlib').Path(reclaimed.private_file_path).exists()


@pytest.mark.django_db(transaction=True)
def test_other_user_cannot_poll_job(uploader, client):
    response = submit(uploader, _pdf_from_lines(THESIS_LINES))
    other = User.objects.create_user(
        email='otherasync@pampangastateu.edu.ph', first_name='Other',
        last_name='User', role=Role.STUDENT, password='Test12345!Test',
    )
    from auth_service.services import issue_token_pair
    token = issue_token_pair(other, request=None, remember_me=False).access_token
    denied = client.get(
        reverse('processing-job-status', args=[response.data['job_id']]),
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )
    assert denied.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_access_document_returns_processing_then_worker_decision(client):
    from PIL import Image
    from access_requests.models import AccessRequest

    image = Image.new('RGB', (160, 100), 'white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    response = client.post(
        reverse('access-request-submit'),
        data={
            'email': '2023123456@pampangastateu.edu.ph',
            'first_name': 'Sample', 'last_name': 'Student',
            'requested_role': 'student',
            'document': SimpleUploadedFile('id.png', buffer.getvalue(), content_type='image/png'),
        },
        HTTP_ORIGIN='http://localhost:5173',
    )
    assert response.status_code == 202
    assert response.json()['decision'] == 'processing'
    claim = response.json()['claim']
    waiting = client.get(reverse('access-request-status'), {'claim': claim})
    assert waiting.json()['status'] == 'processing'
    job = claim_next()
    assert job.kind == ProcessingJob.Kind.IDENTITY
    run_one(job)
    job.refresh_from_db()
    assert job.state == ProcessingJob.State.SUCCEEDED
    req = AccessRequest.objects.get(email='2023123456@pampangastateu.edu.ph')
    assert req.status in ('pending', 'denied', 'pending_email_verification')


@pytest.mark.django_db(transaction=True)
def test_identity_retry_does_not_send_second_email(monkeypatch):
    from access_requests.models import AccessRequest
    from processing_jobs.services import enqueue_identity
    from processing_jobs.worker import execute
    from identity_verification.services.orchestrator import VerificationOrchestrator
    import processing_jobs.worker as worker

    req = AccessRequest.objects.create(
        email='2023123400@pampangastateu.edu.ph', first_name='Sample',
        last_name='Student', requested_role='student', status='processing',
    )
    calls = {'ocr': 0, 'email': 0}

    def verify(_self, _id):
        calls['ocr'] += 1
        return type('Outcome', (), {'status': 'auto_approved'})()

    def email(request):
        calls['email'] += 1
        request.status = 'pending_email_verification'
        request.save(update_fields=['status'])

    monkeypatch.setattr(VerificationOrchestrator, 'verify_request', verify)
    monkeypatch.setattr(worker, 'issue_email_verification_token', email)
    job = enqueue_identity(req.id)
    execute(job)
    execute(job)
    assert calls == {'ocr': 1, 'email': 1}
