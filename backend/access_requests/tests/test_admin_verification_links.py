"""Admin presentation for the verification records attached to access requests."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from accounts.models import User
from access_requests.models import AccessRequest
from identity_verification.models import VerificationDocument, VerificationResult


@pytest.fixture
def admin_client(client, db):
    admin_user = User.objects.create_superuser(
        email='access-request.admin@example.test',
        first_name='Access',
        last_name='Reviewer',
        password='Test12345!Test',
    )
    client.force_login(admin_user)
    return client


@pytest.fixture
def pending_request(db):
    return AccessRequest.objects.create(
        email='applicant@example.test',
        first_name='Avery',
        last_name='Applicant',
        requested_role='student',
        status='pending',
    )


def _change_url(access_request):
    return reverse(
        'admin:access_requests_accessrequest_change',
        args=(access_request.pk,),
    )


@pytest.mark.django_db
def test_pending_request_links_to_its_verification_records_and_keeps_actions_below(
    admin_client,
    pending_request,
):
    document = VerificationDocument.objects.create(
        access_request=pending_request,
        file_path='/private/verification/example.png',
        mime_type='image/png',
        sha256='a' * 64,
        size_bytes=1024,
    )
    result = VerificationResult.objects.create(
        access_request=pending_request,
        status='pending_manual_review',
    )

    response = admin_client.get(_change_url(pending_request))

    assert response.status_code == 200
    html = response.content.decode()
    document_url = reverse(
        'admin:identity_verification_verificationdocument_change',
        args=(document.pk,),
    )
    result_url = reverse(
        'admin:identity_verification_verificationresult_change',
        args=(result.pk,),
    )
    assert f'href="{document_url}">{document.pk}</a>' in html
    assert f'href="{result_url}">{result.pk}</a>' in html
    assert admin_client.get(document_url).status_code == 200
    assert admin_client.get(result_url).status_code == 200

    object_tools = re.search(
        r'<ul class="object-tools[^\"]*">(.*?)</ul>',
        html,
        flags=re.DOTALL,
    )
    assert object_tools is not None
    assert 'History' in object_tools.group(1)
    assert 'Approve request' not in object_tools.group(1)
    assert 'Reject request' not in object_tools.group(1)

    action_row = '<div class="submit-row access-request-review-actions">'
    action_row_index = html.index(action_row)
    assert action_row_index > html.index('Reviewed at:')
    assert action_row_index < html.index('</form>', action_row_index)
    approve_url = reverse(
        'admin:access_requests_accessrequest_approve',
        args=(pending_request.pk,),
    )
    reject_url = reverse(
        'admin:access_requests_accessrequest_reject',
        args=(pending_request.pk,),
    )
    assert f'href="{approve_url}"' in html[action_row_index:]
    assert f'href="{reject_url}"' in html[action_row_index:]
    assert 'access-request-action access-request-approve' in html[action_row_index:]
    assert 'access-request-action access-request-reject' in html[action_row_index:]
    assert 'background: #15803d' in html
    assert 'background: #be123c' in html
    assert 'focus-visible' in html
    assert 'outline: 3px solid #1d4ed8' in html
    assert admin_client.get(approve_url).status_code == 200
    assert admin_client.get(reject_url).status_code == 200


@pytest.mark.django_db
def test_missing_verification_records_render_dashes(admin_client, pending_request):
    response = admin_client.get(_change_url(pending_request))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'Verification document id:</label>' in html
    assert 'Verification result id:</label>' in html
    document_row = re.search(
        r'<div class="form-row field-verification_document_link">'
        r'(.*?)(?=<div class="form-row|\Z)',
        html,
        flags=re.DOTALL,
    )
    result_row = re.search(
        r'<div class="form-row field-verification_result_link">'
        r'(.*?)(?=<div class="form-row|\Z)',
        html,
        flags=re.DOTALL,
    )
    assert document_row is not None
    assert result_row is not None
    assert '<div class="readonly">—</div>' in document_row.group(1)
    assert '<div class="readonly">—</div>' in result_row.group(1)


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['approved', 'denied'])
def test_reviewed_request_hides_approval_actions_but_keeps_history(
    admin_client,
    pending_request,
    status,
):
    pending_request.status = status
    pending_request.save(update_fields=['status'])

    response = admin_client.get(_change_url(pending_request))

    assert response.status_code == 200
    html = response.content.decode()
    object_tools = re.search(
        r'<ul class="object-tools[^"]*">(.*?)</ul>',
        html,
        flags=re.DOTALL,
    )
    assert object_tools is not None
    assert 'History' in object_tools.group(1)
    assert 'Approve request' not in html
    assert 'Reject request' not in html
    assert '<div class="submit-row access-request-review-actions">' not in html
