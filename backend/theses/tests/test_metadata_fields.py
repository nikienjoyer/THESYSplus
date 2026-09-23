"""Tests for the five non-title field extractors and POST /theses/extract-metadata/.

Content-level assertions use DOCX fixtures rather than synthetic PDFs on
purpose: ``_extract_docx`` joins paragraphs with a blank line, which gives the
exact blank-line structure the heuristics key on, deterministically. Synthetic
minimal PDFs cannot reproduce pypdf's line breaking reliably. The PDF path is
covered by the real THESYS+ document in ``TestRealDocumentAccuracy``.
"""
from __future__ import annotations

import io
import os
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import Role, User
from theses.models import Program
from theses.services.metadata_extraction import (
    CANONICAL_PROGRAMS,
    MAX_AUTHORS,
    MAX_KEYWORDS,
    METADATA_FIELDS,
    MIN_ABSTRACT_WORDS,
    MIN_PROSE_ALPHA_RATIO,
    MIN_YEAR,
    detect_abstract,
    detect_authors,
    detect_keywords,
    detect_program,
    detect_year,
    extract_metadata,
    max_year,
)

REAL_THESYSPLUS_PDF = os.path.join('media', 'theses', '2026', 'thesysplus-250826_1.pdf')


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='facmeta@pampangastateu.edu.ph',
        first_name='Faculty',
        last_name='Metadata',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _docx(paragraphs: list[str]) -> bytes:
    """Minimal DOCX; each entry becomes its own paragraph."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org'
            '/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.'
            'openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.'
            'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        zf.writestr(
            '_rels/.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org'
            '/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        body = ''.join(
            f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>'
            for p in paragraphs
        )
        zf.writestr(
            'word/document.xml',
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
            'openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{body}</w:body></w:document>',
        )
        zf.writestr(
            'word/_rels/document.xml.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"/>',
        )
    return buf.getvalue()


ABSTRACT_BODY = (
    'This study developed a mobile health records system for rural clinics in '
    'the province of Pampanga. The researchers applied an iterative software '
    'development methodology and evaluated the resulting platform with clinic '
    'staff using a descriptive survey instrument, reporting adoption and '
    'usability outcomes across three pilot sites.'
)

# A complete front matter with all six fields present.
FULL_FRONTMATTER = [
    'PAMPANGA STATE UNIVERSITY',
    'A MOBILE HEALTH RECORDS SYSTEM FOR RURAL CLINICS',
    'A Capstone',
    'Presented to the Faculty of',
    'In Partial Fulfillment',
    'of the Requirements for the Degree',
    'Bachelor of Science in Information Technology',
    'by:',
    'Dela Cruz, Juan M.',
    'Santos, Maria A.',
    'May 2025',
    'ABSTRACT',
    ABSTRACT_BODY,
    'Keywords: mobile health, records management, rural clinics, NLP',
]

FULL_TEXT = '\n\n'.join(FULL_FRONTMATTER)


# ---------------------------------------------------------------------------
# The enum contract
# ---------------------------------------------------------------------------

class TestProgramEnumContract:
    def test_canonical_programs_match_the_model_enum_exactly(self):
        """CANONICAL_PROGRAMS is duplicated in the pure service module.

        This assertion is what makes the duplication safe: change
        ``theses.models.Program`` and this fails immediately rather than the
        extractor silently emitting a value the serializer will reject.
        """
        assert set(CANONICAL_PROGRAMS) == set(Program.values)
        assert len(CANONICAL_PROGRAMS) == len(Program.values)

    def test_singular_information_system_is_the_enum_spelling(self):
        """Guard the singular/plural trap: documents say "Systems"."""
        assert 'BS Information System' in Program.values
        assert 'BS Information Systems' not in Program.values


# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------

class TestDetectProgram:
    @pytest.mark.parametrize('degree_line, expected', [
        ('Bachelor of Science in Information Systems', 'BS Information System'),
        ('Bachelor of Science in Information System', 'BS Information System'),
        ('Bachelor of Science in Information Technology', 'BS Information Technology'),
        ('Bachelor of Science in Computer Science', 'BS Computer Science'),
        ('Associate in Computer Technology', 'Associate in Computer Technology'),
    ])
    def test_degree_lines_map_to_enum_values(self, degree_line, expected):
        text = (
            'PAMPANGA STATE UNIVERSITY\n\n'
            'A SAMPLE THESIS TITLE FOR TESTING\n\n'
            'of the Requirements for the Degree\n\n'
            f'{degree_line}\n\n'
            'by:\n\nDela Cruz, Juan M.\n'
        )
        program, confidence = detect_program(text)

        assert program == expected
        assert program in Program.values
        assert confidence == 'high'

    @pytest.mark.parametrize('acronym, expected', [
        ('Degree: BSIT', 'BS Information Technology'),
        ('Degree: BSIS', 'BS Information System'),
        ('Degree: BSCS', 'BS Computer Science'),
    ])
    def test_acronym_degree_lines(self, acronym, expected):
        program, confidence = detect_program(f'TITLE OF THE STUDY\n\n{acronym}\n')

        assert program == expected
        assert confidence == 'high'

    def test_ocr_damaged_degree_line_uses_fuzzy_fallback(self):
        """rapidfuzz exists for this case, not for well-formed documents."""
        text = (
            'A SAMPLE THESIS\n\n'
            'Bachelor of Scienc in Informaton Systerns\n\n'
            'by:\n\nDela Cruz, Juan M.\n'
        )
        program, confidence = detect_program(text)

        assert program == 'BS Information System'
        assert confidence == 'medium'

    def test_program_words_in_title_alone_do_not_set_program(self):
        """No degree line means no program — a title is not a degree."""
        text = (
            'PAMPANGA STATE UNIVERSITY\n\n'
            'AN INFORMATION TECHNOLOGY ASSET TRACKING SYSTEM\n\n'
            'by:\n\nDela Cruz, Juan M.\n\nMay 2025\n'
        )
        program, confidence = detect_program(text)

        assert program == ''
        assert confidence == 'low'

    def test_unrecognised_degree_returns_empty_not_a_guess(self):
        """Never emit a value outside the enum — an unfillable dropdown beats
        a VALIDATION_ERROR on submit."""
        text = 'A STUDY OF SOMETHING\n\nBachelor of Arts in Communication\n'
        program, _ = detect_program(text)

        assert program == ''

    @pytest.mark.parametrize('text', ['', '   ', 'no degree information here'])
    def test_degenerate_input(self, text):
        assert detect_program(text) == ('', 'low')

    def test_never_returns_out_of_enum_value(self):
        """Property check across a spread of degree lines."""
        lines = [
            'Bachelor of Science in Information Systems',
            'Bachelor of Science in Computer Engineering',
            'Associate in Computer Technology',
            'Master of Science in Information Technology',
            'BSIT',
            'Doctor of Philosophy',
            'Bachelor of Elementary Education',
        ]
        for line in lines:
            program, _ = detect_program(f'TITLE\n\n{line}\n')
            assert program == '' or program in Program.values


# ---------------------------------------------------------------------------
# Year
# ---------------------------------------------------------------------------

class TestDetectYear:
    def test_month_year_is_high_confidence(self):
        year, confidence = detect_year('A TITLE\n\nby:\n\nDela Cruz, Juan M.\n\nMay 2025\n')

        assert year == 2025
        assert confidence == 'high'

    def test_bare_year_on_own_line_is_high_confidence(self):
        year, confidence = detect_year('A TITLE\n\nDela Cruz, Juan M.\n\n2019\n')

        assert year == 2019
        assert confidence == 'high'

    def test_embedded_year_is_medium_confidence(self):
        year, confidence = detect_year(
            'A TITLE\n\nSubmitted for the academic year 2021 requirements\n'
        )

        assert year == 2021
        assert confidence == 'medium'

    def test_latest_in_range_year_wins(self):
        """Front matter cites earlier years; it is dated by the latest."""
        year, _ = detect_year(
            'A TITLE\n\nCurriculum approved 2018, revised 2020\n\nsubmitted 2023\n'
        )

        assert year == 2023

    def test_year_below_minimum_is_rejected(self):
        assert detect_year(f'A TITLE\n\n{MIN_YEAR - 5}\n') == (None, 'low')

    def test_year_beyond_next_calendar_year_is_rejected(self):
        far_future = max_year() + 5
        assert detect_year(f'A TITLE\n\n{far_future}\n') == (None, 'low')

    def test_next_calendar_year_is_accepted(self):
        """A December submission is routinely dated the following year."""
        year, _ = detect_year(f'A TITLE\n\nDecember {max_year()}\n')

        assert year == max_year()

    def test_body_text_years_beyond_the_title_page_do_not_win(self):
        """Only the title page region is searched."""
        padding = '\n\n'.join(f'Table of contents row {i}' for i in range(80))
        year, _ = detect_year(f'A TITLE\n\nMay 2005\n\n{padding}\n\nMay 2024\n')

        assert year == 2005

    @pytest.mark.parametrize('text', ['', '   ', 'no digits at all here'])
    def test_degenerate_input(self, text):
        assert detect_year(text) == (None, 'low')


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

class TestDetectKeywords:
    @pytest.mark.parametrize('label', [
        'Keywords:', 'Keyword:', 'KEYWORDS:', 'Key words:', 'Index Terms:',
    ])
    def test_label_variants(self, label):
        keywords, confidence = detect_keywords(f'{label} mobile health, NLP, clinics\n')

        assert keywords == ['mobile health', 'NLP', 'clinics']
        assert confidence == 'high'

    def test_semicolon_separated(self):
        keywords, _ = detect_keywords('Keywords: alpha; beta; gamma\n')

        assert keywords == ['alpha', 'beta', 'gamma']

    def test_sentence_beginning_with_the_word_is_not_a_keyword_line(self):
        """Real body text from this corpus: "keywords, contextual meanings, …".

        A comma is deliberately not a valid label separator for this reason.
        """
        text = (
            'The system indexes documents by their semantic content rather than\n'
            'keywords, contextual meanings, and topic, improving efficiency.\n'
        )
        keywords, confidence = detect_keywords(text)

        assert keywords == []
        assert confidence == 'low'

    def test_wrapped_keyword_line_is_continued(self):
        text = 'Keywords: semantic search, topic modelling,\nthesis repository, SBERT\n\nCHAPTER I\n'
        keywords, _ = detect_keywords(text)

        assert 'thesis repository' in keywords
        assert 'SBERT' in keywords

    def test_duplicates_removed_case_insensitively(self):
        keywords, _ = detect_keywords('Keywords: NLP, nlp, Nlp, OCR\n')

        assert keywords == ['NLP', 'OCR']

    def test_count_is_capped(self):
        many = ', '.join(f'kw{i}' for i in range(40))
        keywords, _ = detect_keywords(f'Keywords: {many}\n')

        assert len(keywords) == MAX_KEYWORDS

    def test_single_keyword_is_medium_confidence(self):
        """One item usually means the separators were lost in extraction."""
        keywords, confidence = detect_keywords('Keywords: semantic search\n')

        assert keywords == ['semantic search']
        assert confidence == 'medium'

    def test_numeric_only_fragments_dropped(self):
        keywords, _ = detect_keywords('Keywords: NLP, 2025, , OCR\n')

        assert keywords == ['NLP', 'OCR']

    @pytest.mark.parametrize('text', ['', '   ', 'no keyword label here'])
    def test_degenerate_input(self, text):
        assert detect_keywords(text) == ([], 'low')


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------

class TestDetectAbstract:
    def test_heading_then_body(self):
        text = f'ABSTRACT\n\n{ABSTRACT_BODY}\n\nCHAPTER I\n'
        abstract, confidence = detect_abstract(text)

        assert abstract.startswith('This study developed a mobile health records system')
        assert confidence == 'high'
        assert 'CHAPTER' not in abstract

    def test_run_in_heading_on_same_line(self):
        text = f'Abstract: {ABSTRACT_BODY}\n\nKeywords: a, b\n'
        abstract, _ = detect_abstract(text)

        assert abstract.startswith('This study developed')
        assert 'Keywords' not in abstract

    def test_stops_at_keywords_line(self):
        text = f'ABSTRACT\n\n{ABSTRACT_BODY}\n\nKeywords: mobile health, NLP\n'
        abstract, _ = detect_abstract(text)

        assert 'mobile health, NLP' not in abstract

    def test_table_of_contents_row_is_not_an_abstract(self):
        """"Abstract ............ vii" is a TOC entry, not a heading."""
        text = (
            'Table of Contents\n'
            'Abstract ................................................ vii\n'
            'Chapter I ............................................... 1\n'
        )
        abstract, confidence = detect_abstract(text)

        assert abstract == ''
        assert confidence == 'low'

    def test_word_abstract_mid_sentence_is_ignored(self):
        text = 'The researchers performed abstract screening of 40 papers.\n'
        assert detect_abstract(text) == ('', 'low')

    def test_too_short_body_returns_empty(self):
        """Below the modal's minLength={20} an auto-fill would only fail submit."""
        abstract, confidence = detect_abstract('ABSTRACT\n\nShort.\n\nCHAPTER I\n')

        assert abstract == ''
        assert confidence == 'low'

    def test_wrapped_lines_are_rejoined(self):
        text = (
            'ABSTRACT\n'
            'This study examined the adoption of a semantic search system for\n'
            'undergraduate theses at a state university in central Luzon over\n'
            'two academic terms and reported the measured retrieval accuracy.\n'
            '\n\n\n'
        )
        abstract, _ = detect_abstract(text)

        assert '\n' not in abstract
        assert 'system for undergraduate theses' in abstract

    def test_hyphenated_line_break_is_rejoined(self):
        # Padded past MIN_ABSTRACT_WORDS so this exercises hyphen rejoining
        # rather than tripping the prose floor.
        text = (
            'ABSTRACT\n'
            'The researchers evaluated the develop-\n'
            'ment of a records platform for three rural clinics in the province\n'
            'of Pampanga and measured staff adoption over two academic terms.\n'
        )
        abstract, _ = detect_abstract(text)

        assert 'development of a records platform' in abstract

    def test_paragraph_breaks_preserved(self):
        text = f'ABSTRACT\n\n{ABSTRACT_BODY}\n\nA second paragraph of the abstract body text.\n'
        abstract, _ = detect_abstract(text)

        assert '\n\n' in abstract
        assert 'second paragraph' in abstract

    def test_document_without_abstract_returns_empty(self):
        """The real THESYS+ thesis has none; inventing one would be worse."""
        text = 'PAMPANGA STATE UNIVERSITY\n\nA TITLE\n\nby:\n\nDela Cruz, Juan M.\n'
        assert detect_abstract(text) == ('', 'low')

    @pytest.mark.parametrize('text', ['', '   '])
    def test_degenerate_input(self, text):
        assert detect_abstract(text) == ('', 'low')


