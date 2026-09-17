"""Unit tests for theses.services.metadata_extraction.

These lock in the multi-line title-detection fixes. They call ``detect_title``
directly (no HTTP, no DB, no file I/O), so they run fast and pin the heuristics
rather than the endpoint wiring — ``test_extract_title.py`` still covers the
endpoint contract.

FIXTURE PROVENANCE — read this before trusting the coverage
-----------------------------------------------------------
Of the three theses the fix was designed against, only THESYS+ is present in
this repository (``media/theses/2026/thesysplus-250826_1.pdf``). Its test runs
against that REAL file and is skipped when the media file is absent (it is not
tracked in version control).

THESIX and EXTHEALTH are NOT in the repository. Their cases below are SYNTHETIC
fixtures reproducing the exact line structure described for them — a two-line
all-caps title whose continuation opens with an uppercase "WITH", and a
three-line title whose final line ("PROCESSING") carries no connector at all.
They are structural regression tests, not verification against those documents.
"""
from __future__ import annotations

import os

import pytest

from theses.services.metadata_extraction import (
    collapse_whitespace,
    detect_title,
    normalize_title_case,
)

# ---------------------------------------------------------------------------
# Synthetic front matter
# ---------------------------------------------------------------------------

# Two physical title lines; continuation opens with an UPPERCASE connector.
# "AND THESIS REPOSITORY" is why the noise filter must not use containment —
# 'thesis' is a noise heading on its own but legitimate inside a title.
THESIX_FRONTMATTER = """\
PAMPANGA STATE UNIVERSITY

THESIX: AN ONLINE THESIS ARCHIVING AND THESIS REPOSITORY
WITH NLP SEARCH

A Capstone Project
Presented to the Faculty of
College of Computing Studies

by:
Dela Cruz, Juan M.
"""

# Three physical title lines; the third ("PROCESSING") has NO connector, which
# is why the blank line — not the connector list — must be the primary signal.
EXTHEALTH_FRONTMATTER = """\
PAMPANGA STATE UNIVERSITY

EXTHEALTH: A MOBILE HEALTH RECORDS SYSTEM
FOR RURAL CLINICS USING NATURAL LANGUAGE
PROCESSING

A Thesis
Presented to the Faculty of

by:
Santos, Maria L.
"""

REAL_THESYSPLUS_PDF = os.path.join('media', 'theses', '2026', 'thesysplus-250826_1.pdf')


def _real_pdf_page_one() -> str:
    from pypdf import PdfReader
    return PdfReader(REAL_THESYSPLUS_PDF).pages[0].extract_text() or ''


# ---------------------------------------------------------------------------
# Multi-line joining — the core defect
# ---------------------------------------------------------------------------

class TestMultiLineTitleJoining:
    @pytest.mark.skipif(
        not os.path.exists(REAL_THESYSPLUS_PDF),
        reason='media/ is untracked; real THESYS+ PDF not present in this checkout',
    )
    def test_real_thesysplus_pdf_joins_both_title_lines(self):
        """Regression: previously truncated at the first line.

        Before the fix this returned only
        'THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis
        System', dropping the entire second line.
        """
        title, confidence = detect_title(_real_pdf_page_one())

        assert title == (
            'THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend '
            'Analysis System for CCS Undergraduate Theses at Pampanga State '
            'University'
        )
        assert confidence == 'high'
        assert len(title.split()) == 18
        # Stops before the degree boilerplate that follows the blank line.
        assert 'Capstone' not in title
        # pypdf emits double spaces on justified text; they must not survive.
        assert '  ' not in title

    def test_uppercase_connector_continuation_is_joined(self):
        """THESIX pattern (synthetic): continuation opens with 'WITH'.

        A case-sensitive connector list silently failed this.
        """
        title, _ = detect_title(THESIX_FRONTMATTER)

        assert title == (
            'Thesix: An Online Thesis Archiving And Thesis Repository '
            'With NLP Search'
        )
        # Acronym preserved rather than title-cased to 'Nlp'.
        assert 'NLP' in title
        # A legitimate 'THESIS' inside the title survives the noise filter.
        assert title.lower().count('thesis') == 2

    def test_connectorless_third_line_is_joined(self):
        """EXTHEALTH pattern (synthetic): third line is a bare 'PROCESSING'.

        Only the blank-line boundary can join this; no connector exists.
        """
        title, _ = detect_title(EXTHEALTH_FRONTMATTER)

        assert title == (
            'Exthealth: A Mobile Health Records System For Rural Clinics '
            'Using Natural Language Processing'
        )
        assert title.endswith('Processing')

    def test_block_stops_at_blank_line_not_at_author(self):
        """The join must terminate on the blank line, well before 'by:'."""
        title, _ = detect_title(EXTHEALTH_FRONTMATTER)

        assert 'Santos' not in title
        assert 'Thesis' not in title.split()[1:]  # 'A Thesis' not swallowed


