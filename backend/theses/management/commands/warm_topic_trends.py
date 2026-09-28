"""Precompute the default Topic Trend result before the first page visit."""

from django.core.management.base import BaseCommand

from theses.services.cached_topic_trends import get_topic_trends_data


class Command(BaseCommand):
    help = 'Warm the shared Topic Trend cache for the current approved corpus.'

    def handle(self, *args, **options):
        result = get_topic_trends_data()
        self.stdout.write(self.style.SUCCESS(
            f"Topic trends ready: {result['total_theses']} approved theses, "
            f"{result['total_topics']} clusters."
        ))