# ---------------------------------------------------------------------------
# Table-of-contents dot leaders must never reach the Abstract field
# ---------------------------------------------------------------------------

# Real abstract prose, 150+ words, used as the "this must still work" control.
REAL_ABSTRACT_PROSE = (
    'This study designed and evaluated a semantic retrieval system for the '
    'undergraduate thesis collection of the College of Computing Studies. '
    'The researchers observed that keyword matching alone failed to surface '
    'related work when authors described the same concept with different '
    'terminology, which led students to duplicate topics that already existed '
    'in the archive. To address this, the system encodes each submitted '
    'document with a sentence transformer and ranks results by cosine '
    'similarity against the resulting vectors, rather than by lexical overlap '
    'alone. A term frequency analysis is layered on top to group approved '
    'submissions into topic clusters, allowing faculty to see which research '
    'areas are saturated and which remain underexplored across academic '
    'years. The researchers followed an iterative development methodology and '
    'evaluated the platform with faculty reviewers and graduating students '
    'over two academic terms, gathering both task completion times and '
    'perceived usefulness ratings through a descriptive survey instrument. '
    'Results indicate that retrieval relevance improved substantially over '
    'the previous keyword search, that reviewers located comparable prior '
    'work more quickly, and that respondents rated the topic trend view as '
    'useful for advising. The researchers recommend extending the corpus to '
    'earlier academic years and periodically retraining the encoder as the '
    'archive grows.'
)

