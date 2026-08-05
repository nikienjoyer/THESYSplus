"""URL configuration for the ``audit`` app.

Administrator-only audit log read endpoint.
"""

from django.urls import path

from .views import AuditLogListView

urlpatterns = [
    path('audit-log/', AuditLogListView.as_view(), name='audit_log_list'),
]
