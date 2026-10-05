"""Find repository theses cited in a thesis's reference list.

Two signals, strongest first:
  title        — the cited thesis's title (first 8 words, at least 4) appears in
                 the references text after normalising case and punctuation.
  author_year  — the cited thesis's first-author surname (4+ characters) and
                 its year appear on the same reference line.
Only approved theses are candidates. The uploader confirms which are real.
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


def _surname(thesis: Thesis) -> str:
    first = (thesis.authors or [''])[0]
    return _norm(first.split(',')[0])


def find_cited_theses(text: str, exclude_id=None) -> list[dict]:
    refs = references_section(text)
    if not refs.strip():
        return []
    refs_norm = f' {_norm(refs)} '
    lines = [f' {_norm(line)} ' for line in refs.splitlines()]

    # ponytail: scans every approved thesis per upload; fine at hundreds of theses.
    candidates = Thesis.objects.filter(status=ThesisStatus.APPROVED).only('id', 'title', 'year', 'authors')
    if exclude_id:
        candidates = candidates.exclude(id=exclude_id)

    found = []
    for thesis in candidates.order_by('title'):
        words = _norm(thesis.title).split()
        if len(words) >= 4 and f" {' '.join(words[:8])} " in refs_norm:
            match = 'title'
        else:
            surname, year = _surname(thesis), str(thesis.year)
            if len(surname) < 4 or not any(f' {surname} ' in line and f' {year} ' in line for line in lines):
                continue
            match = 'author_year'
        found.append({'id': str(thesis.id), 'title': thesis.title, 'year': thesis.year, 'match': match})
    return found