# The exact structure that produced the bug: a contents listing whose ABSTRACT
# row carries dot leaders and a roman page number. ``{leader}`` is substituted
# per-case so the same document can be rendered with different leader glyphs.
_TOC_TEMPLATE = """\
TABLE OF CONTENTS

TITLE PAGE {leader} i
APPROVAL SHEET {leader} ii
ACKNOWLEDGEMENT {leader} iv
ABSTRACT {leader} viii
CHAPTER I: THE PROBLEM AND ITS BACKGROUND {leader} 1
"""

ASCII_LEADER = '.' * 41
ELLIPSIS_LEADER = '…' * 14
MIDDLE_DOT_LEADER = '·' * 20


class TestAbstractRejectsTableOfContents:
    """Regression: a contents row auto-filled the Abstract with dot leaders.

    The row "ABSTRACT ......... viii" matched the run-in heading pattern, so
    the leader text became the abstract body. It was reported at medium
    confidence, which corroborated the cause — medium is only emitted below
    200 characters, and a leader-plus-page-number string lands in that range.
    """

    def test_ascii_period_leader_row_is_rejected(self):
        abstract, confidence = detect_abstract(
            _TOC_TEMPLATE.format(leader=ASCII_LEADER)
        )

        assert abstract == ''
        assert confidence == 'low'

    @pytest.mark.parametrize('leader, description', [
        (ASCII_LEADER, 'ascii periods'),
        (ELLIPSIS_LEADER, 'ellipsis characters'),
        (MIDDLE_DOT_LEADER, 'middle dots'),
    ])
    def test_every_leader_glyph_is_rejected(self, leader, description):
        """The point of the fix: glyph-agnostic.

        The previous guard's character class only knew ASCII periods, so an
        ellipsis or middle-dot leader sailed through. Enumerating glyphs is
        unbounded — the next extractor will pick a fourth one — so the test
        pins behaviour across all three rather than the character list.
        """
        abstract, confidence = detect_abstract(_TOC_TEMPLATE.format(leader=leader))

        assert abstract == '', f'{description} leader leaked into the abstract'
        assert confidence == 'low'

    @pytest.mark.parametrize('leader', [
        ASCII_LEADER, ELLIPSIS_LEADER, MIDDLE_DOT_LEADER,
    ])
    def test_no_leader_character_survives_anywhere(self, leader):
        """Belt and braces: not merely empty, but provably leader-free."""
        abstract, _ = detect_abstract(_TOC_TEMPLATE.format(leader=leader))

        assert leader[0] not in abstract
        assert 'viii' not in abstract

    def test_arabic_page_number_row_is_rejected(self):
        text = (
            'TABLE OF CONTENTS\n\n'
            f'ABSTRACT {ASCII_LEADER} 8\n'
            f'CHAPTER I {ASCII_LEADER} 12\n'
        )
        abstract, confidence = detect_abstract(text)

        assert abstract == ''
        assert confidence == 'low'

    def test_genuine_abstract_still_extracts(self):
        """The control. The fix must not cost a real abstract."""
        abstract, confidence = detect_abstract(
            f'ABSTRACT\n\n{REAL_ABSTRACT_PROSE}\n\nCHAPTER I\n'
        )

        assert abstract.startswith('This study designed and evaluated')
        assert len(abstract.split()) > 150
        assert confidence == 'high'
        assert 'CHAPTER' not in abstract

    def test_toc_listing_plus_real_abstract_returns_the_real_one(self):
        """Skipping the contents region is what makes ordering work.

        Before the fix the contents row was found first and the search stopped
        there, so the real section further down was never reached.
        """
        text = (
            f'{_TOC_TEMPLATE.format(leader=ASCII_LEADER)}\n'
            'CHAPTER I: THE PROBLEM AND ITS BACKGROUND\n\n'
            'ABSTRACT\n\n'
            f'{REAL_ABSTRACT_PROSE}\n\n'
            'Keywords: semantic search, thesis repository\n'
        )
        abstract, confidence = detect_abstract(text)

        assert abstract.startswith('This study designed and evaluated')
        assert ASCII_LEADER[0] * 3 not in abstract
        assert 'viii' not in abstract
        assert confidence == 'high'

    def test_document_with_no_abstract_heading_returns_empty(self):
        text = (
            'PAMPANGA STATE UNIVERSITY\n\n'
            'A SEMANTIC SEARCH SYSTEM FOR THESIS RETRIEVAL\n\n'
            'Bachelor of Science in Information Systems\n\n'
            'by:\n\nDela Cruz, Juan M.\n\nMay 2025\n'
        )
        abstract, confidence = detect_abstract(text)

        assert abstract == ''
        assert confidence == 'low'

    def test_leader_only_body_under_a_bare_heading_is_rejected(self):
        """Layer 3 on its own: heading is clean, body is leaders.

        Covers the case where a contents listing has no "TABLE OF CONTENTS"
        heading to key off and the leaders land on the following line instead
        of the heading line, so only the prose test can catch it.
        """
        abstract, confidence = detect_abstract(
            f'ABSTRACT\n{ASCII_LEADER} viii\n\n\n'
        )

        assert abstract == ''
        assert confidence == 'low'

    def test_prose_floors_are_the_documented_values(self):
        """Pin the two thresholds the rejection depends on."""
        assert MIN_PROSE_ALPHA_RATIO == 0.6
        assert MIN_ABSTRACT_WORDS == 20

    def test_alpha_ratio_gap_between_prose_and_leaders_is_wide(self):
        """Evidence for the threshold choice rather than a bare assertion."""
        from theses.services.metadata_extraction import _alpha_ratio

        leader_row = f'ABSTRACT {ASCII_LEADER} viii'

        assert _alpha_ratio(leader_row) < 0.3
        assert _alpha_ratio(REAL_ABSTRACT_PROSE) > 0.75


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

