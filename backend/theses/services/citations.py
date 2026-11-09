"""Find repository theses cited in a thesis's reference list.

One signal: the cited thesis's whole title (at least 4 words) appears in the
references text after normalising case and punctuation. Only approved theses
are candidates. Matches are saved without anyone confirming them, so the rule
stays strict: a reference that drops a subtitle is missed rather than guessed.
"""

from __future__ import annotations

import re

from theses.models import Thesis, ThesisStatus

_HEADING = re.compile(r'(?im)^\s*(references|bibliography|literature cited)\s*$')
_NON_WORD = re.compile(r'[^a-z0-9 ]+')


def _norm(text: str) -> str:
    return ' '.join(_NON_WORD.sub(' ', (text or '').lower()).split())


def references_section(text: str) -> str:
    """Text after the LAST references heading (a table of contents can list one
    earlier); the final 20% of the text when there is no heading."""
    text = text or ''
    headings = list(_HEADING.finditer(text))
    if headings:
        return text[headings[-1].end():]
    return text[int(len(text) * 0.8):]


def find_cited_theses(text: str, exclude_id=None) -> list[dict]:
    refs = references_section(text)
    if not refs.strip():
        return []
    refs_norm = f' {_norm(refs)} '

    # ponytail: scans every approved thesis per upload; fine at hundreds of theses.
    candidates = Thesis.objects.filter(status=ThesisStatus.APPROVED).only('id', 'title', 'year')
    if exclude_id:
        candidates = candidates.exclude(id=exclude_id)

    found = []
    for thesis in candidates.order_by('title'):
        words = _norm(thesis.title).split()
        if len(words) >= 4 and f" {' '.join(words)} " in refs_norm:
            found.append({'id': str(thesis.id), 'title': thesis.title, 'year': thesis.year})
    return found
