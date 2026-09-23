"""Tests for the thesis document-type gate.

The bug: a Certificate of Registration (a class-schedule table) was accepted by
Title Similarity, the title extractor returned a run of schedule cells as the
"detected title", and a similarity check reported a meaningless 38.1%.

The two failure modes these tests defend against pull in OPPOSITE directions,
and both matter:

  1. Accepting a non-thesis  — the reported bug.
  2. Rejecting a real thesis — the bug a negative-keyword blocklist would have
     introduced. A thesis about enrolment or scheduling shares its entire
     vocabulary with a COR, so SCHEDULE/ROOM/UNIT/CREDIT cannot be used as
     rejection signals. ``TestFalsePositiveGuard`` is that boundary.

Fixtures are plain strings — the checker performs no file I/O.
"""
from __future__ import annotations

import os

import pytest

from theses.services.thesis_document_check import (
    MARKER_ABSTRACT,
    MARKER_CHAPTERS,
    MARKER_KEYWORDS,
    MARKER_REFERENCES,
    MARKER_TITLE_PAGE_DEGREE,
    MARKER_TITLE_PAGE_FULFILMENT,
    MARKER_TITLE_PAGE_KIND,
    MARKER_TITLE_PAGE_PRESENTED,
    MIN_MARKERS,
    MIN_TEXT_CHARS,
    REASON_NOT_A_THESIS,
    REASON_OK,
    REASON_UNREADABLE,
    check_thesis_document,
    find_markers,
)

REAL_THESYSPLUS_PDF = os.path.join('media', 'theses', '2026', 'thesysplus-250826_1.pdf')

# Padding to clear MIN_TEXT_CHARS without contributing any marker, so a
# fixture's marker count is exactly what it declares.
FILLER = (
    'This paragraph exists only to give the document enough readable text to '
    'be judged on structure rather than dismissed as unreadable. It carries '
    'no headings and no structural markers of any kind whatsoever. '
) * 3


# ---------------------------------------------------------------------------
# Fixtures modelled on real documents
# ---------------------------------------------------------------------------

# Shape of the ACTUAL extraction from SALONGA_COR.pdf, per the bug report. The
# fourth line is verbatim the string that was returned as a "detected title".
COR_TEXT = """\
PAMPANGA STATE UNIVERSITY
CERTIFICATE OF REGISTRATION
Student No.: 2023313546   Name: SALONGA, ROMEL S.
Bachelor of Science in Information Systems 4th Year SCHEDULE / ROOMSECTIONLec
U N I TSUBJECT TITLECODE Lab Credit 303Data Mining and Business
IntelligenceISDBI 413 BSIS 4-A 303Strategy Management and AcquisitionISSMA 414
BSIS 4-A 303Systems Integration and ArchitectureISSIA 415 BSIS 4-A
303Information Assurance and SecurityISIAS 416 BSIS 4-A
TOTAL UNITS: 24
Assessment: Tuition Fee 12,000.00   Misc 2,500.00   Total 14,500.00
Registrar   Cashier   Adviser
Date Enrolled: August 12, 2026
"""

STANDALONE_TITLE_PAGE = """\
PAMPANGA STATE UNIVERSITY
College of Computing Studies

A MOBILE HEALTH RECORDS SYSTEM FOR RURAL CLINICS
USING NATURAL LANGUAGE PROCESSING

A Capstone
Presented to the Faculty of
College of Computing Studies
Pampanga State University

by:
Dela Cruz, Juan M.
Santos, Maria A.

May 2025
""" + FILLER


# ---------------------------------------------------------------------------
# The reported bug
# ---------------------------------------------------------------------------

class TestCertificateOfRegistrationIsRejected:
    def test_cor_fails(self):
        result = check_thesis_document(COR_TEXT)

        assert result.passed is False
        assert result.reason == REASON_NOT_A_THESIS

    def test_cor_scores_zero_markers(self):
        """Not "few markers" — none at all. The gate has enormous headroom."""
        result = check_thesis_document(COR_TEXT)

        assert result.markers == []
        assert result.marker_count == 0

    def test_cor_reason_is_not_the_unreadable_one(self):
        """The COR is perfectly readable; it is simply the wrong document."""
        assert check_thesis_document(COR_TEXT).reason != REASON_UNREADABLE

    def test_the_line_that_became_a_title_contributes_nothing(self):
        """The offending line mentions a degree but is not title-page boilerplate.

        "Bachelor of Science in Information Systems 4th Year SCHEDULE…" scored
        well in the title heuristic. It must score zero here.
        """
        offending = (
            'Bachelor of Science in Information Systems 4th Year SCHEDULE / '
            'ROOMSECTIONLec U N I TSUBJECT TITLECODE Lab Credit'
        )
        assert find_markers(offending) == []


