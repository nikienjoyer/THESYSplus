"""Find citations between theses already in the repository.

Dry run by default: prints every candidate. ``--apply`` stores title matches
only: there is no uploader to confirm the weaker author-year matches.
"""

from django.core.management.base import BaseCommand

from theses.models import Thesis, ThesisCitation, ThesisStatus
from theses.services.citations import find_cited_theses


class Command(BaseCommand):
    help = 'Detect citations between existing approved theses (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Store title matches.')

    def handle(self, *args, apply=False, **options):
        title_matches = 0
        for thesis in Thesis.objects.filter(status=ThesisStatus.APPROVED).exclude(extracted_text=''):
            for cand in find_cited_theses(thesis.extracted_text, exclude_id=thesis.id):
                self.stdout.write(f'{cand["match"]:11} {thesis.title[:50]!r} -> {cand["title"][:50]!r}')
                if cand['match'] == 'title':
                    title_matches += 1
                    if apply:
                        ThesisCitation.objects.get_or_create(citing=thesis, cited_id=cand['id'])
        verb = 'Stored' if apply else 'Would store (run with --apply)'
        self.stdout.write(self.style.SUCCESS(f'{verb}: {title_matches} title match(es).'))