# ---------------------------------------------------------------------------
# Connector fallback for documents with no blank-line structure
# ---------------------------------------------------------------------------

class TestNoBlankLineStructure:
    def test_connector_fallback_joins_only_connector_lines(self):
        """When an extractor drops blank lines, the connector list takes over.

        'Cruz, Juan' does not open with a connector, so the block ends before
        the author line even though no blank line separates them.
        """
        text = (
            'PAMPANGA STATE UNIVERSITY\n'
            'A SEMANTIC SEARCH SYSTEM FOR THESIS RETRIEVAL\n'
            'USING SENTENCE TRANSFORMERS\n'
            'Cruz, Juan\n'
        )
        title, _ = detect_title(text)

        assert title == (
            'A Semantic Search System For Thesis Retrieval '
            'Using Sentence Transformers'
        )
        assert 'Cruz' not in title

    def test_trailing_newline_alone_does_not_count_as_structure(self):
        """A trailing '\\n' is a split artifact, not document structure.

        Regression: ``any(line == '')`` treated the trailing blank produced by
        ``text.split('\\n')`` as blank-line structure, which disabled the
        connector fallback and let the title run into the author line.
        """
        text = (
            'A DEEP LEARNING APPROACH TO CROP DISEASE DETECTION\n'
            'IN PHILIPPINE RICE FIELDS\n'
            'Reyes, Ana\n'
        )
        title, _ = detect_title(text)

        assert 'Reyes' not in title
        assert title.endswith('Fields')


# ---------------------------------------------------------------------------
# Noise filtering — exact match, not prefix, not containment
# ---------------------------------------------------------------------------

class TestNoiseFiltering:
    def test_title_starting_with_noise_word_is_kept(self):
        """Prefix matching discarded any title opening with 'Thesis'."""
        text = (
            'PAMPANGA STATE UNIVERSITY\n'
            '\n'
            'THESIS REPOSITORY MANAGEMENT SYSTEM FOR THE COLLEGE\n'
            'OF COMPUTING STUDIES\n'
            '\n'
            'A Capstone Project\n'
        )
        title, _ = detect_title(text)

        assert title.lower().startswith('thesis repository management system')

    def test_bare_section_heading_is_still_rejected(self):
        """Exact-match noise filtering must still reject standalone headings."""
        text = (
            'TABLE OF CONTENTS\n'
            'ACKNOWLEDGEMENTS\n'
            'LIST OF FIGURES\n'
            'LIST OF TABLES\n'
        )
        title, confidence = detect_title(text)

        assert title == ''
        assert confidence == 'low'

    def test_chapter_only_document_caps_confidence_low(self):
        text = (
            'CHAPTER I\n'
            '\n'
            'THE PROBLEM AND ITS BACKGROUND\n'
            '\n'
            'Introduction\n'
        )
        _, confidence = detect_title(text)

        assert confidence == 'low'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestCollapseWhitespace:
    @pytest.mark.parametrize('raw, expected', [
        ('a  b', 'a b'),
        ('  leading and trailing  ', 'leading and trailing'),
        ('tab\tsep', 'tab sep'),
        ('', ''),
        (None, ''),
    ])
    def test_collapse(self, raw, expected):
        assert collapse_whitespace(raw) == expected


class TestNormalizeTitleCase:
    def test_mixed_case_is_left_untouched(self):
        original = 'THESYS+: A Semantic-Based Thesis Retrieval System'
        assert normalize_title_case(original) == original

    def test_all_caps_is_title_cased(self):
        assert normalize_title_case('A MOBILE HEALTH RECORDS SYSTEM') == (
            'A Mobile Health Records System'
        )

    def test_known_acronyms_survive_normalisation(self):
        assert normalize_title_case('SEARCH USING NLP AND OCR') == (
            'Search Using NLP And OCR'
        )

    def test_parenthesised_acronym_is_not_mangled(self):
        """Regression: bare .title() turned '(NLP)' into '(Nlp)'."""
        assert '(NLP)' in normalize_title_case(
            'NATURAL LANGUAGE PROCESSING (NLP) FOR SEARCH'
        )

    def test_no_letters_returns_input(self):
        assert normalize_title_case('123 456') == '123 456'


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

class TestDegenerateInput:
    @pytest.mark.parametrize('text', ['', '   ', '\n\n\n'])
    def test_empty_text_returns_low_confidence(self, text):
        assert detect_title(text) == ('', 'low')
