"""Unit tests for the shared exact-title matcher (theses/services/title_match.py).

Pure string logic - no database and no SBERT model.
"""

from __future__ import annotations

import pytest

from theses.services.title_match import (
    TITLE_MATCH_MAX_TITLES,
    build_title_matcher,
    is_title_match,
    normalize_title,
    title_name_segment,
)

THESIX = 'Thesix: Centralized Web-Based Capstone And Thesis Repository'

# Enough unrelated titles that none of the words under test is rare.
FILLER = [
    'Hotel Booking System',
    'Library Inventory System',
    'Payroll System With Web Portal',
    'Student Web Portal',
    'Barangay Web Records',
]


class TestNormalize:
    def test_casefold_and_whitespace(self):
        assert normalize_title('  ThEsIx   Repo ') == 'thesix repo'

    def test_hyphens_and_dashes_are_spaces(self):
        assert normalize_title('Web-Based') == 'web based'
        assert normalize_title('Web–Based') == 'web based'
        assert normalize_title('Web—Based') == 'web based'

    def test_other_punctuation_is_kept(self):
        assert normalize_title('THESYS+') == 'thesys+'
        assert normalize_title('THESYS+') != normalize_title('THESYS')

    def test_nfkc(self):
        assert normalize_title('Ｔhesix') == 'thesix'  # fullwidth T

    def test_none_and_empty(self):
        assert normalize_title(None) == ''
        assert normalize_title('') == ''

    def test_name_segment(self):
        assert title_name_segment(THESIX) == 'Thesix'
        assert title_name_segment('Thesix - Centralized Repository') == 'Thesix'
        assert title_name_segment('Thesix – Centralized Repository') == 'Thesix'
        assert title_name_segment('Thesix—Centralized') == 'Thesix'
        # A plain hyphen inside a word is not a separator.
        assert title_name_segment('Web-Based Portal') == 'Web-Based Portal'


class TestWholeWordMatching:
    @pytest.mark.parametrize('query', ['thesix', 'THESIX', 'Thesix', 'tHeSiX'])
    def test_any_casing_matches(self, query):
        assert is_title_match(query, THESIX, [THESIX] + FILLER)

    def test_partial_word_does_not_match(self):
        corpus = ['Thesixty Days Of Learning']
        assert not is_title_match('thesix', 'Thesixty Days Of Learning', corpus)
        assert not is_title_match('thesix', 'Prethesix Study', ['Prethesix Study'])

    def test_hyphen_and_space_are_equivalent(self):
        title = 'Web-Based Attendance Portal'
        assert is_title_match('web based', title)
        assert is_title_match('Web-Based', title)
        assert is_title_match('web based attendance', 'Web Based Attendance Portal')

    def test_phrase_must_be_contiguous_words(self):
        assert not is_title_match('attendance web', 'Web-Based Attendance Portal')

    def test_empty_query_never_matches(self):
        assert not is_title_match('', THESIX, [THESIX])
        assert not is_title_match('   ', THESIX, [THESIX])
        assert not is_title_match('--', THESIX, [THESIX])