# ---------------------------------------------------------------------------
# The threshold
# ---------------------------------------------------------------------------

class TestThreshold:
    def test_threshold_is_two(self):
        assert MIN_MARKERS == 2

    def test_exactly_one_marker_fails(self):
        """Proves the threshold is 2, not 1.

        A stray "Introduction" line appears in plenty of non-thesis documents,
        so one marker cannot be sufficient.
        """
        text = 'INTRODUCTION\n' + FILLER
        result = check_thesis_document(text)

        assert result.markers == [MARKER_CHAPTERS]
        assert result.marker_count == 1
        assert result.passed is False
        assert result.reason == REASON_NOT_A_THESIS

    def test_exactly_two_markers_passes(self):
        text = 'ABSTRACT\n' + FILLER + '\nKeywords: semantic search, retrieval\n'
        result = check_thesis_document(text)

        assert result.marker_count == 2
        assert result.passed is True
        assert result.reason == REASON_OK


# ---------------------------------------------------------------------------
# Passing shapes
# ---------------------------------------------------------------------------

class TestAbstractAndKeywords:
    def test_abstract_plus_keywords_passes(self):
        text = (
            'ABSTRACT\n'
            + FILLER
            + '\nKeywords: mobile health, records management, NLP\n'
        )
        result = check_thesis_document(text)

        assert result.passed is True
        assert MARKER_ABSTRACT in result.markers
        assert MARKER_KEYWORDS in result.markers

    @pytest.mark.parametrize('label', [
        'Keywords:', 'Keyword:', 'KEYWORDS:', 'Key words:', 'Index Terms:',
    ])
    def test_keyword_label_variants(self, label):
        text = f'ABSTRACT\n{FILLER}\n{label} alpha, beta, gamma\n'
        assert MARKER_KEYWORDS in check_thesis_document(text).markers


class TestTitlePageBoilerplateWithChapters:
    """The THESYS+ shape — and the most important test in this file.

    The real THESYS+ manuscript in this repository has NO abstract heading
    anywhere in its 93 pages. If an abstract were a mandatory marker, the gate
    would reject the project's own thesis.
    """

    THESYSPLUS_SHAPE = """\
PAMPANGA STATE UNIVERSITY
THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System
for CCS Undergraduate Theses at Pampanga State University

A Capstone
Presented to the Faculty of
College of Computing Studies
Pampanga State University
In Partial Fulfillment
of the Requirements for the Degree
Bachelor of Science in Information Systems

by:
Quizon, Valerie Daphne D.

May 2026

CHAPTER I
THE PROBLEM AND ITS BACKGROUND
""" + FILLER + """
CHAPTER III
METHODOLOGY
""" + FILLER + """
REFERENCES
"""

    def test_passes_without_any_abstract(self):
        result = check_thesis_document(self.THESYSPLUS_SHAPE)

        assert result.passed is True
        assert MARKER_ABSTRACT not in result.markers, (
            'fixture must not contain an abstract — that is the point of it'
        )

    def test_finds_chapters_and_references(self):
        markers = check_thesis_document(self.THESYSPLUS_SHAPE).markers

        assert MARKER_CHAPTERS in markers
        assert MARKER_REFERENCES in markers

    def test_finds_all_four_distinct_boilerplate_phrases(self):
        markers = check_thesis_document(self.THESYSPLUS_SHAPE).markers

        assert MARKER_TITLE_PAGE_KIND in markers
        assert MARKER_TITLE_PAGE_PRESENTED in markers
        assert MARKER_TITLE_PAGE_FULFILMENT in markers
        assert MARKER_TITLE_PAGE_DEGREE in markers


class TestNumberedJournalHeadings:
    """`_CHAPTER_PATTERNS` is anchored ^...$, so numbering must be stripped."""

    def test_numbered_sections_plus_references_passes(self):
        text = (
            '1. INTRODUCTION\n' + FILLER
            + '\n2. METHODOLOGY\n' + FILLER
            + '\n5. REFERENCES\n'
        )
        result = check_thesis_document(text)

        assert result.passed is True
        assert MARKER_CHAPTERS in result.markers
        assert MARKER_REFERENCES in result.markers

    @pytest.mark.parametrize('heading', [
        '1. INTRODUCTION',
        '1 INTRODUCTION',
        '2.1 Methodology',
        '3.2.1 Results and Discussion',
        'I. INTRODUCTION',
        'IV) CONCLUSION',
        'CHAPTER I',
        'CHAPTER IV',
        'METHODS',
        'Methodology',
    ])
    def test_heading_forms_recognised(self, heading):
        assert MARKER_CHAPTERS in find_markers(heading)

    def test_prose_beginning_with_a_capital_i_is_not_a_heading(self):
        """The roman-numeral strip requires punctuation, so prose is safe."""
        assert find_markers('I am describing the enrolment process here.') == []


