"""List "Long Form (ACR)" pairs in approved theses that the glossary lacks.

Read-only. Review the output and add real terms to
``theses/services/acronyms.py`` ``GLOSSARY`` by hand - the glossary is curated,
never filled automatically, because an acronym can mean different things.

    python manage.py list_acronym_candidates
"""

import re
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from theses.models import Thesis, ThesisStatus
from theses.services.acronyms import GLOSSARY

_PAIR_RE = re.compile(r'((?:[A-Za-z][\w-]*\s+){0,7}[A-Za-z][\w-]*)\s*\(([A-Z][A-Za-z0-9]{1,7})\)')
_SKIP = {'of', 'and', 'the', 'for', 'to', 'in', 'a', 'an', 'with', 'on', 'at', 'by'}


def _long_form(words, acronym):
    """The shortest run of trailing words whose initials spell the acronym."""
    letters = re.sub(r'[^a-z]', '', acronym.lower())
    for k in range(1, len(words) + 1):
        run = words[-k:]
        if run[0].lower() in _SKIP:
            continue
        initials = ''.join(w[0].lower() for w in run if w.lower() not in _SKIP)
        if initials == letters:
            return ' '.join(run).lower()
    return None


class Command(BaseCommand):
    help = 'List acronym/long-form pairs found in approved theses but missing from the glossary.'

    def handle(self, *args, **options):
        known = {t.acronym.lower() for t in GLOSSARY}
        found = defaultdict(Counter)
        for title, abstract, keywords, text in (
            Thesis.objects.filter(status=ThesisStatus.APPROVED)
            .values_list('title', 'abstract', 'keywords', 'extracted_text')
        ):
            kws = ' ; '.join(k for k in (keywords or []) if isinstance(k, str))
            for m in _PAIR_RE.finditer(' \n'.join([title or '', abstract or '', kws, text or ''])):
                acronym = m.group(2)
                if acronym.lower() in known:
                    continue
                long_form = _long_form(m.group(1).split(), acronym)
                if long_form:
                    found[acronym][long_form] += 1

        if not found:
            self.stdout.write('No new acronym pairs found.')
            return
        for acronym, forms in sorted(found.items(), key=lambda kv: -sum(kv[1].values())):
            listed = ' | '.join(f'{form} ({n})' for form, n in forms.most_common(3))
            self.stdout.write(f'{acronym:10} {sum(forms.values()):3}x  {listed}')
