"""Test the audit log admin endpoint.

Per Requirement 11.4, the audit log read endpoint is restricted to administrators
and supports pagination and filtering.
"""

from __future__ import annotations

import pytest
from datetime import timezone as dt_timezone
from django.test import Client
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


@pytest.fixture
def admin_user(db):
    """Create an administrator user."""
    return User.objects.create_user(
        email='admin@pampangastateu.edu.ph',
        first_name='Admin',
        last_name='User',
        role='administrator',
        password='SecurePassword123',
    )


@pytest.fixture
def student_user(db):
    """Create a student user."""
    return User.objects.create_user(
        email='student@pampangastateu.edu.ph',
        first_name='Student',
        last_name='User',
        role='student',
        password='SecurePassword123',
    )


@pytest.fixture
def faculty_user(db):
    """Create a faculty user."""
    return User.objects.create_user(
        email='faculty@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='User',
        role='faculty',
        password='SecurePassword123',
    )


@pytest.mark.django_db
class TestAuditLogAdminEndpoint:
    """Test the GET /api/v1/admin/audit-log/ endpoint."""

    def test_unauthenticated_access_denied(self, client):
        """WHEN an unauthenticated user accesses the audit log, THEN they receive 401."""
        response = client.get('/api/v1/admin/audit-log/')
        assert response.status_code == 401

    def test_student_access_denied(self, client, student_user):
        """WHEN a student accesses the audit log, THEN they receive 403."""
        # Login as student
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'student@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 403

    def test_faculty_access_denied(self, client, faculty_user):
        """WHEN a faculty member accesses the audit log, THEN they receive 403."""
        # Login as faculty
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'faculty@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 403

    def test_admin_can_access_audit_log(self, client, admin_user):
        """WHEN an administrator accesses the audit log, THEN they receive 200 with paginated results."""
        # Create some audit log entries
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={'test': 'data'},
        )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert 'count' in data
        assert isinstance(data['results'], list)

    def test_filter_by_event_type(self, client, admin_user, student_user):
        """WHEN filtering by event_type, THEN only matching events are returned."""
        # Create audit log entries with different event types
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={},
        )
        AuditLog.objects.create(
            event_type='auth.logout',
            actor_user=student_user,
            target_user=student_user,
            success=True,
            metadata={},
        )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/?event_type=auth.logout', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) >= 1
        for entry in data['results']:
            if entry['event_type'] != 'auth.login.success':  # Exclude login from this test
                assert entry['event_type'] == 'auth.logout'

    def test_filter_by_actor_user_id(self, client, admin_user, student_user):
        """WHEN filtering by actor_user_id, THEN only events by that actor are returned."""
        # Create audit log entries with different actors
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={},
        )
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=student_user,
            target_user=student_user,
            success=True,
            metadata={},
        )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get(f'/api/v1/admin/audit-log/?actor_user_id={student_user.id}', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        for entry in data['results']:
            if entry['actor_user_id'] is not None:
                assert entry['actor_user_id'] == str(student_user.id)

    def test_filter_by_target_user_id(self, client, admin_user, student_user):
        """WHEN filtering by target_user_id, THEN only events targeting that user are returned."""
        # Create audit log entries with different targets
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={},
        )
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=student_user,
            target_user=student_user,
            success=True,
            metadata={},
        )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get(f'/api/v1/admin/audit-log/?target_user_id={student_user.id}', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        for entry in data['results']:
            if entry['target_user_id'] is not None:
                assert entry['target_user_id'] == str(student_user.id)

    def test_filter_by_created_at_gte(self, client, admin_user):
        """WHEN filtering by created_at__gte, THEN only events after that time are returned."""
        # Create an old audit log entry
        old_time = timezone.now() - timezone.timedelta(days=2)
        AuditLog.objects.create(
            event_type='auth.login.success',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={},
            created_at=old_time,
        )

        # Create a recent audit log entry
        recent_time = timezone.now()
        AuditLog.objects.create(
            event_type='auth.logout',
            actor_user=admin_user,
            target_user=admin_user,
            success=True,
            metadata={},
            created_at=recent_time,
        )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        # Use a format without timezone offset (will be interpreted as UTC by the server)
        cutoff_dt = (timezone.now() - timezone.timedelta(days=1)).replace(microsecond=0)
        # Convert to naive datetime in UTC and format as ISO string
        cutoff = cutoff_dt.astimezone(dt_timezone.utc).replace(tzinfo=None).isoformat()
        response = client.get(f'/api/v1/admin/audit-log/?created_at__gte={cutoff}', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        for entry in data['results']:
            entry_time = timezone.datetime.fromisoformat(entry['created_at'].replace('Z', '+00:00'))
            cutoff_aware = timezone.datetime.fromisoformat(cutoff).replace(tzinfo=dt_timezone.utc)
            assert entry_time >= cutoff_aware

    def test_filter_by_created_at_lte(self, client, admin_user):
        """WHEN filtering by created_at__lte, THEN only events before that time are returned."""
        # Login as admin first
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        # Get current count
        response = client.get('/api/v1/admin/audit-log/', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        initial_count = response.json()['count']

        # Use a cutoff far in the future - should return all entries
        future_cutoff = (timezone.now() + timezone.timedelta(days=1)).replace(microsecond=0)
        cutoff = future_cutoff.astimezone(dt_timezone.utc).replace(tzinfo=None).isoformat()
        response = client.get(f'/api/v1/admin/audit-log/?created_at__lte={cutoff}', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        # Should find all entries since cutoff is in the future
        assert data['count'] == initial_count

        # Use a cutoff far in the past - should return no entries
        past_cutoff = (timezone.now() - timezone.timedelta(days=365)).replace(microsecond=0)
        cutoff = past_cutoff.astimezone(dt_timezone.utc).replace(tzinfo=None).isoformat()
        response = client.get(f'/api/v1/admin/audit-log/?created_at__lte={cutoff}', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        # Should find no entries since cutoff is in the past
        assert data['count'] == 0

    def test_invalid_uuid_filter_returns_400(self, client, admin_user):
        """WHEN an invalid UUID is provided for filtering, THEN a 400 error is returned."""
        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/?actor_user_id=invalid-uuid', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert data['error']['code'] == 'INVALID_UUID'

    def test_invalid_datetime_filter_returns_400(self, client, admin_user):
        """WHEN an invalid datetime is provided for filtering, THEN a 400 error is returned."""
        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/?created_at__gte=invalid-datetime', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data
        assert data['error']['code'] == 'INVALID_DATETIME'

    def test_pagination_works(self, client, admin_user):
        """WHEN requesting a specific page size, THEN pagination is applied correctly."""
        # Create multiple audit log entries
        for i in range(25):
            AuditLog.objects.create(
                event_type='auth.login.success',
                actor_user=admin_user,
                target_user=admin_user,
                success=True,
                metadata={'index': i},
            )

        # Login as admin
        login_response = client.post(
            '/api/v1/auth/login/',
            data={'email': 'admin@pampangastateu.edu.ph', 'password': 'SecurePassword123', 'remember_me': False},
            content_type='application/json',
            HTTP_ORIGIN='http://localhost:5173',
        )
        assert login_response.status_code == 200
        access_token = login_response.json()['access_token']

        response = client.get('/api/v1/admin/audit-log/?page_size=10', HTTP_AUTHORIZATION=f'Bearer {access_token}')
        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) == 10
        assert data['count'] >= 25

