"""Find repository theses cited in a thesis's reference list.

One signal: the cited thesis's whole title (at least 4 words) appears in the
references, ignoring case, punctuation, ligatures and accents, and it stands
as a whole reference title: it starts after a year or closing quote (or at a
line start) and ends at a full stop, comma, quote, bracket or line end.
Approved and pending theses are candidates; rejected ones never are. Matches
are saved without anyone confirming them, so the rule stays strict.
"""

from __future__ import annotations

import re
import unicodedata

from theses.models import Thesis, ThesisStatus

_HEADING = re.compile(r'(?im)^\s*(references|bibliography|literature cited)\s*$')
_NON_WORD = re.compile(r'[^a-z0-9 ]+')
_QUOTES = '"\'“”‘’'


def _fold(text: str) -> str:
    """Lowercase, with ligatures split ('ﬁ' -> 'fi') and accents dropped."""
    decomposed = unicodedata.normalize('NFKD', text or '')
    return ''.join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _norm(text: str) -> str:
    return ' '.join(_NON_WORD.sub(' ', _fold(text)).split())


PREFIX_WORDS = 8


def _title_pattern(words: list[str]) -> re.Pattern:
    """The whole title, or at least its first PREFIX_WORDS words when the
    reference title ends right there (stored titles can keep a cover-page
    line such as "A Sample Undergraduate Thesis Manuscript")."""
    # ponytail: a longer reference title that line-wraps exactly where a
    # shorter repository title ends still matches; rare, tighten if seen.
    sep = '[^a-z0-9]+'
    tail = ''
    for word in reversed(words[PREFIX_WORDS:]):
        tail = f'(?:{sep}{re.escape(word)}{tail})?'
    head = sep.join(map(re.escape, words[:PREFIX_WORDS]))
    start = rf'(?:^|[.){_QUOTES}])[^a-z0-9\n]*'
    end = rf'(?=[ \t]*(?:[.?!,\[{_QUOTES}]|$))'
    return re.compile(start + head + tail + end, re.MULTILINE)


def references_section(text: str) -> str:
    """Text after the LAST references heading (a table of contents can list one
    earlier); the final 20% of the text when there is no heading."""
    text = text or ''
    headings = list(_HEADING.finditer(text))
    if headings:
        return text[headings[-1].end():]
    return text[int(len(text) * 0.8):]


def find_cited_theses(text: str, exclude_id=None) -> list[dict]:
    refs = _fold(references_section(text))
    if not refs.strip():
        return []

    # Pending theses count too: the citation is saved now and only shows under
    # "Cited by" once both theses are approved. Rejected theses never count.
    # ponytail: scans every candidate per upload; fine at hundreds of theses.
    candidates = (
        Thesis.objects.filter(status__in=[ThesisStatus.APPROVED, ThesisStatus.PENDING_REVIEW])
        .only('id', 'title', 'year', 'status', 'uploaded_by_id')
    )
    if exclude_id:
        candidates = candidates.exclude(id=exclude_id)

    found = []
    for thesis in candidates.order_by('title'):
        words = _norm(thesis.title).split()
        if len(words) >= 4 and _title_pattern(words).search(refs):
            found.append({
                'id': str(thesis.id), 'title': thesis.title, 'year': thesis.year,
                'under_review': thesis.status != ThesisStatus.APPROVED,
                'uploaded_by_id': thesis.uploaded_by_id,
            })
    return found
