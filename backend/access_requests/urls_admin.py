"""Admin URL configuration for the ``access_requests`` app.

Mounted at ``/api/v1/admin/`` by the root URLConf. Every endpoint here is
gated by ``IsAdministrator``.
"""

from django.urls import path

from .views import (
    AccessRequestListView,
    ApproveAccessRequestView,
    DenyAccessRequestView,
)


urlpatterns = [
    path('access-requests/', AccessRequestListView.as_view(),
         name='admin-access-request-list'),
    path('access-requests/<str:id>/approve/', ApproveAccessRequestView.as_view(),
         name='admin-access-request-approve'),
    path('access-requests/<str:id>/deny/', DenyAccessRequestView.as_view(),
         name='admin-access-request-deny'),
]