class TestStandaloneTitlePage:
    """Proves per-phrase counting, which is why this shape is accepted.

    A title page is a legitimate Title Similarity upload — and the one document
    guaranteed to hold a clean, well-formed title. If all boilerplate collapsed
    into a single shared marker it would score 1 and be refused.
    """

    def test_two_distinct_phrases_and_nothing_else_passes(self):
        result = check_thesis_document(STANDALONE_TITLE_PAGE)

        assert result.passed is True
        assert result.markers == [
            MARKER_TITLE_PAGE_KIND, MARKER_TITLE_PAGE_PRESENTED,
        ]
        assert result.marker_count == 2

    def test_no_other_marker_carried_it(self):
        markers = check_thesis_document(STANDALONE_TITLE_PAGE).markers

        assert MARKER_ABSTRACT not in markers
        assert MARKER_KEYWORDS not in markers
        assert MARKER_CHAPTERS not in markers
        assert MARKER_REFERENCES not in markers

    def test_only_one_boilerplate_phrase_fails(self):
        """Counting is per DISTINCT phrase, not "boilerplate present anywhere"."""
        text = """\
PAMPANGA STATE UNIVERSITY

AN ENROLMENT MANAGEMENT SYSTEM FOR SENIOR HIGH SCHOOL

A Thesis

by:
Dela Cruz, Juan M.
""" + FILLER
        result = check_thesis_document(text)

        assert result.markers == [MARKER_TITLE_PAGE_KIND]
        assert result.marker_count == 1
        assert result.passed is False

    def test_both_fulfilment_spellings_are_one_marker(self):
        """Same phrase, not two independent signals."""
        text = (
            'In Partial Fulfillment\n'
            'In Partial Fulfilment\n'
            + FILLER
        )
        result = check_thesis_document(text)

        assert result.markers == [MARKER_TITLE_PAGE_FULFILMENT]
        assert result.marker_count == 1
        assert result.passed is False


# ---------------------------------------------------------------------------
# Unreadable — a distinct reason, not "not a thesis"
# ---------------------------------------------------------------------------

class TestUnreadable:
    @pytest.mark.parametrize('text', ['', '   ', '\n\n\t\n', None])
    def test_empty_input_is_unreadable_not_not_a_thesis(self, text):
        """A failed OCR pass and a COR need different remedies.

        "Upload a text-based PDF" versus "upload a different document" — telling
        the user the wrong one sends them to solve the wrong problem.
        """
        result = check_thesis_document(text)

        assert result.passed is False
        assert result.reason == REASON_UNREADABLE
        assert result.reason != REASON_NOT_A_THESIS

    def test_a_few_characters_is_unreadable(self):
        result = check_thesis_document('Thesis')

        assert result.reason == REASON_UNREADABLE

    def test_unreadable_reports_no_markers(self):
        assert check_thesis_document('').markers == []

    def test_threshold_boundary(self):
        """Just under MIN_TEXT_CHARS is unreadable; just over is judged."""
        assert check_thesis_document('a' * (MIN_TEXT_CHARS - 1)).reason == REASON_UNREADABLE
        # Long enough to judge, but structurally empty → not_a_thesis.
        assert check_thesis_document('word ' * MIN_TEXT_CHARS).reason == REASON_NOT_A_THESIS

    def test_a_marker_rich_but_tiny_document_is_still_unreadable(self):
        """Length is a precondition, checked before markers are counted."""
        result = check_thesis_document('ABSTRACT\nKeywords: a, b\n')

        assert result.reason == REASON_UNREADABLE


# ---------------------------------------------------------------------------
# The false-positive guard — why a blocklist was rejected
# ---------------------------------------------------------------------------

