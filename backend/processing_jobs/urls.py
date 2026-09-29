from django.urls import path

from .views import JobStatusView

urlpatterns = [path('<uuid:job_id>/', JobStatusView.as_view(), name='processing-job-status')]
