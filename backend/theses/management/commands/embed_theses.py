"""Management command — backfill / regenerate SBERT embeddings.

Usage:
    python manage.py embed_theses                # fill missing only
    python manage.py embed_theses --regenerate   # re-embed every thesis

Loads the SBERT model once and processes the entire corpus in one
process — fast for the demo-scale repository (~15 records).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from theses.models import Thesis
from theses.services.semantic_search import (
    MODEL_NAME,
    generate_thesis_embedding,
)


class Command(BaseCommand):
    help = 'Generate SBERT embeddings for theses (backfill missing or regenerate all).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Re-embed every thesis (default: only those without an embedding).',
        )

    def handle(self, *args, **options):
        regenerate = options.get('regenerate', False)

        if regenerate:
            qs = Thesis.objects.all().order_by('created_at')
            self.stdout.write(self.style.WARNING(
                f'Regenerating embeddings for ALL {qs.count()} theses '
                f'using {MODEL_NAME}...'
            ))
        else:
            qs = Thesis.objects.filter(embedding_vector__isnull=True).order_by('created_at')
            self.stdout.write(self.style.NOTICE(
                f'Embedding {qs.count()} theses missing embeddings using {MODEL_NAME}...'
            ))

        ok = 0
        failed = 0
        for thesis in qs:
            try:
                generate_thesis_embedding(thesis)
                ok += 1
                self.stdout.write(f'  ✓ {thesis.title[:60]}')
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  ✗ {thesis.title[:60]} — {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Done — {ok} embedded, {failed} failed.'
        ))