class TestDetectAuthors:
    def test_blank_line_between_marker_and_names(self):
        """The THESYS+ PDF layout: "by:", blank, then contiguous names."""
        text = 'A TITLE\n\nby:\n\nQuizon, Valerie Daphne D.\nCortez, Reanne Kirby Y.\n\nMay 2026\n'
        authors, confidence = detect_authors(text)

        assert authors == ['Quizon, Valerie Daphne D.', 'Cortez, Reanne Kirby Y.']
        assert confidence == 'low'

    def test_blank_line_between_every_name(self):
        """The DOCX layout: every paragraph is its own block."""
        text = 'A TITLE\n\nby:\n\nDela Cruz, Juan M.\n\nSantos, Maria A.\n\nMay 2025\n'
        authors, _ = detect_authors(text)

        assert authors == ['Dela Cruz, Juan M.', 'Santos, Maria A.']

    def test_inline_name_after_marker(self):
        authors, _ = detect_authors('A TITLE\n\nby Juan Dela Cruz\n\n2024\n')

        assert authors == ['Juan Dela Cruz']

    @pytest.mark.parametrize('marker', ['by', 'by:', 'Submitted by:', 'Prepared by', 'Researchers:'])
    def test_marker_variants(self, marker):
        authors, _ = detect_authors(f'A TITLE\n\n{marker}\n\nDela Cruz, Juan M.\n\n2024\n')

        assert authors == ['Dela Cruz, Juan M.']

    def test_stops_at_a_line_containing_digits(self):
        text = 'A TITLE\n\nby:\n\nDela Cruz, Juan M.\n\nMay 2025\n\nSantos, Maria A.\n'
        authors, _ = detect_authors(text)

        assert authors == ['Dela Cruz, Juan M.']

    def test_stops_at_institutional_line(self):
        text = 'A TITLE\n\nby:\n\nDela Cruz, Juan M.\n\nCollege of Computing Studies\n'
        authors, _ = detect_authors(text)

        assert authors == ['Dela Cruz, Juan M.']

    def test_lowercase_particles_allowed(self):
        text = 'A TITLE\n\nby:\n\nde la Cruz, Juan M.\nvan der Berg, Anna\n'
        authors, _ = detect_authors(text)

        assert len(authors) == 2

    def test_count_is_capped(self):
        # Distinct alphabetic surnames — a digit anywhere disqualifies a line
        # as a name, so 'Surname1' would be rejected for the wrong reason.
        names = '\n'.join(
            f'Surname{chr(ord("A") + i)}, Given N.' for i in range(26)
        )
        authors, _ = detect_authors(f'A TITLE\n\nby:\n\n{names}\n')

        assert len(authors) == MAX_AUTHORS

    def test_duplicates_removed(self):
        text = 'A TITLE\n\nby:\n\nDela Cruz, Juan M.\nDELA CRUZ, JUAN M.\n'
        authors, _ = detect_authors(text)

        assert len(authors) == 1

    def test_no_marker_returns_empty(self):
        assert detect_authors('A TITLE\n\nDela Cruz, Juan M.\n') == ([], 'low')

    def test_confidence_never_exceeds_low(self):
        """Deliberate: an author block has no label to anchor on, so a line of
        Title Case words is as likely to be an adviser or a department."""
        text = 'A TITLE\n\nby:\n\nDela Cruz, Juan M.\nSantos, Maria A.\nReyes, Ana B.\n'
        _, confidence = detect_authors(text)

        assert confidence == 'low'

    @pytest.mark.parametrize('text', ['', '   '])
    def test_degenerate_input(self, text):
        assert detect_authors(text) == ([], 'low')


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_all_six_fields_from_complete_front_matter(self):
        fields = extract_metadata(FULL_TEXT)

        assert set(fields) == set(METADATA_FIELDS)
        assert fields['title']['value'] == 'A Mobile Health Records System For Rural Clinics'
        assert fields['program']['value'] == 'BS Information Technology'
        assert fields['year']['value'] == 2025
        assert fields['authors']['value'] == ['Dela Cruz, Juan M.', 'Santos, Maria A.']
        assert fields['keywords']['value'] == [
            'mobile health', 'records management', 'rural clinics', 'NLP',
        ]
        assert fields['abstract']['value'].startswith('This study developed')

    def test_value_types_are_form_ready(self):
        fields = extract_metadata(FULL_TEXT)

        assert isinstance(fields['title']['value'], str)
        assert isinstance(fields['abstract']['value'], str)
        assert isinstance(fields['program']['value'], str)
        assert isinstance(fields['authors']['value'], list)
        assert isinstance(fields['keywords']['value'], list)
        assert isinstance(fields['year']['value'], int)

    def test_every_field_carries_a_valid_confidence(self):
        fields = extract_metadata(FULL_TEXT)

        for field in METADATA_FIELDS:
            assert fields[field]['confidence'] in ('high', 'medium', 'low')

    def test_empty_text_yields_all_empty_fields(self):
        fields = extract_metadata('')

        assert fields['title']['value'] == ''
        assert fields['abstract']['value'] == ''
        assert fields['authors']['value'] == []
        assert fields['keywords']['value'] == []
        assert fields['program']['value'] == ''
        assert fields['year']['value'] is None

    def test_one_failing_extractor_does_not_lose_the_others(self, monkeypatch):
        from theses.services import metadata_extraction as me

        def boom(_text):
            raise RuntimeError('simulated extractor crash')

        monkeypatch.setattr(me, 'detect_keywords', boom)
        fields = me.extract_metadata(FULL_TEXT)

        assert fields['keywords']['value'] == []
        assert fields['keywords']['confidence'] == 'low'
        assert fields['title']['value'] != ''
        assert fields['program']['value'] == 'BS Information Technology'


