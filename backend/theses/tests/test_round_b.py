"""Round B regression tests for metadata extraction improvements.

B1 — Year detection: incidental year rejection
B2 — Title start-line: continuation blocking & lone acronym acceptance
B3 — Keywords label shapes: bare labels, slash, ACM no-separator
B4 — Quote folding: curly apostrophe → straight

These lock in the behaviour added by Round B. Every test is DESIGNED and not
copied — each exercises a distinct code path and specifies why it matters.
"""
from __future__ import annotations

import pytest

from theses.services.metadata_extraction import (
    detect_keywords,
    detect_title,
    detect_year,
    fold_quotes,
)


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


class TestYearAcceptsLegitimate:
    """B1: legitimate year shapes must still be detected."""

    def test_month_year_high(self):
        """'May 2026' on a title page → high confidence."""
        year, conf = detect_year('Bacolor, Pampanga\nMay 2026\n')
        assert year == 2026 and conf == 'high'

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
        assert title.upper().startswith('MEMOLOOP')

    def test_abstract_colon_still_rejected(self):
        """'ABSTRACT:' must still be caught by _SECTION_NOISE before the
        lone-acronym rule fires.  Locks the ordering of checks."""
        text = 'ABSTRACT:\nSome thesis content about the study\n'
        title, _ = detect_title(text)
        assert title.upper() != 'ABSTRACT:'

    def test_keywords_colon_still_rejected(self):
        """Same ordering check for 'Keywords:'."""
        text = 'Keywords:\ndata mining, analytics, visualization\n'
        title, _ = detect_title(text)
        assert title.upper() != 'KEYWORDS:'


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
        assert "NOAH'S" in title or "Noah's" in title
        assert '\u2019' not in title

    def test_detect_title_folds_left_double_quote(self):
        text = 'UNIVERSITY\n\n\u201cSMART\u201d CAMPUS SYSTEM\n\nA Thesis\n'
        title, _ = detect_title(text)
        assert '\u201c' not in title
        assert '\u201d' not in title