class TestQualification:
    def test_whole_title_equality_qualifies_even_when_common(self):
        # "system" is in 5 filler titles, but this thesis is literally named it.
        corpus = FILLER + ['System']
        assert is_title_match('system', 'System', corpus)
        assert is_title_match('SYSTEM', 'system', corpus)

    def test_name_segment_equality_qualifies_even_when_common(self):
        title = 'Web: A Study'
        corpus = FILLER + [title]
        assert is_title_match('web', title, corpus)
        # ...but the same word does not match a title that merely contains it.
        assert not is_title_match('web', 'Student Web Portal', corpus)

    def test_short_single_word_needs_equality(self):
        # "go" is not a glossary term, so the length rule still applies.
        assert not is_title_match('go', 'Go Attendance Tool', ['Go Attendance Tool'])
        assert is_title_match('go', 'Go', ['Go'])

    def test_short_glossary_acronym_matches_as_a_word(self):
        # "ai" is a glossary term (artificial intelligence), so it is
        # specific despite its length.
        assert is_title_match('ai', 'AI Attendance Tool', ['AI Attendance Tool'])

    def test_rarity_boundary_three_qualifies_four_does_not(self):
        assert TITLE_MATCH_MAX_TITLES == 3
        three = [f'Zeta Study {n}' for n in range(3)]
        four = [f'Zeta Study {n}' for n in range(4)]
        assert build_title_matcher('zeta', three).qualifies is True
        assert build_title_matcher('zeta', four).qualifies is False
        assert is_title_match('zeta', three[0], three)
        assert not is_title_match('zeta', four[0], four)

    @pytest.mark.parametrize('query', ['system', 'SYSTEM', 'System', 'sYsTeM'])
    def test_common_word_rejected_in_every_casing(self, query):
        corpus = [f'Alpha System {n}' for n in range(5)]
        matcher = build_title_matcher(query, corpus)
        assert matcher.qualifies is False
        assert not matcher.matches(corpus[0])

    def test_casing_does_not_change_rarity_outcome(self):
        corpus = ['RFID-Based Attendance', 'Hotel System']
        assert all(is_title_match(q, corpus[0], corpus) for q in ('rfid', 'Rfid', 'RFID'))

    def test_rarity_counts_whole_words_only(self):
        # Four titles contain "zetamax" as a substring of a longer word, which
        # must not make the rare word "zeta" look common.
        corpus = ['Zeta Portal'] + [f'Zetamax {n}' for n in range(5)]
        assert build_title_matcher('zeta', corpus).qualifies is True

    def test_punctuation_query_qualifies(self):
        title = 'THESYS+: A Semantic Thesis Retrieval System'
        corpus = [title] * 6  # would be "common" if rarity applied
        for query in ('THESYS+', 'thesys+', 'Thesys+'):
            assert is_title_match(query, title, corpus)

    def test_punctuation_query_is_distinct_from_plain_word(self):
        assert not is_title_match('thesys+', 'THESYS Portal', ['THESYS Portal'])

    def test_multi_word_query_qualifies(self):
        corpus = [f'Face Recognition Attendance {n}' for n in range(6)]
        assert is_title_match('face recognition', corpus[0], corpus)

    def test_corpus_is_not_read_for_non_single_word_queries(self):
        def boom():
            raise AssertionError('corpus should not be loaded')
        assert build_title_matcher('face recognition', boom).qualifies is True
        assert build_title_matcher('thesys+', boom).qualifies is True

    def test_corpus_callable_is_used_for_single_word(self):
        matcher = build_title_matcher('thesix', lambda: [THESIX])
        assert matcher.qualifies is True
        assert matcher.matches(THESIX)

    def test_no_corpus_means_single_word_does_not_qualify(self):
        assert build_title_matcher('thesix').qualifies is False


class TestGlossaryTerms:
    """Acronym and long form are one query (theses/services/acronyms.py)."""

    IOT_TITLES = [
        'ShopEase: An IoT-Based Shopping Cart',
        'Headlink: An Iot-Powered Head Pose Tracking System',
        'AnImo: Agricultural Platform With IoT Sensors',
        'AquaFlow: IoT Irrigation',
    ]

    def test_long_form_matches_title_that_uses_the_acronym(self):
        matcher = build_title_matcher('internet of things', FILLER + self.IOT_TITLES)
        assert matcher.matches('ShopEase: An IoT-Based Shopping Cart')

    def test_acronym_matches_title_that_uses_the_long_form(self):
        matcher = build_title_matcher('IoT', FILLER)
        assert matcher.matches('Smart Farm Using Internet of Things Sensors')

    def test_glossary_acronym_qualifies_even_when_common(self):
        # "iot" is in 4 titles, above TITLE_MATCH_MAX_TITLES, but it is a
        # known technical term, not a generic word like "system".
        assert len(self.IOT_TITLES) > TITLE_MATCH_MAX_TITLES
        matcher = build_title_matcher('iot', FILLER + self.IOT_TITLES)
        assert all(matcher.matches(t) for t in self.IOT_TITLES)

    def test_case_sensitive_acronym_ignores_the_ordinary_word(self):
        matcher = build_title_matcher('IT', FILLER)
        assert matcher.matches('IT Helpdesk Ticketing System')
        assert not matcher.matches('Make It Count: A Budget Tracker')

    def test_non_glossary_common_word_still_rejected(self):
        matcher = build_title_matcher('system', FILLER + self.IOT_TITLES)
        assert not matcher.matches('Hotel Booking System')
