import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ProcessingJob(models.Model):
    class Kind(models.TextChoices):
        TITLE = 'title', 'Title extraction'
        METADATA = 'metadata', 'Metadata extraction'
        THESIS = 'thesis', 'Thesis upload'
        IDENTITY = 'identity', 'Identity verification'

    class State(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    access_request_id = models.UUIDField(null=True, blank=True)
    private_file_path = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=['state', 'lease_until', 'created_at'])]
