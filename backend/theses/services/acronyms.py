"""Acronym glossary shared by Repository search and Title Similarity.

The search model (all-MiniLM-L6-v2) splits "iot" into "io" + "##t" and has
no idea that IoT means Internet of Things, so the two spellings of the same
query rank theses differently. This module makes them one query:

* ``expand_query(q)`` - the query plus each variant with one glossary term
  swapped for its other form ("IoT-based cart" -> "internet of things based
  cart"). Semantic ranking scores every variant and keeps the best.
* ``glossary_term_variants(q)`` - both forms when the WHOLE query is one
  glossary term. Only such term searches get the lexical term-match rescue.
* ``count_mentions(text, q)`` - whole-word mentions of the term in either
  form, used to decide whether a thesis is actually about the term.

Rules
-----
* Case-insensitive, except acronyms that are also ordinary words ("IT",
  "AR", "IS", "POS", "ML"): those count only in capitals, in the query and in
  the text, so "is it working" is not about information technology.
* Whole words only: "iot" never matches "patriot". Hyphens and dashes read
  as spaces, so "IoT-based" and "internet-of-things" both count.
* A trailing "s" is accepted on either form ("BHWs", "barangay health
  workers").

Add terms to ``GLOSSARY`` by review. ``manage.py list_acronym_candidates``
lists "Long Form (ACR)" pairs found in approved theses that are not here yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional


@dataclass(frozen=True)
class Term:
    acronym: str        # canonical spelling, e.g. "IoT"
    long_form: str      # lowercase, e.g. "internet of things"
    case_sensitive: bool = False

    @cached_property
    def acronym_re(self) -> 're.Pattern[str]':
        flags = 0 if self.case_sensitive else re.IGNORECASE
        body = re.escape(self.acronym.upper() if self.case_sensitive else self.acronym)
        return re.compile(rf'(?<![\w]){body}(s?)(?![\w])', flags)

    @cached_property
    def long_form_re(self) -> 're.Pattern[str]':
        words = [re.escape(w) for w in self.long_form.split()]
        return re.compile(r'(?<![\w])' + _SEP.join(words) + r'(s?)(?![\w])', re.IGNORECASE)


# Hyphens, dashes and whitespace all separate words.
_SEP = r'[\s\-‐-―−]+'
_SEP_RE = re.compile(_SEP)


GLOSSARY: tuple = (
    # Technology
    Term('IoT', 'internet of things'),
    Term('AI', 'artificial intelligence'),
    Term('AR', 'augmented reality', case_sensitive=True),
    Term('VR', 'virtual reality'),
    Term('OCR', 'optical character recognition'),
    Term('NLP', 'natural language processing'),
    Term('GPS', 'global positioning system'),
    Term('SMS', 'short message service'),
    Term('QR', 'quick response'),
    Term('RFID', 'radio frequency identification'),
    Term('SQL', 'structured query language'),
    Term('OTP', 'one time password'),
    Term('BERT', 'bidirectional encoder representations from transformers'),
    Term('SBERT', 'sentence bert'),
    Term('ML', 'machine learning', case_sensitive=True),
    Term('DL', 'deep learning', case_sensitive=True),
    Term('CNN', 'convolutional neural network'),
    Term('LLM', 'large language model'),
    Term('GIS', 'geographic information system'),
    Term('POS', 'point of sale', case_sensitive=True),
    Term('UI', 'user interface'),
    Term('UX', 'user experience'),
    Term('API', 'application programming interface'),
    Term('HCI', 'human computer interaction'),
    Term('PWA', 'progressive web app'),
    Term('CMS', 'content management system'),
    Term('LMS', 'learning management system'),
    Term('RPG', 'role playing game'),
    Term('SDLC', 'software development life cycle'),
    Term('RAD', 'rapid application development', case_sensitive=True),
    Term('IT', 'information technology', case_sensitive=True),
    Term('IS', 'information system', case_sensitive=True),
    Term('CS', 'computer science', case_sensitive=True),
    Term('ICT', 'information and communications technology'),
    Term('GUI', 'graphical user interface'),
    Term('IDE', 'integrated development environment'),
    Term('UML', 'unified modeling language'),
    Term('ERD', 'entity relationship diagram'),
    Term('DFD', 'data flow diagram'),
    Term('UAT', 'user acceptance testing'),
    Term('TAM', 'technology acceptance model', case_sensitive=True),
    # Local government and school offices named in the corpus
    Term('MSWDO', 'municipal social welfare and development office'),
    Term('MSWD', 'municipal social welfare and development'),
    Term('CGMS', 'complaints and grievances management system'),
    Term('HTE', 'host training establishment'),
    Term('PSMO', 'procurement and supply management office'),
    Term('OSA', 'office of student affairs', case_sensitive=True),
    Term('GWA', 'general weighted average'),
    Term('WHO', 'world health organization', case_sensitive=True),
    Term('PSU', 'pampanga state university'),
    Term('BHW', 'barangay health worker'),
    Term('RHU', 'rural health unit'),
    Term('OSCA', 'office for senior citizens affairs'),
    Term('AICS', 'assistance to individuals in crisis situations'),
    Term('LGU', 'local government unit'),
    Term('PWD', 'person with disability'),
    Term('CCS', 'college of computing studies'),
    Term('DHVSU', 'don honorio ventura state university'),
)


# Full-text mentions count only when frequent AND dense. A thesis that uses a
# technology names it throughout (the fuzzy-logic farming app: 9 IoT mentions
# in 43k characters); one that only cites it in the literature review spreads
# a few mentions across a long document (APPOKO: 5 in 226k). Measured on the
# approved corpus, 1 per 10,000 characters separates the two.
FULL_TEXT_MIN_MENTIONS = 3
FULL_TEXT_MIN_PER_10K_CHARS = 1.0


def _clean(query: str) -> str:
    """Hyphens and dashes as spaces, whitespace collapsed; case kept."""
    return _SEP_RE.sub(' ', query or '').strip()


def _whole_term(query: str) -> Optional[Term]:
    """The glossary term the entire query spells, in either form."""
    q = _clean(query)
    if not q:
        return None
    for term in GLOSSARY:
        for pattern in (term.acronym_re, term.long_form_re):
            m = pattern.fullmatch(q)
            if m:
                return term
    return None


def expand_query(query: str) -> List[str]:
    """The query first, then one variant per glossary term it mentions."""
    original = (query or '').strip()
    if not original:
        return []
    base = _clean(original)
    variants = [original]
    for term in GLOSSARY:
        swapped = term.acronym_re.sub(lambda m: term.long_form + m.group(1), base)
        if swapped == base:
            swapped = term.long_form_re.sub(lambda m: term.acronym.lower() + m.group(1), base)
        if swapped != base:
            variant = swapped.lower()
            if variant not in (v.lower() for v in variants):
                variants.append(variant)
    return variants


def glossary_term_variants(query: str) -> List[str]:
    """Both forms, lowercase, when the whole query is one glossary term."""
    term = _whole_term(query)
    if term is None:
        return []
    return [term.acronym.lower(), term.long_form]


def count_mentions(text: Optional[str], query: str) -> int:
    """Whole-word mentions of the query's glossary term, in either form."""
    term = _whole_term(query)
    if term is None or not text:
        return 0
    return len(term.acronym_re.findall(text)) + len(term.long_form_re.findall(text))


def is_about_term(query: str, *, head: str, full_text: Optional[str]) -> bool:
    """Whether a thesis is about the query's glossary term.

    ``head`` is the short metadata (keywords + abstract): one mention counts.
    ``full_text`` needs ``FULL_TEXT_MIN_MENTIONS`` at a density of at least
    ``FULL_TEXT_MIN_PER_10K_CHARS``, to rule out passing mentions and citations.
    """
    if count_mentions(head, query) > 0:
        return True
    mentions = count_mentions(full_text, query)
    if mentions < FULL_TEXT_MIN_MENTIONS:
        return False
    return mentions * 10_000 / len(full_text) >= FULL_TEXT_MIN_PER_10K_CHARS
