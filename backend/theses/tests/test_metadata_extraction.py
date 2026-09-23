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
import re

import pytest

from theses.services.metadata_extraction import (
    _EMAIL,
    _PHONE,
    _looks_like_author_line,
    _looks_like_person_name,
    _score_candidate_line,
    collapse_whitespace,
    detect_authors,
    detect_title,
    normalize_title_case,
)

# ---------------------------------------------------------------------------
# CANARY TITLES — real titles from this corpus that the author-line terminator
# must never touch.
#
# These exist because _looks_like_person_name returns True for all of them:
# by capitalisation alone a three-word Title Case phrase is indistinguishable
# from a name. If a canary breaks, TIGHTEN the author-line test. Never loosen
# the canary — it is the corpus, not the test, that is authoritative.
# ---------------------------------------------------------------------------

CANARY_TITLES = (
    'Alumni Portal Tracker',
    'Scholarship Management In Pampanga',
    'Web-Based Qualifying Examination',
    'SISTEMA de OBRA: TRAINING MONITORING SYSTEM',
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

# ARADA pattern — taken from the real corpus, where this document's stored
# title was the whole contact block welded onto the end of the title:
#
#   'ARADA: AN ANDROID ONLINE MARKET ... IN PAMPANGA Aguilar, Janwalf S.
#    2018003310@dhvsu.edu.ph 09397429130 Alfonso, Nicholas D. Jr. ...'
#
# Structurally: no "by" marker anywhere, so _AUTHOR_MARKER never fires; the
# author block sits directly against the title with no intervening blank; and
# blank lines DO exist elsewhere on the page, so has_blank_structure is True
# and the old connector gate was switched off.
ARADA_FRONTMATTER = """\
PAMPANGA STATE UNIVERSITY

ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY-DEMAND
STATISTICS FOR SELECTED LOCAL FARMERS
GONZAGA, KURT ROSS E.
AGUILAR, JANWALF S.
kurt.gonzaga@dhvsu.edu.ph
09397429130
09502764793

A Capstone Project
Presented to the Faculty of
"""

# The same page as some extractors actually emit it: ONE line, zero newlines.
# No line-based terminator can fire here — there are no lines to terminate.
ARADA_SINGLE_LINE = (
    'ARADA: AN ANDROID ONLINE MARKET WITH SUPPLY-DEMAND STATISTICS FOR '
    'SELECTED LOCAL FARMERS GONZAGA, KURT ROSS E. kurt.gonzaga@dhvsu.edu.ph '
    '09397429130 AGUILAR, JANWALF S. 09502764793'
)

# Surnames that must never appear in a returned title.
ARADA_SURNAMES = ('GONZAGA', 'AGUILAR', 'Gonzaga', 'Aguilar')

REAL_THESYSPLUS_PDF = os.path.join('media', 'theses', '2026', 'thesysplus-250826_1.pdf')


def assert_no_pii(title: str) -> None:
    """Assert ``title`` carries no contact details and no author surname.

    Kept as one helper so every PII test checks the identical set — a per-test
    copy would drift, and the whole point is that NO shape leaks.
    """
    assert '@' not in title, f'email address reached the title: {title!r}'
    assert not re.search(r'\d{7,}', title), (
        f'7+ digit run (phone / student number) reached the title: {title!r}'
    )
    for surname in ARADA_SURNAMES:
        assert surname not in title, (
            f'author surname {surname!r} reached the title: {title!r}'
        )


def _real_pdf_page_one() -> str:
    from pypdf import PdfReader
    return PdfReader(REAL_THESYSPLUS_PDF).pages[0].extract_text() or ''


# ---------------------------------------------------------------------------
# PII containment
#
# The bias here is deliberate and worth stating: a truncated title costs the
# user a retype, which they can see and fix. A published email address or
# mobile number cannot be taken back. Every ambiguous case cuts.
# ---------------------------------------------------------------------------

class TestTitleCarriesNoPII:
    def test_multiline_author_block_does_not_reach_the_title(self):
        """ARADA pattern: no 'by' marker, author block flush against the title.

        The stored title for this document in the real corpus contained four
        student email addresses and four mobile numbers.
        """
        title, _ = detect_title(ARADA_FRONTMATTER)

        assert_no_pii(title)
        # And the real title is still recovered, not merely blanked.
        assert title.lower().startswith('arada')

    @pytest.mark.parametrize('line', [
        'kurt.gonzaga@dhvsu.edu.ph',
        'GONZAGA, KURT ROSS E. kurt.gonzaga@dhvsu.edu.ph',
        '2018003310@dhvsu.edu.ph',
        'first.last+tag@sub.example.co.uk',
    ])
    def test_email_regex_matches_real_shapes(self, line):
        assert _EMAIL.search(line)

    @pytest.mark.parametrize('line', [
        '09397429130',
        '+639397429130',
        '0939-742-9130',
        '+63 939 742 9130',
        'Contact 09502764793 for details',
        '2018003310',            # student number — PII too
    ])
    def test_phone_regex_matches_real_shapes(self, line):
        assert _PHONE.search(line)

    @pytest.mark.parametrize('line', [
        '2026',
        'May 2026',
        'ISO 9001',
        'BSIT-4A',
        'Chapter 1234',
        'A STUDY OF 4 VARIABLES IN 2025',
        'Section 8.2.1',
    ])
    def test_phone_regex_does_not_match_near_misses(self, line):
        """The 7-digit floor exists so ordinary numbers cannot trip the cut.

        A false positive here truncates a legitimate title, so these are the
        cases that keep the floor honest.
        """
        assert not _PHONE.search(line), f'{line!r} wrongly read as a phone number'

    @pytest.mark.parametrize('line', [
        'A MOBILE HEALTH RECORDS SYSTEM',
        'Presented to the Faculty of',
        'May 2026',
    ])
    def test_email_regex_does_not_match_ordinary_lines(self, line):
        assert not _EMAIL.search(line)

    @pytest.mark.parametrize('line', [
        'GONZAGA, KURT ROSS E.',
        'AGUILAR, JANWALF S.',
        'Dela Cruz, Juan M.',
        'Alfonso, Nicholas D. Jr.',
        'Dr. Maria Santos',
        'Engr. Roberto Reyes',
        'Ramirez, Ana',
    ])
    def test_author_lines_are_recognised(self, line):
        assert _looks_like_author_line(line), f'{line!r} not read as an author line'

    @pytest.mark.parametrize('line', [
        'CRISTOPHER B. AMPA, Don Honorio Ventura State University',
        'JOHN PAUL B. ARNAIZ, Don Honorio Ventura State University',
        'PHILIP LORENZ R. CRASCO, Don Honorio Ventura State University',
        'GENESARET D. ASAS, Don Honorio Ventura State University',
    ])
    def test_name_with_affiliation_on_one_line_is_an_author_line(self, line):
        """Real corpus layout, and a name leak found by auditing it.

        These run eight to nine words, and ``_has_name_shape`` caps a name at
        six — so they were NOT recognised as author lines, and full student
        names were eligible to be joined onto a title. The standalone-initial
        marker is now checked without a length limit for exactly this shape.
        """
        assert _looks_like_author_line(line)

    @pytest.mark.parametrize('line', [
        # A real title that happens to contain 'SURNAME, Place'. The comma rule
        # must not reach this, or the title disqualifies itself.
        'Monitoring for the Office of Municipal Treasury of the Municipality of Bacolor, Pampanga',
        # A real title containing an honorific.
        'A MONITORING SYSTEM FOR DR. JOSE RIZAL MEMORIAL HOSPITAL',
    ])
    def test_titles_containing_name_like_fragments_are_not_author_lines(self, line):
        assert not _looks_like_author_line(line), (
            f'real title {line!r} was read as an author line'
        )

    def test_author_names_with_affiliations_do_not_join_the_title(self):
        """End-to-end version of the leak above.

        Five author lines, each carrying a full student name and the
        university. None may appear in the title, and the title itself must
        survive intact.
        """
        text = (
            'MODEYUL: AN EDUCATIONAL KAPAMPANGAN SUPPLEMENTAL\n'
            'GAME APP FOR GRADE 3 STUDENTS\n'
            'CRISTOPHER B. AMPA, Don Honorio Ventura State University\n'
            'BILLY M. CEPEDA, Don Honorio Ventura State University\n'
            'PHILIP LORENZ R. CRASCO, Don Honorio Ventura State University\n'
            '\n'
            'A Capstone Project\n'
        )
        title, _ = detect_title(text)

        assert title.lower() == (
            'modeyul: an educational kapampangan supplemental '
            'game app for grade 3 students'
        )
        for surname in ('AMPA', 'Ampa', 'CEPEDA', 'Cepeda', 'CRASCO', 'Crasco'):
            assert surname not in title

    def test_single_line_page_does_not_reach_the_title(self):
        """Same page with zero newlines — no line terminator can fire.

        Some extractors emit a whole page as one line. Line-based defenses are
        structurally incapable of helping here, so this is the case that
        requires scrubbing the assembled string.
        """
        title, _ = detect_title(ARADA_SINGLE_LINE)

        assert_no_pii(title)
        assert title.lower().startswith('arada')


class TestCanaryTitlesSurvive:
    """Real corpus titles must come back whole.

    The PII work adds three ways to cut a title short — contact-detail
    terminator, author-line terminator, continuation gate. Each one is a
    chance to truncate something legitimate, and these are the titles most
    at risk because they read like names.
    """

    @pytest.mark.parametrize('title_line', CANARY_TITLES)
    def test_canary_is_not_read_as_an_author_line(self, title_line):
        assert not _looks_like_author_line(title_line), (
            f'real title {title_line!r} was read as an author line and would '
            'be cut from the title'
        )

    @pytest.mark.parametrize('title_line', CANARY_TITLES)
    def test_canary_survives_full_detection(self, title_line):
        text = (
            'PAMPANGA STATE UNIVERSITY\n'
            '\n'
            f'{title_line}\n'
            '\n'
            'A Capstone Project\n'
            'Presented to the Faculty of\n'
        )
        detected, _ = detect_title(text)

        # Compare on lowercase: normalize_title_case legitimately re-cases an
        # all-caps title, so the assertion is about CONTENT surviving, not
        # about casing being preserved.
        assert detected.lower() == title_line.lower(), (
            f'expected {title_line!r} intact, got {detected!r}'
        )

    def test_two_line_all_caps_title_joins_fully(self):
        """Second line is three capitalised words — name-shaped, but a title.

        This is the shape most likely to be destroyed by the author-line
        terminator, and the reason the terminator demands a positive marker
        rather than trusting capitalisation.
        """
        text = (
            'PAMPANGA STATE UNIVERSITY\n'
            '\n'
            'AI-POWERED ATTENDANCE MONITORING SYSTEM FOR\n'
            'PUBLIC SENIOR HIGH SCHOOLS\n'
            '\n'
            'A Capstone Project\n'
        )
        title, _ = detect_title(text)

        # Exact, including casing. This previously had to assert
        # case-insensitively because normalize_title_case mangled 'AI-POWERED'
        # into 'Ai-Powered'; the compound-token fix makes the full assertion
        # available, so it is used.
        assert title == (
            'AI-Powered Attendance Monitoring System For '
            'Public Senior High Schools'
        )


class TestAuthorsSurviveContactDetails:
    """Author extraction must keep names and discard contacts.

    Two separate concerns, both tested here: the name test must never accept a
    contact line (safety), and a contact detail sitting beside a name must not
    destroy the author walk (data loss).
    """

    # ── Safety lock ────────────────────────────────────────────────────────

    @pytest.mark.parametrize('line', [
        'kurt.gonzaga@dhvsu.edu.ph',
        '2018003310@dhvsu.edu.ph',
        '09397429130',
        '+63 939 742 9130',
    ])
    def test_contact_line_is_never_a_person_name(self, line):
        """Regression lock on behaviour that is already correct.

        ``_NAME_DISALLOWED`` excludes '@' and digits today, so this passes
        without any change. The test exists so that widening that character
        class later — to admit some accented or punctuated name form — cannot
        quietly turn contact details into accepted author names.
        """
        assert not _looks_like_person_name(line)

    # ── Data loss ──────────────────────────────────────────────────────────

    def test_email_beside_each_name_does_not_drop_authors(self):
        """The silent-drop bug.

        Every one of these lines carries an email, so every one failed the name
        test and the walk broke on the FIRST of them — yielding no authors at
        all from a perfectly well-formed author block.
        """
        text = (
            'AN ANDROID ONLINE MARKET FOR LOCAL FARMERS\n'
            '\n'
            'by:\n'
            'GONZAGA, KURT ROSS E. kurt.gonzaga@dhvsu.edu.ph\n'
            'AGUILAR, JANWALF S. janwalf.aguilar@dhvsu.edu.ph\n'
            'DAVID, JERICO B. jerico.david@dhvsu.edu.ph\n'
        )
        authors, _ = detect_authors(text)

        assert authors == [
            'GONZAGA, KURT ROSS E.',
            'AGUILAR, JANWALF S.',
            'DAVID, JERICO B.',
        ]
        # The middle initial survives — proof the name is excised from the
        # contact, not truncated at it.
        assert authors[0].endswith('E.')

    def test_phone_beside_name_does_not_drop_authors(self):
        text = (
            'AN ANDROID ONLINE MARKET FOR LOCAL FARMERS\n'
            '\n'
            'by:\n'
            'GONZAGA, KURT ROSS E. 09397429130\n'
            'AGUILAR, JANWALF S. 09502764793\n'
        )
        authors, _ = detect_authors(text)

        assert authors == ['GONZAGA, KURT ROSS E.', 'AGUILAR, JANWALF S.']

    def test_contacts_on_their_own_lines_do_not_end_the_walk(self):
        """The other real layout: contacts beneath each name, not beside it.

        A pure contact line is skipped rather than treated as the end of the
        block, so the authors listed after it are still collected.
        """
        text = (
            'AN ANDROID ONLINE MARKET FOR LOCAL FARMERS\n'
            '\n'
            'by:\n'
            'GONZAGA, KURT ROSS E.\n'
            'kurt.gonzaga@dhvsu.edu.ph\n'
            'AGUILAR, JANWALF S.\n'
            'janwalf.aguilar@dhvsu.edu.ph\n'
        )
        authors, _ = detect_authors(text)

        assert authors == ['GONZAGA, KURT ROSS E.', 'AGUILAR, JANWALF S.']

    @pytest.mark.parametrize('text', [
        (
            'A TITLE FOR THE WORK\n\nby:\n'
            'GONZAGA, KURT ROSS E. kurt.gonzaga@dhvsu.edu.ph\n'
        ),
        (
            'A TITLE FOR THE WORK\n\nby:\n'
            'GONZAGA, KURT ROSS E. 09397429130\n'
        ),
    ])
    def test_contact_details_are_never_stored_in_an_author_value(self, text):
        """Stripping must discard, not relocate."""
        authors, _ = detect_authors(text)

        assert authors
        for author in authors:
            assert '@' not in author
            assert not re.search(r'\d', author), (
                f'digits survived into author value {author!r}'
            )

    def test_inline_name_after_the_marker_is_also_cleaned(self):
        """'by: NAME email' — the same treatment on the marker line itself."""
        text = (
            'A TITLE FOR THE WORK\n'
            '\n'
            'by: GONZAGA, KURT ROSS E. kurt.gonzaga@dhvsu.edu.ph\n'
        )
        authors, _ = detect_authors(text)

        assert authors == ['GONZAGA, KURT ROSS E.']


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


class TestScorerRejectsAuthorLines:
    """The scorer guard, which previously caught almost nothing.

    The old condition was::

        if n_words <= 3 and not any(c in line for c in (':', '-', 'A', 'An', 'The')):

    ``'A' in line`` is a substring test for a single capital letter, so any
    line containing an A satisfied it — and the ``<= 3`` ceiling excluded
    four-token author entries anyway.
    """

    @pytest.mark.parametrize('line', [
        'GONZAGA, KURT ROSS E.',
        'AGUILAR, JANWALF S.',
        'Dela Cruz, Juan M.',
        'Alfonso, Nicholas D. Jr.',
    ])
    def test_author_line_cannot_be_scored_as_a_title(self, line):
        assert _score_candidate_line(line, 0) is None

    @pytest.mark.parametrize('line', [
        'A SEMANTIC SEARCH SYSTEM FOR THESIS RETRIEVAL',
        'THESYS+: A Semantic-Based Thesis Retrieval System',
        'AI-POWERED ATTENDANCE MONITORING USING FACIAL RECOGNITION',
    ])
    def test_real_title_at_index_zero_still_scores_high(self, line):
        """Guard against over-reach: the fix must not start rejecting titles."""
        score = _score_candidate_line(line, 0)
        assert score is not None, f'real title {line!r} was disqualified'
        assert score >= 7, f'real title {line!r} scored only {score}'

    @pytest.mark.parametrize('line', CANARY_TITLES)
    def test_canary_titles_still_score(self, line):
        assert _score_candidate_line(line, 0) is not None


class TestContinuationGateWithBlankStructure:
    """The relaxed gate, one test per admitting condition.

    Before this, the gate ran ONLY when a document had no blank-line
    structure. Any page with a blank line anywhere joined every
    non-terminator line unconditionally — which is how author names got into
    titles, since the blank separating the title block from the degree
    boilerplate lower down switched the gate off for everything between.
    """

    @staticmethod
    def _page(*title_lines: str) -> str:
        body = '\n'.join(title_lines)
        return (
            'PAMPANGA STATE UNIVERSITY\n'
            '\n'
            f'{body}\n'
            '\n'
            'A Capstone Project\n'
        )

    def test_condition_1_leading_connector_joins(self):
        title, _ = detect_title(self._page(
            'A SEMANTIC RETRIEVAL ENGINE',
            'FOR UNDERGRADUATE THESES',
        ))
        assert title.lower().endswith('for undergraduate theses')

    def test_condition_2_title_keyword_joins(self):
        """No leading connector, but the line carries title vocabulary.

        'SYSTEMS' satisfies the 'system' keyword by substring match, matching
        how _score_candidate_line already tests it.
        """
        title, _ = detect_title(self._page(
            'DIGITISING THE REGISTRAR ARCHIVE',
            'CAMPUS RECORDS SYSTEMS',
        ))
        assert title.lower().endswith('campus records systems')

    def test_condition_3_dangling_connector_on_previous_line_joins(self):
        """Neither condition 1 nor 2 holds; the previous line ends on 'FOR'."""
        title, _ = detect_title(self._page(
            'AN ATTENDANCE TRACKER FOR',
            'PUBLIC SENIOR HIGH',
        ))
        assert title.lower().endswith('public senior high')

    def test_condition_5_mid_line_connector_joins(self):
        """A connector anywhere in the line, not just at the start.

        A mid-line preposition means the line is a sentence fragment, and on a
        title page the title is the only sentence. Found by auditing the real
        corpus: 'BARANGAYMED+: … FOR BARANGAY HEALTH' / 'CENTERS IN
        MUNICIPALITY' was truncating on the word 'HEALTH'.
        """
        title, _ = detect_title(self._page(
            'A HYBRID PLATFORM FOR BARANGAY HEALTH',
            'CENTERS IN MUNICIPALITY',
        ))
        assert title.lower().endswith('centers in municipality')

    def test_condition_4_single_word_line_joins(self):
        """A one-word line cannot be an author entry, so it is admitted.

        _has_name_shape requires two to six words, so a lone token is never a
        name — while a wrapped title's final line very often is.
        """
        title, _ = detect_title(self._page(
            'A MOBILE RECORDS TOOL USING NATURAL LANGUAGE',
            'PROCESSING',
        ))
        assert title.lower().endswith('processing')

    def test_bare_name_line_is_cut_even_though_it_is_not_a_marked_author_line(self):
        """The pairing that makes the tightened gate worth it.

        'Juan Miguel Santos' has no comma, no initial, no suffix and no
        honorific, so _looks_like_author_line deliberately does NOT claim it.
        The gate is what stops it: no leading connector, no title vocabulary,
        no dangling connector on the previous line, and more than one word.
        """
        from theses.services.metadata_extraction import _looks_like_author_line

        assert not _looks_like_author_line('Juan Miguel Santos')

        title, _ = detect_title(self._page(
            'AN INVENTORY MANAGEMENT PLATFORM',
            'Juan Miguel Santos',
        ))
        assert 'Santos' not in title
        assert title.lower() == 'an inventory management platform'

    def test_strict_gate_is_unchanged_when_there_is_no_blank_structure(self):
        """The no-blank-structure path must still require a leading connector.

        It is the tighter of the two rules and was not part of this change.
        """
        text = (
            'A DEEP LEARNING APPROACH TO CROP DISEASE DETECTION\n'
            'CAMPUS RECORDS SYSTEMS\n'
        )
        title, _ = detect_title(text)

        # 'CAMPUS RECORDS SYSTEMS' carries a title keyword, which WOULD admit it
        # under the relaxed gate — proof the strict gate is still the one in
        # force here.
        assert 'CAMPUS' not in title.upper()


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

    # ── Compound tokens: hyphen and slash ──────────────────────────────────
    #
    # str.title() capitalises the first letter of each alphabetic run and
    # lowercases the rest, so a compound whose first part is an acronym came
    # out mangled: 'AI-POWERED' -> 'Ai-Powered'. This reached the repository
    # list and the topic chart.

    @pytest.mark.parametrize('raw, expected', [
        (
            'AI-POWERED ATTENDANCE MONITORING SYSTEM',
            'AI-Powered Attendance Monitoring System',
        ),
        (
            'IOT-BASED GREENHOUSE MONITORING',
            'IOT-Based Greenhouse Monitoring',
        ),
        (
            'AI/ML DRIVEN ANALYTICS PLATFORM',
            'AI/ML Driven Analytics Platform',
        ),
        (
            # Per-part punctuation strip: the '(' belongs to the first PART,
            # not to the token, so the acronym lookup has to happen after the
            # part is stripped on its own.
            '(AI-POWERED) ATTENDANCE SYSTEM',
            '(AI-Powered) Attendance System',
        ),
    ])
    def test_compound_acronym_parts_survive(self, raw, expected):
        assert normalize_title_case(raw) == expected

    def test_mixed_delimiters_rejoin_exactly(self):
        """Both delimiters in one token must come back in their own places."""
        assert normalize_title_case('AI/ML-BASED DETECTION') == (
            'AI/ML-Based Detection'
        )

    # ── Regressions: none of these may move ────────────────────────────────

    @pytest.mark.parametrize('raw, expected', [
        # 'WEB' is not an acronym, so both parts title-case as before.
        ('WEB-BASED INVENTORY SYSTEM', 'Web-Based Inventory System'),
        # Whole-token acronym match still wins before any splitting.
        ('(NLP) BASED SENTIMENT SYSTEM', '(NLP) Based Sentiment System'),
        ('SEARCH USING NLP AND OCR', 'Search Using NLP And OCR'),
        ('A MOBILE HEALTH RECORDS SYSTEM', 'A Mobile Health Records System'),
    ])
    def test_existing_behaviour_is_unchanged(self, raw, expected):
        assert normalize_title_case(raw) == expected

    def test_hyphenated_mixed_case_still_early_returns(self):
        """The compound path must sit behind the mixed-case guard.

        A title the document already cased is returned untouched, so a
        hyphenated token in a mixed-case title is never reprocessed.
        """
        original = 'AI-Powered Attendance System For Senior High'
        assert normalize_title_case(original) == original

    def test_acronym_casing_is_preserved_not_canonicalised(self):
        """Documented limit, asserted so it stays a decision.

        'IOT' stays 'IOT'; it is not rewritten to 'IoT'. This function
        preserves the document's own casing for a known acronym — the
        whole-token path has always behaved this way, and the compound path
        matches it.
        """
        assert normalize_title_case('IOT MONITORING PLATFORM') == (
            'IOT Monitoring Platform'
        )
        assert 'IoT' not in normalize_title_case('IOT-BASED MONITORING')


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

class TestDegenerateInput:
    @pytest.mark.parametrize('text', ['', '   ', '\n\n\n'])
    def test_empty_text_returns_low_confidence(self, text):
        assert detect_title(text) == ('', 'low')
