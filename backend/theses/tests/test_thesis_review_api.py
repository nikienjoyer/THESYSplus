"""POST /api/v1/theses/<id>/review/ — administrators approve or reject a
pending thesis from the app, and the uploader is emailed the decision."""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from accounts.models import Role, User
from audit.models import AuditLog
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus


def _user(email, role):
    return User.objects.create_user(
        email=email, first_name='Test', last_name=role.title(), role=role, password='Test12345!Test',
    )


@pytest.fixture
def administrator(db):
    return _user('review-admin@pampangastateu.edu.ph', Role.ADMINISTRATOR)


@pytest.fixture
def student(db):
    return _user('2021990001@pampangastateu.edu.ph', Role.STUDENT)


@pytest.fixture
def pending_thesis(student):
    thesis = Thesis(
        title='Pending Review Thesis', abstract='Abstract.', authors=['T, T.'], keywords=['k'],
        program=Program.BSIT.value, year=2024, adviser='', file_type=FileType.PDF,
        sha256='e' * 64, extracted_text='', status=ThesisStatus.PENDING_REVIEW,
        uploaded_by=student, embedding_status=EmbeddingStatus.READY,
    )
    thesis.uploaded_file.save('pending.pdf', ContentFile(b'%PDF-1.4'), save=False)
    thesis.save()
    return thesis


@pytest.fixture
def sent(monkeypatch):
    """Capture decision emails instead of sending them."""
    outbox = []

    class _Backend:
        def send(self, to, subject, template_name, context):
            outbox.append({'to': to, 'subject': subject, 'template': template_name, 'context': context})
            return True

    monkeypatch.setattr('theses.services.review.default_email_backend', lambda: _Backend())
    return outbox


def _post(client, user, thesis, payload):
    from auth_service.services import issue_token_pair
    token = issue_token_pair(user, request=None, remember_me=False).access_token
    return client.post(
        reverse('thesis-review', kwargs={'id': str(thesis.id)}),
        payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}',
    )


@pytest.mark.django_db
class TestReviewEndpoint:
    def test_administrator_approves_a_pending_thesis(self, client, administrator, pending_thesis, sent):
        response = _post(client, administrator, pending_thesis, {'decision': 'approve'})

        assert response.status_code == 200
        assert response.json()['status'] == ThesisStatus.APPROVED
        pending_thesis.refresh_from_db()
        assert pending_thesis.status == ThesisStatus.APPROVED
        assert pending_thesis.reviewed_by == administrator
        assert pending_thesis.reviewed_at is not None
        assert AuditLog.objects.filter(event_type='thesis.review.approved').count() == 1
        assert [m['template'] for m in sent] == ['thesis_approved']
        assert sent[0]['to'] == pending_thesis.uploaded_by.email
        assert sent[0]['context']['thesis_url'].endswith(f'/repository/{pending_thesis.id}')

    def test_administrator_rejects_with_a_reason(self, client, administrator, pending_thesis, sent):
        response = _post(client, administrator, pending_thesis,
                         {'decision': 'reject', 'reason': 'Abstract is missing the methodology.'})

        assert response.status_code == 200
        pending_thesis.refresh_from_db()
        assert pending_thesis.status == ThesisStatus.REJECTED
        assert pending_thesis.rejection_reason == 'Abstract is missing the methodology.'
        assert response.json()['rejection_reason'] == 'Abstract is missing the methodology.'
        assert AuditLog.objects.filter(event_type='thesis.review.rejected').count() == 1
        assert [m['template'] for m in sent] == ['thesis_rejected']
        assert sent[0]['context']['reason'] == 'Abstract is missing the methodology.'

    @pytest.mark.parametrize('reason', [None, '', '   '])
    def test_rejecting_requires_a_reason(self, client, administrator, pending_thesis, sent, reason):
        payload = {'decision': 'reject'} if reason is None else {'decision': 'reject', 'reason': reason}
        response = _post(client, administrator, pending_thesis, payload)

        assert response.status_code == 400
        pending_thesis.refresh_from_db()
        assert pending_thesis.status == ThesisStatus.PENDING_REVIEW
        assert sent == []

    def test_unknown_decision_is_refused(self, client, administrator, pending_thesis, sent):
        assert _post(client, administrator, pending_thesis, {'decision': 'maybe'}).status_code == 400

    @pytest.mark.parametrize('role', [Role.FACULTY, Role.STUDENT])
    def test_only_administrators_may_review(self, client, pending_thesis, sent, role):
        user = _user(f'not-admin-{role}@pampangastateu.edu.ph', role)
        response = _post(client, user, pending_thesis, {'decision': 'approve'})

        assert response.status_code == 403
        pending_thesis.refresh_from_db()
        assert pending_thesis.status == ThesisStatus.PENDING_REVIEW
        assert sent == []

    def test_a_decided_thesis_is_not_reviewed_again(self, client, administrator, pending_thesis, sent):
        Thesis.objects.filter(pk=pending_thesis.pk).update(status=ThesisStatus.APPROVED)
        response = _post(client, administrator, pending_thesis, {'decision': 'reject', 'reason': 'Late.'})

        assert response.status_code == 409
        assert sent == []

    def test_approval_repairs_a_missing_embedding(self, client, administrator, pending_thesis, sent, monkeypatch):
        calls = []
        monkeypatch.setattr('theses.services.semantic_search.generate_thesis_embedding',
                            lambda t, **k: calls.append('composite'))
        monkeypatch.setattr('theses.services.semantic_search.generate_title_embedding',
                            lambda t, **k: calls.append('title'))
        Thesis.objects.filter(pk=pending_thesis.pk).update(embedding_status=EmbeddingStatus.FAILED)

        assert _post(client, administrator, pending_thesis, {'decision': 'approve'}).status_code == 200
        assert calls == ['composite', 'title']

    def test_a_failed_email_does_not_undo_the_decision(self, client, administrator, pending_thesis, monkeypatch):
        class _Broken:
            def send(self, **kwargs):
                raise RuntimeError('smtp down')

        monkeypatch.setattr('theses.services.review.default_email_backend', lambda: _Broken())
        response = _post(client, administrator, pending_thesis, {'decision': 'approve'})

        assert response.status_code == 200
        pending_thesis.refresh_from_db()
        assert pending_thesis.status == ThesisStatus.APPROVED
