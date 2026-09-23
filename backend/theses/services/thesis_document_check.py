"""Gate non-thesis documents out of upload and title extraction.

WHY THIS EXISTS
---------------
A user uploaded a Certificate of Registration — a class-schedule table — to
Title Similarity. It was accepted, and the title extractor dutifully returned
the most title-like line it could find:

    "Bachelor of Science in Information Systems 4th Year SCHEDULE /
     ROOMSECTIONLec U N I TSUBJECT TITLECODE Lab Credit 303Data Mining…"

A similarity check then ran on that string and reported 38.1%, "Low Similarity
— sufficiently distinct". Every layer behaved correctly in isolation: the
extractor found the best candidate line in a document that simply has no
title. Nothing anywhere asked whether the file was a thesis.

The existing confidence signal would not have caught it either — the COR came
back at MEDIUM ("Please verify"), not LOW. A separate gate is the right layer.

WHY POSITIVE MARKERS, NOT A BLOCKLIST
-------------------------------------
The obvious fix — reject on SCHEDULE / ROOM / SECTION / UNIT / CREDIT — is
wrong, and would be a worse bug than the one it fixes. A thesis ABOUT
enrolment or scheduling contains exactly the same vocabulary as a Certificate
of Registration. This repository already holds "Scholarship Management In
Pampanga", "Alumni Portal Tracker" and "Web-Based Qualifying Examination"; an
enrolment-system thesis is a normal submission here, not an edge case. A
blocklist would refuse real theses, which is a more damaging failure than
accepting the occasional odd document.

So the test is inverted: look for STRUCTURE that a thesis manuscript has and a
form or a schedule does not. A COR scores zero on every marker below without
any word ever being blocklisted.

DELIBERATELY NOT REQUIRED: AN ABSTRACT
--------------------------------------
``metadata_extraction`` documents that the real THESYS+ thesis in this
repository has NO abstract heading anywhere in its 93 pages — verified by
scanning every page. Making an abstract mandatory would reject the project's
own manuscript. It is one marker among several, never a precondition.

REGEX REUSE
-----------
The heading definitions are imported READ-ONLY from
``metadata_extraction`` (``_ABSTRACT_HEADING``, ``_KEYWORDS_LABEL``,
``_CHAPTER_PATTERNS``, ``_FRONTMATTER_STOP``) rather than restated, so the two
modules cannot drift to different ideas of what a chapter heading looks like.
Where this module needs something the originals do not express — per-phrase
bucketing of title-page boilerplate, tolerance of "1. INTRODUCTION" numbering
— it adds that on top of the canonical matchers instead of replacing them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .metadata_extraction import (
    _ABSTRACT_HEADING,
    _CHAPTER_PATTERNS,
    _FRONTMATTER_STOP,
    _KEYWORDS_LABEL,
    collapse_whitespace,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# How many distinct structural markers a document must show.
#
# Two, not one: a single marker is reachable by accident — a stray line reading
# "Introduction" appears in plenty of non-thesis documents. Two independent
# markers is the point where a form or a schedule stops being able to qualify.
#
# Do not raise this without re-checking the whole corpus. Three would reject a
# standalone title page carrying only "A Capstone" and "Presented to the
# Faculty of", which is a legitimate Title Similarity upload — and the one
# document guaranteed to contain a clean, well-formed title.
MIN_MARKERS = 2

# Below this, the document is treated as UNREADABLE rather than as a non-thesis.
# A failed OCR pass and a Certificate of Registration are different problems
# and must not share an error message: one means "try a text-based PDF", the
# other means "upload a different document entirely". Reporting the wrong one
# sends the user down the wrong path.
#
# 200 chars mirrors ``text_extractor.PDF_TEXT_FALLBACK_THRESHOLD`` — the point
# at which that module already concludes a PDF has no usable text layer.
MIN_TEXT_CHARS = 200


# ---------------------------------------------------------------------------
# Additive patterns — things the reused regexes do not express
# ---------------------------------------------------------------------------

# Leading section numbering, stripped before a line is offered to
# ``_CHAPTER_PATTERNS``. That regex is anchored ``^...$``, so journal-style
# "1. INTRODUCTION" and "2.1 Methodology" never match it as written; this lets
# them through without loosening the canonical pattern for every other caller.
_LEADING_NUMBER = re.compile(r'^\s*\d+(?:\.\d+)*\s*[\.\)]?\s*')

# Roman-numeral section numbering ("I. INTRODUCTION"). The punctuation is
# required, so ordinary prose like "I am" is untouched.
_LEADING_ROMAN = re.compile(r'^\s*[IVXLCDM]+\s*[\.\)]\s+')

# "METHODS" as a standalone heading. ``_CHAPTER_PATTERNS`` covers "methodology"
# and "results and discussion" but not this shorter variant.
_METHODS_HEADING = re.compile(r'^methods?[\s\.\:\-]*$', re.IGNORECASE)

# The degree line that customarily sits on its own line directly beneath
# "In Partial Fulfillment" on a Philippine thesis title page. Not covered by
# ``_FRONTMATTER_STOP``, which anchors on the phrase's opening words.
_DEGREE_REQUIREMENTS = re.compile(
    r'^of\s+the\s+requirements?\s+for\s+the\s+degree\b',
    re.IGNORECASE,
)

# Headings that ``_CHAPTER_PATTERNS`` matches but which are NOT chapter
# markers here, because they are counted separately (or not at all). Without
# this, a lone "REFERENCES" line would score twice — once as a chapter heading
# and once as a references section — and clear the threshold on its own.
_NOT_A_CHAPTER = frozenset({
    'references', 'bibliography', 'appendix', 'abstract',
})

_REFERENCES_HEADING = re.compile(
    r'^(references?|bibliography|works\s+cited|literature\s+cited)[\s\.\:\-]*$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Marker identifiers — stable strings, surfaced to the user in error details
# ---------------------------------------------------------------------------

MARKER_ABSTRACT = 'abstract_heading'
MARKER_KEYWORDS = 'keywords_label'
MARKER_CHAPTERS = 'chapter_headings'
MARKER_REFERENCES = 'references_section'
MARKER_TITLE_PAGE_PRESENTED = 'title_page_presented_to'
MARKER_TITLE_PAGE_FULFILMENT = 'title_page_partial_fulfilment'
MARKER_TITLE_PAGE_DEGREE = 'title_page_degree_requirements'
MARKER_TITLE_PAGE_KIND = 'title_page_capstone_or_thesis'

# Human-readable labels for the error payload. A user with a genuinely
# odd-format thesis needs to see what WAS recognised, not just that it failed.
MARKER_LABELS = {
    MARKER_ABSTRACT: 'abstract heading',
    MARKER_KEYWORDS: 'keywords line',
    MARKER_CHAPTERS: 'chapter or section headings',
    MARKER_REFERENCES: 'references section',
    MARKER_TITLE_PAGE_PRESENTED: 'title page ("Presented to the Faculty of")',
    MARKER_TITLE_PAGE_FULFILMENT: 'title page ("In Partial Fulfillment")',
    MARKER_TITLE_PAGE_DEGREE: 'title page ("of the Requirements for the Degree")',
    MARKER_TITLE_PAGE_KIND: 'title page ("A Capstone" / "A Thesis")',
}

# Failure reasons — distinct so callers can word them differently.
REASON_OK = 'ok'
REASON_UNREADABLE = 'unreadable'
REASON_NOT_A_THESIS = 'not_a_thesis'


@dataclass
class ThesisDocumentCheck:
    """Outcome of the document-type gate."""

    passed: bool
    reason: str
    markers: list[str] = field(default_factory=list)

    @property
    def marker_count(self) -> int:
        return len(self.markers)

    @property
    def marker_labels(self) -> list[str]:
        """Found markers, in human-readable form, for an error payload."""
        return [MARKER_LABELS.get(m, m) for m in self.markers]


def _strip_section_numbering(line: str) -> str:
    """Remove leading "1.", "2.1", "IV)" style numbering from a heading."""
    without_roman = _LEADING_ROMAN.sub('', line)
    if without_roman != line:
        return without_roman.strip()
    return _LEADING_NUMBER.sub('', line).strip()


def _classify_title_page_phrase(line: str) -> str | None:
    """Return which distinct title-page phrase ``line`` is, if any.

    PER-PHRASE, NOT PER-DOCUMENT. Each distinct phrase counts as its own
    marker. This is what lets a standalone title page — title, authors,
    "A Capstone", "Presented to the Faculty of" — reach the threshold and be
    accepted for Title Similarity. Collapsing all boilerplate into one shared
    marker would score that page 1 and reject it, even though it is the single
    most reliable source of a clean title there is.

    A Certificate of Registration contains none of these phrases, so the
    looser counting costs nothing in precision.

    The decision of what counts as boilerplate stays with
    ``_FRONTMATTER_STOP``; this only reads which of its alternatives fired.
    """
    if _DEGREE_REQUIREMENTS.match(line):
        return MARKER_TITLE_PAGE_DEGREE

    match = _FRONTMATTER_STOP.match(line)
    if not match:
        return None

    # Group 2 = (capstone|thesis|dissertation|research|project|undergraduate
    # thesis) from the "^(a|an) ..." alternative.
    if match.group(2):
        return MARKER_TITLE_PAGE_KIND

    # Group 3 = the "in partial fulfil(l)ment | presented to | submitted to"
    # alternative. Both fulfilment spellings deliberately collapse to ONE
    # marker — they are the same phrase, not two independent signals.
    third = (match.group(3) or '').lower()
    if 'fulfil' in third:
        return MARKER_TITLE_PAGE_FULFILMENT
    if 'presented' in third or 'submitted' in third:
        return MARKER_TITLE_PAGE_PRESENTED
    return None


def find_markers(text: str) -> list[str]:
    """Return the distinct structural markers present in ``text``.

    Order is stable (declaration order below) so error messages and tests read
    consistently rather than depending on where in the document a marker sat.
    """
    lines = [collapse_whitespace(raw) for raw in (text or '').split('\n')]

    found: set[str] = set()

    for line in lines:
        if not line:
            continue

        # ── Title-page boilerplate — each distinct phrase is its own marker ──
        phrase = _classify_title_page_phrase(line)
        if phrase:
            found.add(phrase)
            # A boilerplate line is never also a chapter heading; skip the rest.
            continue

        # ── Keywords line ──
        if _KEYWORDS_LABEL.match(line):
            found.add(MARKER_KEYWORDS)
            continue

        # ── References / bibliography ──
        heading = _strip_section_numbering(line)
        if _REFERENCES_HEADING.match(heading):
            found.add(MARKER_REFERENCES)
            continue

        # ── Abstract heading ──
        # Counted from the heading itself. A table-of-contents row
        # ("Abstract ......... vii") also indicates a thesis, so it is not
        # filtered out here — unlike in detect_abstract, where it would
        # produce a body of dot leaders.
        if _ABSTRACT_HEADING.match(line):
            found.add(MARKER_ABSTRACT)
            continue

        # ── Chapter / section headings ──
        # Numbering is stripped first so journal-style "1. INTRODUCTION" and
        # "2.1 Methodology" match the same canonical pattern as "CHAPTER I".
        if _METHODS_HEADING.match(heading):
            found.add(MARKER_CHAPTERS)
            continue
        chapter_match = _CHAPTER_PATTERNS.match(heading)
        if chapter_match:
            # Excluded names are counted elsewhere (or not at all), so one
            # line can never satisfy two markers.
            if heading.lower().strip(' .:-') not in _NOT_A_CHAPTER:
                found.add(MARKER_CHAPTERS)
            continue

    ordered = [
        MARKER_ABSTRACT,
        MARKER_KEYWORDS,
        MARKER_CHAPTERS,
        MARKER_REFERENCES,
        MARKER_TITLE_PAGE_KIND,
        MARKER_TITLE_PAGE_PRESENTED,
        MARKER_TITLE_PAGE_FULFILMENT,
        MARKER_TITLE_PAGE_DEGREE,
    ]
    return [m for m in ordered if m in found]


def check_thesis_document(text: str) -> ThesisDocumentCheck:
    """Decide whether ``text`` came from a thesis manuscript.

    Returns a :class:`ThesisDocumentCheck`. Three outcomes:

    * ``passed=True``  — at least :data:`MIN_MARKERS` markers found.
    * ``REASON_UNREADABLE``   — too little text to judge. Distinct on purpose:
      the user needs to hear "we could not read this file", not "this is not a
      thesis", because the remedy is completely different.
    * ``REASON_NOT_A_THESIS`` — readable, but structurally not a manuscript.

    Pure text analysis: no file I/O, no model imports, so it can be exercised
    directly against strings.
    """
    stripped = (text or '').strip()

    if len(stripped) < MIN_TEXT_CHARS:
        return ThesisDocumentCheck(
            passed=False, reason=REASON_UNREADABLE, markers=[],
        )

    markers = find_markers(stripped)
    if len(markers) >= MIN_MARKERS:
        return ThesisDocumentCheck(
            passed=True, reason=REASON_OK, markers=markers,
        )

    return ThesisDocumentCheck(
        passed=False, reason=REASON_NOT_A_THESIS, markers=markers,
    )
