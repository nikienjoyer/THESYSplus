import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from processing_jobs.models import ProcessingJob
from processing_jobs.services import claim_next, remove_job_file, remove_uncommitted_thesis_file
from processing_jobs.worker import run_one


class Command(BaseCommand):
    help = 'Run one durable document-processing worker. Start once per deployment.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        last_cleanup = 0
        while True:
            close_old_connections()
            if time.monotonic() - last_cleanup > 3600:
                expired = ProcessingJob.objects.filter(
                    state__in=[ProcessingJob.State.SUCCEEDED, ProcessingJob.State.FAILED],
                    expires_at__lt=timezone.now(),
                )[:100]
                for old_job in list(expired):
                    remove_uncommitted_thesis_file(old_job)
                    remove_job_file(old_job)
                    old_job.delete()
                last_cleanup = time.monotonic()
            job = claim_next()
            if job is None:
                # Expired abandoned jobs and stale private uploads are pruned
                # only after they have reached a terminal state.
                if options['once']:
                    return
                time.sleep(2)
                continue
            run_one(job)
            if options['once']:
                return