# ---------------------------------------------------------------------------
# Accuracy against the one real document in the repository
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(REAL_THESYSPLUS_PDF),
    reason='media/ is untracked; real THESYS+ PDF not present in this checkout',
)
class TestRealDocumentAccuracy:
    """Per-field accuracy evidence for the real THESYS+ capstone (93 pages).

    Abstract and keywords come back EMPTY and that is correct: this document
    contains neither an abstract section nor a labelled keywords line. Verified
    by scanning all 93 pages for those headings.
    """

    @pytest.fixture(scope='class')
    def fields(self):
        from theses.services.text_extractor import METADATA_PAGES, ThesisTextExtractor

        result = ThesisTextExtractor().extract(
            REAL_THESYSPLUS_PDF, max_pages=METADATA_PAGES,
        )
        assert result.success
        return extract_metadata(result.text)

    def test_title(self, fields):
        assert fields['title']['value'] == (
            'THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend '
            'Analysis System for CCS Undergraduate Theses at Pampanga State '
            'University'
        )
        assert fields['title']['confidence'] == 'high'

    def test_all_seven_authors(self, fields):
        assert fields['authors']['value'] == [
            'Quizon, Valerie Daphne D.',
            'Cortez, Reanne Kirby Y.',
            'Gonzaga, Kurt Ross E.',
            'Miclat, John Mar L.',
            'Romero, Tommy M.',
            'Salonga, Romel S.',
            'Torres, Jerry Vic P.',
        ]

    def test_program_maps_plural_document_wording_to_singular_enum(self, fields):
        """The document reads "Information Systems"; the enum is singular."""
        assert fields['program']['value'] == 'BS Information System'
        assert fields['program']['value'] in Program.values
        assert fields['program']['confidence'] == 'high'

    def test_year_from_may_2026(self, fields):
        assert fields['year']['value'] == 2026
        assert fields['year']['confidence'] == 'high'

    def test_abstract_absent_from_document(self, fields):
        assert fields['abstract']['value'] == ''

    def test_keywords_absent_from_document(self, fields):
        assert fields['keywords']['value'] == []