class TestFalsePositiveGuard:
    """A thesis ABOUT scheduling must pass.

    This is the boundary a negative-keyword approach would have crossed. This
    repository already holds "Scholarship Management In Pampanga", "Alumni
    Portal Tracker" and "Web-Based Qualifying Examination" — an enrolment
    thesis is a normal submission here, and it contains a COR's entire
    vocabulary.
    """

    SCHEDULING_THESIS = """\
PAMPANGA STATE UNIVERSITY

AN AUTOMATED CLASS SCHEDULING AND ROOM ALLOCATION SYSTEM
FOR THE COLLEGE OF COMPUTING STUDIES

A Capstone
Presented to the Faculty of
In Partial Fulfillment
of the Requirements for the Degree

ABSTRACT

This study developed a system that assigns each SECTION to a ROOM and
computes the total UNIT and CREDIT load per student. The SCHEDULE produced
by the system was compared against the registrar's manual timetable, and
the SUBJECT TITLE and CODE mappings were validated against the curriculum.
Lecture and laboratory UNITS were balanced across available ROOMS.

Keywords: class scheduling, room allocation, enrolment, timetabling

CHAPTER I
INTRODUCTION

The registrar prepares the SCHEDULE by hand each term, assigning a ROOM and
a SECTION to every SUBJECT and tallying CREDIT UNITS per student.

CHAPTER III
METHODOLOGY

REFERENCES
"""

    def test_a_scheduling_thesis_passes(self):
        result = check_thesis_document(self.SCHEDULING_THESIS)

        assert result.passed is True, (
            'a thesis about scheduling must not be mistaken for a schedule'
        )

    def test_it_passes_comfortably_not_marginally(self):
        """Well clear of the threshold, so small wording changes cannot flip it."""
        result = check_thesis_document(self.SCHEDULING_THESIS)

        assert result.marker_count >= 5

    def test_cor_vocabulary_alone_never_rejects(self):
        """The blocklist words carry no weight in either direction."""
        loaded = (
            'SCHEDULE ROOM SECTION UNIT SUBJECT TITLE CODE CREDIT Lec Lab '
            'TOTAL UNITS Registrar Cashier Assessment Tuition Fee '
        ) * 4
        with_markers = 'ABSTRACT\n' + loaded + '\nKeywords: a, b, c\n'

        assert check_thesis_document(with_markers).passed is True

    def test_an_enrolment_thesis_title_page_alone_passes(self):
        """Even the sparsest legitimate case survives the vocabulary overlap."""
        text = """\
AN ONLINE ENROLMENT AND CLASS SCHEDULE MANAGEMENT SYSTEM

A Thesis
Presented to the Faculty of
""" + FILLER
        assert check_thesis_document(text).passed is True


# ---------------------------------------------------------------------------
# Result object contract
# ---------------------------------------------------------------------------

class TestResultShape:
    def test_marker_labels_are_human_readable(self):
        """The error payload shows a user what WAS recognised."""
        result = check_thesis_document('ABSTRACT\n' + FILLER + '\nKeywords: a, b\n')

        labels = result.marker_labels
        assert 'abstract heading' in labels
        assert 'keywords line' in labels
        # Identifiers must not leak into user-facing copy.
        assert not any('_' in label for label in labels)

    def test_marker_count_matches_marker_list(self):
        result = check_thesis_document(STANDALONE_TITLE_PAGE)
        assert result.marker_count == len(result.markers)

    def test_marker_order_is_stable(self):
        """Declaration order, not document order — messages read consistently."""
        forwards = 'ABSTRACT\n' + FILLER + '\nKeywords: a, b\nREFERENCES\n'
        backwards = 'REFERENCES\nKeywords: a, b\n' + FILLER + '\nABSTRACT\n'

        assert check_thesis_document(forwards).markers == \
            check_thesis_document(backwards).markers

    def test_markers_are_never_duplicated(self):
        text = (
            'ABSTRACT\nABSTRACT\nCHAPTER I\nCHAPTER II\nCHAPTER III\n'
            + FILLER
        )
        markers = check_thesis_document(text).markers

        assert len(markers) == len(set(markers))


# ---------------------------------------------------------------------------
# Against the one real document in the repository
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(REAL_THESYSPLUS_PDF),
    reason='media/ is untracked; real THESYS+ PDF not present in this checkout',
)
class TestRealThesysPlusDocument:
    """Pins the gate against the actual manuscript, not just a fixture of it."""

    def _text(self, **kwargs):
        from theses.services.text_extractor import ThesisTextExtractor
        result = ThesisTextExtractor().extract(REAL_THESYSPLUS_PDF, **kwargs)
        assert result.success
        return result.text

    def test_full_document_passes(self):
        result = check_thesis_document(self._text())

        assert result.passed is True
        assert result.marker_count >= 4

    def test_it_really_has_no_abstract_heading(self):
        """The premise behind not requiring an abstract, verified on the file."""
        result = check_thesis_document(self._text())

        assert MARKER_ABSTRACT not in result.markers

    def test_front_matter_alone_passes(self):
        """extract-title reads only the first few pages — that must suffice."""
        from theses.services.text_extractor import FRONT_MATTER_PAGES

        result = check_thesis_document(self._text(max_pages=FRONT_MATTER_PAGES))

        assert result.passed is True

    def test_metadata_window_passes(self):
        from theses.services.text_extractor import METADATA_PAGES

        result = check_thesis_document(self._text(max_pages=METADATA_PAGES))

        assert result.passed is True
