"""HTTP views for the audit app.

Administrator surface (gated by ``IsAdministrator``):
* ``GET /api/v1/admin/audit-log/`` — paginated, filterable audit log list
"""

from __future__ import annotations

import uuid
from datetime import datetime

from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from common.errors import make_error_response

from .models import AuditLog
from .serializers import AuditLogSerializer


class _AuditLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AuditLogListView(APIView):
    """``GET /api/v1/admin/audit-log/?event_type=...&actor_user_id=...&target_user_id=...&created_at__gte=...&created_at__lte=...&page=...&page_size=...``

    Restricted to administrators. Returns paginated audit log entries with optional filters.
    """

    permission_classes = [IsAdministrator]

    def get(self, request, *args, **kwargs):
        qs = AuditLog.objects.all().order_by('-created_at')

        # Filter by event_type
        event_type = request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)

        # Filter by actor_user_id
        actor_user_id = request.query_params.get('actor_user_id')
        if actor_user_id:
            try:
                actor_uuid = uuid.UUID(actor_user_id)
                qs = qs.filter(actor_user_id=actor_uuid)
            except (ValueError, TypeError):
                return make_error_response(
                    code='INVALID_UUID',
                    message='actor_user_id must be a valid UUID.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filter by target_user_id
        target_user_id = request.query_params.get('target_user_id')
        if target_user_id:
            try:
                target_uuid = uuid.UUID(target_user_id)
                qs = qs.filter(target_user_id=target_uuid)
            except (ValueError, TypeError):
                return make_error_response(
                    code='INVALID_UUID',
                    message='target_user_id must be a valid UUID.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filter by created_at__gte
        created_at_gte = request.query_params.get('created_at__gte')
        if created_at_gte:
            try:
                # Use datetime.fromisoformat which handles ISO 8601 formats better
                parsed = datetime.fromisoformat(created_at_gte)
                # Ensure the datetime is timezone-aware
                if django_timezone.is_naive(parsed):
                    parsed = django_timezone.make_aware(parsed)
                qs = qs.filter(created_at__gte=parsed)
            except (ValueError, TypeError):
                return make_error_response(
                    code='INVALID_DATETIME',
                    message='created_at__gte must be a valid ISO 8601 datetime.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Filter by created_at__lte
        created_at_lte = request.query_params.get('created_at__lte')
        if created_at_lte:
            try:
                # Use datetime.fromisoformat which handles ISO 8601 formats better
                parsed = datetime.fromisoformat(created_at_lte)
                # Ensure the datetime is timezone-aware
                if django_timezone.is_naive(parsed):
                    parsed = django_timezone.make_aware(parsed)
                qs = qs.filter(created_at__lte=parsed)
            except (ValueError, TypeError):
                return make_error_response(
                    code='INVALID_DATETIME',
                    message='created_at__lte must be a valid ISO 8601 datetime.',
                    status=status.HTTP_400_BAD_REQUEST,
                )

        paginator = _AuditLogPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = AuditLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
