"""Management command — backfill / regenerate SBERT embeddings.

Usage:
    python manage.py embed_theses                            # fill missing composite
    python manage.py embed_theses --regenerate               # re-embed every thesis
    python manage.py embed_theses --titles-only              # fill missing title vectors
    python manage.py embed_theses --titles-only --regenerate # re-embed every title

Loads the SBERT model once and processes the entire corpus in one
process — fast for the demo-scale repository (~15 records).

``--titles-only`` swaps both the selection predicate and the generator, so
it writes ``title_embedding`` / ``title_embedding_generated_at`` and leaves
the composite embedding columns untouched (and vice versa). The two flags
are orthogonal.

Note: the plain ``--titles-only`` pass selects rows with no stored title
vector at all. It does not detect a vector that has gone stale because the
title was edited afterwards — use ``--titles-only --regenerate`` to refresh
the whole corpus.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from theses.models import Thesis
from theses.services.semantic_search import (
    MODEL_NAME,
    generate_thesis_embedding,
    generate_title_embedding,
)


class Command(BaseCommand):
    help = 'Generate SBERT embeddings for theses (backfill missing or regenerate all).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Re-embed every thesis (default: only those without an embedding).',
        )
        parser.add_argument(
            '--titles-only',
            action='store_true',
            help=(
                'Generate only Thesis.title_embedding (skip the composite '
                'embedding). Used to backfill review-time redundancy analysis.'
            ),
        )

    def handle(self, *args, **options):
        regenerate = options.get('regenerate', False)
        titles_only = options.get('titles_only', False)

        if titles_only:
            generator = generate_title_embedding
            missing_filter = {'title_embedding__isnull': True}
            label = 'title embeddings'
        else:
            generator = generate_thesis_embedding
            missing_filter = {'embedding_vector__isnull': True}
            label = 'embeddings'

        if regenerate:
            qs = Thesis.objects.all().order_by('created_at')
            self.stdout.write(self.style.WARNING(
                f'Regenerating {label} for ALL {qs.count()} theses '
                f'using {MODEL_NAME}...'
            ))
        else:
            qs = Thesis.objects.filter(**missing_filter).order_by('created_at')
            self.stdout.write(self.style.NOTICE(
                f'Embedding {qs.count()} theses missing {label} using {MODEL_NAME}...'
            ))

        ok = 0
        failed = 0
        for thesis in qs:
            try:
                generator(thesis)
                ok += 1
                self.stdout.write(f'  ✓ {thesis.title[:60]}')
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  ✗ {thesis.title[:60]} — {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Done — {ok} embedded, {failed} failed.'
        ))
