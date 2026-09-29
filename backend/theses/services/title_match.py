"""Case-insensitive exact title / name matching shared by the Repository
search and Title Similarity.

SBERT scores a one-word name such as ``thesix`` far below a long title that
contains it, so semantic ranking alone cannot tell "this is the study called
Thesix" from noise. This module supplies the lexical signal: does the query
appear in a title as whole words, and is the query specific enough for that
to mean something?

Rules
-----
* Comparison is on ``normalize_title`` output: NFKC, case-folded, hyphens and
  dashes read as spaces, whitespace collapsed. Other punctuation is kept, so
  ``THESYS+`` still differs from ``THESYS``.
* A query matches a title when it appears in it as whole words or a phrase,
  never inside a longer word (``thesix`` does not match "Thesixty").
* A query is specific enough when ANY of:
    1. it equals the whole title, or the title's name segment (the text
       before the first ``:`` or spaced/long dash) - checked per title;
    2. it contains punctuation other than hyphens;
    3. it has two or more words;
    4. it is one word of at least ``MIN_SINGLE_WORD_LENGTH`` characters that
       appears as a whole word in at most ``TITLE_MATCH_MAX_TITLES`` titles of
       the reference corpus. This replaces the old ALL-CAPS rule: ``rfid``,
       ``Rfid`` and ``RFID`` behave identically, while words such as
       "system" or "web" never qualify in any casing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable, Optional, Union

# A single word is a title match only if this rare in the corpus.
TITLE_MATCH_MAX_TITLES = 3
MIN_SINGLE_WORD_LENGTH = 3

_DASHES = '‐‑‒–—―−'
_HYPHEN_RE = re.compile(f'[-{_DASHES}]')
_SPACE_RE = re.compile(r'\s+')
# Colon, spaced hyphen/dash, or a long dash ends the "name" of a title:
# "Thesix: Centralized ..." and "Thesix - Centralized ..." both name "Thesix"
# but the hyphen in "Web-Based" does not.
_NAME_SEPARATOR_RE = re.compile(r':|\s[-‐-―−]+\s|[–—―]')


def normalize_title(text: str) -> str:
    """Fold ``text`` to the form used for title comparison."""
    text = unicodedata.normalize('NFKC', text or '').casefold()
    text = _HYPHEN_RE.sub(' ', text)
    return _SPACE_RE.sub(' ', text).strip()


def title_name_segment(title: str) -> str:
    """The name part of a title: text before the first ':' or dash separator."""
    return _NAME_SEPARATOR_RE.split(title or '', maxsplit=1)[0]


def _whole_word_pattern(normalized_query: str) -> 're.Pattern[str]':
    return re.compile(rf'(?<!\w){re.escape(normalized_query)}(?!\w)')


def _has_punctuation(normalized_query: str) -> bool:
    return any(not ch.isalnum() and not ch.isspace() for ch in normalized_query)


CorpusTitles = Union[Iterable[str], Callable[[], Iterable[str]]]


class TitleMatcher:
    """A query prepared once per request, then tested against many titles.

    ``corpus_titles`` is only read for the rarity rule (a single plain word),
    so it may be a zero-argument callable that is not invoked otherwise.
    """

    def __init__(self, query: str, corpus_titles: Optional[CorpusTitles] = None):
        self.query = normalize_title(query)
        self._pattern = _whole_word_pattern(self.query) if self.query else None
        self.qualifies = self._qualifies(corpus_titles)

    def _qualifies(self, corpus_titles: Optional[CorpusTitles]) -> bool:
        q = self.query
        if not q:
            return False
        if _has_punctuation(q):
            return True
        if ' ' in q:
            return True
        if len(q) < MIN_SINGLE_WORD_LENGTH or corpus_titles is None:
            return False
        titles = corpus_titles() if callable(corpus_titles) else corpus_titles
        count = 0
        for title in titles:
            if self._pattern.search(normalize_title(title)):
                count += 1
                if count > TITLE_MATCH_MAX_TITLES:
                    return False
        return True

    def matches(self, title: str) -> bool:
        if not self.query:
            return False
        normalized = normalize_title(title)
        if normalized == self.query:
            return True
        if normalize_title(title_name_segment(title)) == self.query:
            return True
        return self.qualifies and bool(self._pattern.search(normalized))


def build_title_matcher(query: str, corpus_titles: Optional[CorpusTitles] = None) -> TitleMatcher:
    """Precompute the query's qualification once; call ``.matches(title)`` per thesis."""
    return TitleMatcher(query, corpus_titles)


def is_title_match(query: str, title: str, corpus_titles: Optional[CorpusTitles] = None) -> bool:
    """One-off convenience wrapper; prefer ``build_title_matcher`` in loops."""
    return TitleMatcher(query, corpus_titles).matches(title)
