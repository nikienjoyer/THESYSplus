"""Round B regression tests for metadata extraction improvements.

B1 — Year detection: incidental year rejection
B2 — Title start-line: continuation blocking & lone acronym acceptance
B3 — Keywords label shapes: bare labels, slash, ACM no-separator
B4 — Quote folding: curly apostrophe → straight

These lock in the behaviour added by Round B. Every test is DESIGNED and not
copied — each exercises a distinct code path and specifies why it matters.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from theses.services.metadata_extraction import (
    detect_keywords,
    detect_title,
    detect_year,
    fold_quotes,
)
from theses.services.text_extractor import ThesisTextExtractor


REAL_MEMOLOOP_PDF = (
    Path(__file__).resolve().parents[2]
    / 'media' / 'theses' / '2026' / 'MEMOLOOP.pdf'
)
PHASE6_TITLE_PDF_ROOT = (
    Path(__file__).resolve().parents[2]
    / 'media' / 'theses' / '2026'
)
EMERGENCY_COMMUNICATION_PDF = (
    PHASE6_TITLE_PDF_ROOT
    / '31B_A_117_EMERGENCY_COMMUNICATION_PLATFORM_FOR_ABUSE_REPORT_IN_A_MOBILE_APPLICATION.pdf'
)

# Phase 6 review set: expected values were checked against each PDF's printed
# title page. The corpus is not tracked in every checkout, so these integration
# canaries skip individually when their source PDF is unavailable.
PHASE6_TITLE_PDF_CASES = [
    (
        'MedicScale.pdf',
        "MedicScale: An Android Application for Patients' Medical Chart",
    ),
    (
        'MAMALAKAYA.pdf',
        'Mamalakaya: A Web-based HIV Awareness Campaign Site with an '
        'Educational Game and Testing Centers Directory',
    ),
    (
        'AQUAFLOW.pdf',
        'AQUAFLOW: An Arduino-Powered Smart Irrigation System For Gumain Dam',
    ),
    (
        'CODEQUEST.pdf',
        'CODEQUEST: When Java Programming Meets Playful Learning',
    ),
    (
        'DormHonorio.pdf',
        'DormHonorio: Dormitory Booking and Algorithm-Driven Roommate '
        'Matching Mobile Application for Honorians',
    ),
    (
        'E-PANGASIWA.pdf',
        'E-pangasiwa: Data Dashboard for Business Establishment Monitoring '
        'for the Office of Municipal Treasury of the Municipality of Bacolor, '
        'Pampanga',
    ),
    (
        'EXTHEALTH.pdf',
        'EXTHEALTH: A Browser Extension For Health Information On X Using '
        'Natural Language Processing (NLP)',
    ),
    (
        'MY_HONORIAN_BUDDY.pdf',
        'My Honorian Buddy: A Web-Based Peer-Tutoring System For The Students '
        'Of Pampanga State University',
    ),
    (
        'SIMULATION_OF_LOGIC_GATES_CIRCUITS_TEST_AND_GUIDE_USING_ANDROID_APPLICATION.pdf',
        'Simulation Of Logic Gates Circuits Test And Guide Using Android '
        'Application',
    ),
    (
        'SINDALAN_CONNECT.pdf',
        'Sindalan Connect: A Next Generation Local Community Management '
        'System Powered By AI Chatbot And Emergency Response',
    ),
    (
        'SISTEMA_de_OBRA.pdf',
        'SISTEMA de OBRA: TRAINING MONITORING SYSTEM',
    ),
    (
        'Web-Based_Qualifying_Examination_for_Accountancy_Students_of_Don_Honorio_Ventura_State_University__Main_Campus.pdf',
        'Web-Based Qualifying Examination for Accountancy Students of Don '
        'Honorio Ventura State University – Main Campus',
    ),
    # Additional source-PDF checks requested for the colon prefix and printed
    # all-caps casing behavior.
    (
        'TASKGROVE.pdf',
        'TASKGROVE: A Tree-Based Project Management Application',
    ),
    (
        'DHVCAT.pdf.pdf',
        'DHVCHAT: A Web-Based Intelligent Chat Assistant For The Admissions '
        'Office Using Natural Language Processing',
    ),
]

# Phase 7 keyword review set. Expected lists were transcribed from the printed
# keyword sections on each source PDF's first page, not from stored metadata.
PHASE7_KEYWORD_PDF_CASES = [
    (
        'ANIDELIVERY.pdf.pdf',
        [
            'AniDelivery', 'Digital Marketplace', 'Supply Chain Management',
            'Over Supply', 'Under Supply', 'Consumer',
        ],
    ),
    (
        'DORMIFY.pdf',
        ['Dorm Finder', 'Management System', 'Geofencing Technology'],
    ),
    (
        'MEMOLOOP.pdf',
        [
            'Digital Flashcards', 'MemoLoop mobile application',
            'Learning and Memorizing Information',
        ],
    ),
    (
        'VAXTRACK.pdf.pdf',
        [
            'Web Application', 'Animal bites', 'Public Health Concern',
            'Vaccination Tracking and Management', 'VaxTrack', 'User-friendly',
            'Accessible', 'Manage Animal Welfare Information',
            'Rabies Prevention',
        ],
    ),
    (
        'HTEFinder.pdf',
        [
            'On-the-Job Training', 'Host Training Establishment',
            'Geofencing Technology', 'Expert System', 'Laravel Framework',
            'MySQL Database',
        ],
    ),
]

# Phase 8 source checks: these values were compared with the printed keyword
# sections. A None page limit means the DOCX extractor's flat paragraph stream.
PHASE8_KEYWORD_SOURCE_CASES = [
    (
        'HUBISKO.pdf', 15,
        ['Web Based Automation System', 'Scholarship'], 'medium',
    ),
    (
        'EXTHEALTH.pdf', 15,
        [
            'Health Misinformation', 'Browser Extension', 'Fact-checking',
            'X', 'Twitter', 'Social Media',
        ],
        'high',
    ),
    (
        'APPOKO.pdf', 15,
        [
            'Elderly healthcare management', 'web-based system',
            'GPS tracking', 'Agile Software Development Methodology',
            'Web-based Approach',
        ],
        'high',
    ),
    ('thesysplus-250826_1.pdf', 15, [], 'low'),
    (
        'AQUAFLOW.pdf', 10,
        [
            'Smart Irrigation System', 'Arduino Technology',
            'Blynk Application', 'IoT (Internet of Things)',
            'Water Flow Control', 'Water Level Monitoring',
        ],
        'high',
    ),
    (
        'COMPAWNION.pdf.pdf', 10,
        [
            'Geo-location', 'Profile Management', 'Stray pets', 'Dogs',
            'Cats', 'Mabalacat City',
        ],
        'high',
    ),
    (
        'iSecure.docx', None,
        [
            'iSecure', 'Access Control', 'RFID', 'Facial Recognition', 'OCR',
            'Security Operations', 'ISO/IEC 25010', 'Agile Scrum',
        ],
        'high',
    ),
    (
        'ModeYul.pdf', 10,
        ['Programming', 'Unity Software', 'C#', '2D', 'Game Ap'],
        'medium',
    ),
    (
        'TASKGROVE.pdf', 10,
        ['project management', 'tree-based', 'task management', 'monitoring'],
        'medium',
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# B1 — Year detection: _is_incidental_year rejects non-date occurrences
# ═══════════════════════════════════════════════════════════════════════════

class TestYearRejectsIncidental:
    """B1: bare years in citations, statutes, postal codes and IDs → None."""

    def test_citation_parenthesised(self):
        """'(BLS, 2021)' is an inline citation, not a submission date."""
        year, conf = detect_year('(BLS, 2021). Software developers\n')
        assert year is None and conf == 'low'

    def test_citation_author_year(self):
        """'Ranada (2020)' — author-year citation."""
        year, conf = detect_year('Ranada (2020) reported that the system\n')
        assert year is None and conf == 'low'

    def test_statute_reference(self):
        """'E-Commerce Act of 2000' — Philippine statute."""
        year, conf = detect_year('E-Commerce Act of 2000.\n')
        assert year is None and conf == 'low'

    def test_postal_code(self):
        """'Bacolor, Pampanga 2001 Philippines' — postal address."""
        year, conf = detect_year('Bacolor, Pampanga 2001 Philippines\n')
        assert year is None and conf == 'low'

    def test_student_id_email(self):
        """'2020@dhvsu.edu.ph' — student number as email prefix."""
        year, conf = detect_year('2020@dhvsu.edu.ph\n')
        assert year is None and conf == 'low'

    def test_citation_comma_before_year(self):
        """'Prevention, 2021)' — comma-then-year inside a citation."""
        year, conf = detect_year('Prevention, 2021) noted an increase\n')
        assert year is None and conf == 'low'

    def test_line_wrapped_cited_statistic_at_line_end_is_not_a_thesis_year(self):
        text = (
            'A TITLE\n'
            "According to the Philippine Statistics Authority's (PSA) 2017\n"
            'National Demographic and Health Survey, one in four women...\n'
        )
        assert detect_year(text) == (None, 'low')


class TestYearAcceptsLegitimate:
    """B1: legitimate year shapes must still be detected."""

    def test_month_year_high(self):
        """'May 2026' on a title page → high confidence."""
        year, conf = detect_year('Bacolor, Pampanga\nMay 2026\n')
        assert year == 2026 and conf == 'high'

    def test_abstract_month_year_does_not_override_title_page_date(self):
        text = (
            'A TITLE\n'
            'Bacolor, Pampanga May 2024\n'
            'ABSTRACT\n'
            'The survey includes a report published in July 2025.\n'
        )
        assert detect_year(text) == (2024, 'high')

    def test_abstract_date_without_title_page_date_is_unknown(self):
        text = (
            'A TITLE\n'
            'ABSTRACT\n'
            'The survey includes a report published in July 2025.\n'
        )
        assert detect_year(text) == (None, 'low')

    def test_run_in_abstract_date_does_not_override_title_page_date(self):
        text = (
            'A TITLE\n'
            'May 2024\n'
            'Abstract: The survey includes a report published in July 2025.\n'
        )
        assert detect_year(text) == (2024, 'high')

    def test_bare_year_own_line_high(self):
        """A bare year on its own line → high confidence."""
        year, conf = detect_year('Some header\n2025\nMore text\n')
        assert year == 2025 and conf == 'high'

    def test_academic_year_midsentence(self):
        """'academic year 2021' mid-sentence — DATE_WORD exemption fires."""
        year, conf = detect_year('for academic year 2021 requirements\n')
        assert year == 2021 and conf == 'medium'

    def test_school_year_abbreviation(self):
        """'S.Y. 2024' — abbreviated school year."""
        year, conf = detect_year('Enrolled during S.Y. 2024\n')
        assert year == 2024 and conf == 'medium'


# Emergency source-PDF regression: the first-page 2017 is a cited statistic.
class TestEmergencyCommunicationPDFYear:
    def test_cited_statistic_does_not_supply_submission_year(self):
        if not EMERGENCY_COMMUNICATION_PDF.exists():
            pytest.skip('emergency-communication source PDF not present')

        extracted = ThesisTextExtractor().extract(
            str(EMERGENCY_COMMUNICATION_PDF), max_pages=1,
        )
        assert extracted.success, extracted.error
        assert detect_year(extracted.text) == (None, 'low')


# ═══════════════════════════════════════════════════════════════════════════
# B2 — Title start-line selection
# ═══════════════════════════════════════════════════════════════════════════

class TestTitleStartLineBlocking:
    """B2(a): continuation lines must not be chosen as the title start."""

    def test_using_not_a_title_start(self):
        """'USING FUZZY LOGIC ...' is a continuation, not a start."""
        text = ('UNIVERSITY NAME\n\n'
                'CAREER TRACK MOBILE APPLICATION\n'
                'USING FUZZY LOGIC FOR HIGH SCHOOL\n\n'
                'A Capstone Project\n')
        title, _ = detect_title(text)
        assert 'CAREER TRACK' in title.upper()
        assert 'USING' in title.upper()  # joined as continuation

    def test_for_not_a_title_start(self):
        """A line starting with 'FOR' cannot be a title start."""
        text = ('UNIVERSITY\n\n'
                'SMART SCHEDULING SYSTEM\n'
                'FOR FACULTY AND STUDENTS\n\n'
                'A Thesis\n')
        title, _ = detect_title(text)
        assert 'SMART SCHEDULING' in title.upper()
        assert 'FOR FACULTY' in title.upper()

    def test_of_not_a_title_start(self):
        """A line starting with 'OF' cannot be a title start."""
        text = ('UNIVERSITY\n\n'
                'DEVELOPMENT AND IMPLEMENTATION\n'
                'OF AN ENROLLMENT SYSTEM\n\n'
                'A Capstone Project\n')
        title, _ = detect_title(text)
        assert 'DEVELOPMENT' in title.upper()


class TestTitleLoneAcronym:
    """B2(b): a lone acronym line ending in ':' is a valid title start."""

    def test_memoloop_colon(self):
        """'MEMOLOOP:' on its own line → accepted as title start."""
        text = ('UNIVERSITY\n\n'
                'MEMOLOOP:\n'
                'A CUSTOMIZABLE DIGITAL LEARNING\n'
                'FLASHCARDS FOR MEMORIZATION\n\n'
                'A Capstone Project\n')
        title, _ = detect_title(text)
        assert title == (
            'MEMOLOOP: A Customizable Digital Learning '
            'Flashcards For Memorization'
        )

    @pytest.mark.skipif(
        not REAL_MEMOLOOP_PDF.exists(),
        reason='media/ is untracked; real MEMOLOOP PDF not present in this checkout',
    )
    def test_real_memoloop_pdf_keeps_brand_prefix(self):
        extracted = ThesisTextExtractor().extract(
            str(REAL_MEMOLOOP_PDF), max_pages=3,
        )
        title, _ = detect_title(extracted.text)
        assert title == (
            'MEMOLOOP: A Customizable Digital Learning Flashcards '
            'For Memorization Assessment'
        )

    def test_abstract_colon_still_rejected(self):
        """'ABSTRACT:' must still be caught by _SECTION_NOISE before the
        lone-acronym rule fires.  Locks the ordering of checks."""
        text = 'ABSTRACT:\nSome thesis content about the study\n'
        title, _ = detect_title(text)
        assert title.upper() != 'ABSTRACT:'

    def test_keywords_colon_still_rejected(self):
        """A bare keyword label and its value line are not a title."""
        text = 'Keywords:\ndata mining, analytics, visualization\n'
        assert detect_title(text) == ('', 'low')


    def test_populated_keywords_line_is_not_a_title(self):
        text = 'Keywords: data mining, predictive analytics, enrollment\n'
        assert detect_title(text) == ('', 'low')

    def test_populated_keywords_line_ends_title_join(self):
        text = (
            'UNIVERSITY\n\n'
            'SMART CAMPUS SYSTEM\n'
            'Keywords: monitoring, analytics\n\n'
        )
        title, _ = detect_title(text)
        assert title == 'Smart Campus System'


class TestPhase6TitlePDFReview:
    @pytest.mark.parametrize('pdf_name, expected', PHASE6_TITLE_PDF_CASES)
    def test_real_title_page_matches_extraction(self, pdf_name, expected):
        path = PHASE6_TITLE_PDF_ROOT / pdf_name
        if not path.exists():
            pytest.skip(f'corpus PDF not present in this checkout: {pdf_name}')

        extracted = ThesisTextExtractor().extract(str(path), max_pages=5)
        assert extracted.success, extracted.error

        title, _ = detect_title(extracted.text)
        assert title == expected

class TestTitleCanariesSurviveB2:
    """B2 canary: titles starting with 'A'/'An'/'The' must not be blocked."""

    @pytest.mark.parametrize('title_text', [
        'A Web-Based Qualifying Examination System',
        'An Android Application for Patients and Clinics',
        'The Design and Implementation of a Portal',
    ])
    def test_opening_article_allowed(self, title_text):
        text = f'UNIVERSITY\n\n{title_text}\n\nA Capstone Project\n'
        title, _ = detect_title(text)
        assert title, f'Title starting with article was rejected: {title_text!r}'


class TestShortTitleLines:
    def test_smart_parking_is_accepted_as_a_two_word_title(self):
        text = (
            'PAMPANGA STATE UNIVERSITY\n'
            'SMART PARKING\n'
            'A Capstone Project\n'
        )
        title, _ = detect_title(text)
        assert title == 'Smart Parking'

    def test_bare_two_word_author_name_is_not_a_title(self):
        assert detect_title('John Smith') == ('', 'low')


# ═══════════════════════════════════════════════════════════════════════════
# B3 — Keywords label shapes
# ═══════════════════════════════════════════════════════════════════════════

class TestKeywordsLabelShapes:
    """B3: bare labels, slash forms, ACM no-separator."""

    def test_bare_capitalised_label_nextline(self):
        """'Keywords' on its own line, list on the next line."""
        text = 'Keywords\naeroponics; fuzzy logic; indoor\n'
        kw, conf = detect_keywords(text)
        assert 'aeroponics' in kw
        assert 'fuzzy logic' in kw
        assert 'indoor' in kw
        assert conf == 'high'

    def test_keyword_slash_s_colon(self):
        """'Keyword/s:' — slash variant."""
        text = 'Keyword/s: alumni portal, tracker, analytics\n'
        kw, conf = detect_keywords(text)
        assert len(kw) == 3
        assert 'alumni portal' in kw

    def test_all_caps_keyword_slash_s_bare_label_nextline(self):
        """Uppercase slash label on its own line keeps the following list."""
        text = 'KEYWORD/S\nmachine learning; prediction; analytics\n'
        kw, conf = detect_keywords(text)
        assert kw == ['machine learning', 'prediction', 'analytics']
        assert conf == 'high'

    def test_acm_no_separator_label(self):
        """'Keywords Dorm Finder, Management System, Geofencing'.
        No colon/dash between label and values — space separator only."""
        text = 'Keywords Dorm Finder, Management System, Geofencing\n'
        kw, conf = detect_keywords(text)
        assert 'Geofencing' in kw
        assert 'Dorm Finder' in kw

    def test_all_caps_keywords_label(self):
        """'KEYWORDS' (all caps) bare label with next-line list."""
        text = 'KEYWORDS\nmachine learning; prediction; analytics\n'
        kw, conf = detect_keywords(text)
        assert 'machine learning' in kw

    def test_lowercase_bare_rejected(self):
        """'keywords, contextual meanings' — lowercase body prose must NOT match.
        The capitalisation guard in _KEYWORDS_LABEL_LOOSE is load-bearing."""
        text = 'keywords, contextual meanings, and topic, improving\n'
        kw, _ = detect_keywords(text)
        assert kw == []

    def test_bare_label_before_heading_rejected(self):
        """'Keywords' followed by a section heading → no keywords extracted."""
        text = 'Keywords\nIntroduction\n'
        kw, _ = detect_keywords(text)
        assert kw == []

    def test_bare_label_nextline_no_separator_rejected(self):
        """Bare label + next line WITHOUT any list separator → rejected.
        The _KEYWORD_SPLIT guard stops body prose from being swallowed."""
        text = 'Keywords\nThe study examined various approaches\n'
        kw, _ = detect_keywords(text)
        assert kw == []

    def test_wrapped_single_word_completes_keyword_and_stops_at_author(self):
        text = (
            'Keywords: alpha, beta, Geofencing\n'
            'Technology\n'
            'Bernal, Denisse Jasmine V.\n'
        )
        kw, confidence = detect_keywords(text)

        assert kw == ['alpha', 'beta', 'Geofencing Technology']
        assert confidence == 'high'

    def test_wrapped_conjunction_phrase_completes_final_keyword(self):
        text = (
            'Keywords\n'
            'Digital Flashcards, MemoLoop mobile application, Learning\n'
            'and Memorizing Information\n'
            '1.INTRODUCTION\n'
            'The introduction begins here.\n'
        )
        kw, confidence = detect_keywords(text)

        assert kw == [
            'Digital Flashcards', 'MemoLoop mobile application',
            'Learning and Memorizing Information',
        ]
        assert confidence == 'high'

    def test_wrapped_list_lines_are_not_rejected_as_author_names(self):
        text = (
            'Keywords\n'
            'alpha term, beta phrase, gamma system,\n'
            'delta model, epsilon platform\n'
            'Bernal, Denisse Jasmine V.\n'
        )
        kw, _ = detect_keywords(text)

        assert kw == [
            'alpha term', 'beta phrase', 'gamma system',
            'delta model', 'epsilon platform',
        ]

    def test_short_sentence_with_a_comma_is_not_appended(self):
        text = (
            'Keywords: alpha, beta, technology,\n'
            'Technology improves access, and supports students.\n'
            '1. INTRODUCTION\n'
        )
        kw, _ = detect_keywords(text)

        assert kw == ['alpha', 'beta', 'technology']

    def test_trailing_list_delimiter_caps_confidence(self):
        kw, confidence = detect_keywords(
            'Keywords: alpha, beta, gamma,\n1. INTRODUCTION\n'
        )

        assert kw == ['alpha', 'beta', 'gamma']
        assert confidence == 'medium'


class TestPhase7KeywordPDFReview:
    @pytest.mark.parametrize('pdf_name, expected', PHASE7_KEYWORD_PDF_CASES)
    def test_real_keyword_section_matches_printed_pdf(self, pdf_name, expected):
        path = PHASE6_TITLE_PDF_ROOT / pdf_name
        if not path.exists():
            pytest.skip(f'corpus PDF not present in this checkout: {pdf_name}')

        extracted = ThesisTextExtractor().extract(str(path), max_pages=1)
        assert extracted.success, extracted.error

        keywords, confidence = detect_keywords(extracted.text)
        assert keywords == expected
        assert confidence == 'high'


class TestPhase8KeywordSources:
    @pytest.mark.parametrize(
        'file_name,max_pages,expected,expected_confidence',
        PHASE8_KEYWORD_SOURCE_CASES,
    )
    def test_current_keyword_result_matches_printed_source(
        self, file_name, max_pages, expected, expected_confidence,
    ):
        path = PHASE6_TITLE_PDF_ROOT / file_name
        if not path.exists():
            pytest.skip(f'corpus source not present in this checkout: {file_name}')

        extracted = ThesisTextExtractor().extract(str(path), max_pages=max_pages)
        assert extracted.success, extracted.error
        assert detect_keywords(extracted.text) == (expected, expected_confidence)

    def test_cyberescape_image_backed_keyword_label_is_read_with_one_page_ocr(self):
        path = PHASE6_TITLE_PDF_ROOT / 'CYBERESCAPE.pdf'
        if not path.exists():
            pytest.skip('CYBERESCAPE source PDF not present in this checkout')

        extracted = ThesisTextExtractor().extract(str(path), max_pages=1)
        if extracted.method != 'ocr_tesseract':
            pytest.skip('one-page OCR is unavailable in this environment')

        assert detect_keywords(extracted.text) == (['CyberEscape'], 'medium')


class TestKeywordFalsePositiveBoundaries:
    def test_weak_author_line_after_trailing_comma_is_not_added(self):
        text = 'Keywords: alpha, beta,\nSmith, Jane\n1. INTRODUCTION\n'
        assert detect_keywords(text) == (['alpha', 'beta'], 'medium')

    def test_prose_after_wrapped_list_is_not_added(self):
        text = (
            'Keywords: alpha, beta,\n'
            'gamma system\n'
            'Introduction\n'
            'The system supports students across the campus.\n'
        )
        assert detect_keywords(text) == (
            ['alpha', 'beta', 'gamma system'], 'high',
        )


class TestKeywordsStrictStillWorks:
    """B3 regression: strict label shapes that worked before must still work."""

    def test_keywords_colon(self):
        text = 'Keywords: data mining, predictive analytics, enrollment\n'
        kw, _ = detect_keywords(text)
        assert len(kw) == 3

    def test_key_words_dash(self):
        text = 'Key words - AI, machine learning, NLP\n'
        kw, _ = detect_keywords(text)
        assert 'AI' in kw


# ═══════════════════════════════════════════════════════════════════════════
# B4 — Quote folding
# ═══════════════════════════════════════════════════════════════════════════

class TestQuoteFolding:
    """B4: typographic quotes → ASCII in both fold_quotes and detect_title."""

    def test_fold_quotes_curly_apostrophe(self):
        assert fold_quotes('NOAH\u2019S ARK') == "NOAH'S ARK"

    def test_fold_quotes_double_curly(self):
        assert fold_quotes('\u201cHello\u201d') == '"Hello"'

    def test_fold_quotes_preserves_dashes(self):
        """En/em dashes must NOT be folded."""
        assert fold_quotes('Campus \u2013 Bacolor') == 'Campus \u2013 Bacolor'
        assert fold_quotes('Title \u2014 Subtitle') == 'Title \u2014 Subtitle'

    def test_fold_quotes_empty_string(self):
        assert fold_quotes('') == ''

    def test_detect_title_folds_curly_apostrophe(self):
        """End-to-end: a title with a curly apostrophe comes out straight."""
        text = 'UNIVERSITY\n\nCOMPAWNION: NOAH\u2019S ARK DOG SHELTER\n\nA Capstone Project\n'
        title, _ = detect_title(text)
        assert "Noah's Ark" in title
        assert '\u2019' not in title

    def test_all_caps_possessive_title_lowers_s_after_apostrophe(self):
        title, _ = detect_title('NOAH\u2019S ARK DOG AND CAT SHELTER')
        assert title == "Noah's Ark Dog And Cat Shelter"

    def test_detect_title_folds_left_double_quote(self):
        text = 'UNIVERSITY\n\n\u201cSMART\u201d CAMPUS SYSTEM\n\nA Thesis\n'
        title, _ = detect_title(text)
        assert '\u201c' not in title
        assert '\u201d' not in title