# ---------------------------------------------------------------------------
# POST /theses/extract-metadata/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExtractMetadataEndpoint:
    URL_NAME = 'thesis-extract-metadata'

    def test_requires_authentication(self, client):
        response = client.post(reverse(self.URL_NAME), data={})

        assert response.status_code in (401, 403)

    def test_missing_file_returns_400(self, client, faculty_user):
        response = client.post(
            reverse(self.URL_NAME),
            data={},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'MISSING_FILE'

    def test_wrong_file_type_rejected(self, client, faculty_user):
        bad = SimpleUploadedFile('notes.txt', b'text', content_type='text/plain')
        response = client.post(
            reverse(self.URL_NAME),
            data={'file': bad},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'FILE_TYPE_NOT_ALLOWED'

    def test_oversized_file_rejected(self, client, faculty_user):
        from theses.views import ThesisExtractMetadataView

        oversized = SimpleUploadedFile(
            'big.pdf',
            b'x' * (ThesisExtractMetadataView.MAX_FILE_SIZE_BYTES + 1),
            content_type='application/pdf',
        )
        response = client.post(
            reverse(self.URL_NAME),
            data={'file': oversized},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert response.status_code == 400
        assert response.json()['error']['code'] == 'FILE_TOO_LARGE'

    def test_cap_matches_extract_title_endpoint(self):
        from theses.views import ThesisExtractMetadataView, ThesisExtractTitleView

        assert (
            ThesisExtractMetadataView.MAX_FILE_SIZE_BYTES
            == ThesisExtractTitleView.MAX_FILE_SIZE_BYTES
            == 25 * 1024 * 1024
        )

    def test_docx_returns_every_field(self, client, faculty_user):
        upload = SimpleUploadedFile(
            'proposal.docx',
            _docx(FULL_FRONTMATTER),
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )
        response = client.post(
            reverse(self.URL_NAME),
            data={'file': upload},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {'fields', 'filled_fields', 'method', 'message'}
        assert body['method'] == 'python_docx'
        assert set(body['fields']) == set(METADATA_FIELDS)
        for field in METADATA_FIELDS:
            assert set(body['fields'][field]) == {'value', 'confidence'}
            assert body['fields'][field]['confidence'] in ('high', 'medium', 'low')

        assert body['fields']['program']['value'] == 'BS Information Technology'
        assert body['fields']['year']['value'] == 2025
        assert sorted(body['filled_fields']) == sorted(METADATA_FIELDS)
        assert 'All fields were detected' in body['message']

    def test_partial_extraction_lists_missing_fields(self, client, faculty_user):
        upload = SimpleUploadedFile(
            'sparse.docx',
            # Sparse on purpose: no abstract, no keywords, no degree line, so
            # those three fields come back empty. It still carries two distinct
            # title-page phrases ('A Capstone', 'Presented to') and enough text
            # to clear the document-type gate — a document that cannot be
            # recognised as a thesis at all is a different test.
            _docx([
                'PAMPANGA STATE UNIVERSITY',
                'College of Computing Studies',
                'A SEMANTIC SEARCH SYSTEM FOR THESIS RETRIEVAL',
                'A Capstone',
                'Presented to the Faculty of',
                'by:',
                'Dela Cruz, Juan M.',
                'May 2025',
                'Main Campus, City of San Fernando, Pampanga, Philippines',
            ]),
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )
        response = client.post(
            reverse(self.URL_NAME),
            data={'file': upload},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        body = response.json()
        assert response.status_code == 200
        assert body['fields']['abstract']['value'] == ''
        assert body['fields']['keywords']['value'] == []
        assert body['fields']['program']['value'] == ''
        assert 'abstract' not in body['filled_fields']
        assert 'program' not in body['filled_fields']
        assert 'abstract' in body['message']

    def test_nothing_is_persisted(self, client, faculty_user):
        from theses.models import Thesis

        before = Thesis.objects.count()
        upload = SimpleUploadedFile(
            'proposal.docx',
            _docx(FULL_FRONTMATTER),
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )
        client.post(
            reverse(self.URL_NAME),
            data={'file': upload},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert Thesis.objects.count() == before

    def test_unreadable_document_returns_empty_envelope(self, client, faculty_user):
        """Extraction failure must still return the full field shape so the
        frontend never has to special-case a missing key."""
        upload = SimpleUploadedFile(
            'broken.docx', b'not a real docx at all', content_type='application/octet-stream',
        )
        response = client.post(
            reverse(self.URL_NAME),
            data={'file': upload},
            HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
        )

        assert response.status_code == 200
        body = response.json()
        assert set(body['fields']) == set(METADATA_FIELDS)
        assert body['filled_fields'] == []
        assert body['fields']['authors']['value'] == []
        assert body['fields']['year']['value'] is None
        assert body['fields']['title']['value'] == ''


def test_extract_title_response_contract_unchanged(client, faculty_user):
    """The new endpoint must not have altered the old one's contract."""
    upload = SimpleUploadedFile(
        'proposal.docx',
        _docx(FULL_FRONTMATTER),
        content_type=(
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document'
        ),
    )
    response = client.post(
        reverse('thesis-extract-title'),
        data={'file': upload},
        HTTP_AUTHORIZATION=f'Bearer {_bearer(faculty_user)}',
    )

    assert response.status_code == 200
    assert set(response.json()) == {'detected_title', 'confidence', 'method', 'message'}
