"""Unit tests for the acronym glossary (theses/services/acronyms.py).

Pure string logic - no database and no SBERT model.
"""

from __future__ import annotations

import pytest

from theses.services.acronyms import (
    count_mentions,
    expand_query,
    glossary_term_variants,
    is_about_term,
)


class TestExpandQuery:
    def test_acronym_expands_to_long_form(self):
        assert expand_query('iot') == ['iot', 'internet of things']

    def test_long_form_contracts_to_acronym(self):
        assert expand_query('internet of things') == ['internet of things', 'iot']

    @pytest.mark.parametrize('query', ['IoT', 'IOT', 'iOt'])
    def test_any_casing_of_a_plain_acronym_expands(self, query):
        assert 'internet of things' in expand_query(query)

    def test_acronym_inside_a_longer_query_is_replaced_in_place(self):
        assert 'internet of things based shopping cart' in expand_query('IoT-based shopping cart')

    def test_original_query_is_always_first(self):
        assert expand_query('RFID attendance')[0] == 'RFID attendance'

    def test_query_without_glossary_terms_is_unchanged(self):
        assert expand_query('hotel booking system') == ['hotel booking system']

    def test_ambiguous_acronym_needs_capitals(self):
        # "it" is a pronoun; only "IT" means information technology.
        assert expand_query('is it working') == ['is it working']
        assert 'information technology helpdesk' in expand_query('IT helpdesk')

    def test_partial_words_are_not_expanded(self):
        assert expand_query('patriot') == ['patriot']

    def test_plural_acronym_expands_to_plural_long_form(self):
        assert 'barangay health workers' in expand_query('BHWs')

    def test_empty_query(self):
        assert expand_query('') == []
        assert expand_query('   ') == []


class TestGlossaryTermVariants:
    def test_known_acronym_returns_both_forms(self):
        assert set(glossary_term_variants('IoT')) == {'iot', 'internet of things'}

    def test_known_long_form_returns_both_forms(self):
        assert set(glossary_term_variants('Optical Character Recognition')) == {
            'ocr', 'optical character recognition',
        }

    def test_query_that_is_not_exactly_a_term_returns_nothing(self):
        # A term inside a longer query is not a "term search" - the rescue
        # for longer phrases stays with the title matcher.
        assert glossary_term_variants('iot shopping cart') == []
        assert glossary_term_variants('system') == []

    def test_ambiguous_acronym_in_lowercase_is_not_a_term(self):
        assert glossary_term_variants('it') == []
        assert 'information technology' in glossary_term_variants('IT')


class TestCountMentions:
    def test_counts_acronym_and_long_form_together(self):
        text = 'An IoT device. The Internet of Things (IoT) grows. internet-of-things'
        assert count_mentions(text, 'iot') == 4

    def test_whole_words_only(self):
        assert count_mentions('patriot riot idiot', 'iot') == 0

    def test_hyphenated_compound_counts(self):
        assert count_mentions('an IoT-based cart', 'iot') == 1

    def test_ambiguous_acronym_counts_capitals_only(self):
        assert count_mentions('it is IT and it', 'IT') == 1

    def test_non_term_counts_zero(self):
        assert count_mentions('system system', 'system') == 0

    def test_empty_text(self):
        assert count_mentions('', 'iot') == 0
        assert count_mentions(None, 'iot') == 0


class TestIsAboutTerm:
    FILLER = 'Lorem ipsum dolor sit amet. '   # 28 characters

    def test_one_mention_in_keywords_or_abstract_is_enough(self):
        assert is_about_term('iot', head='IoT sensors', full_text='')

    def test_three_mentions_in_a_short_document(self):
        text = 'IoT device. IoT sensor. Internet of Things. ' + self.FILLER * 300   # ~8.5k chars
        assert is_about_term('iot', head='', full_text=text)

    def test_two_mentions_are_never_enough(self):
        assert not is_about_term('iot', head='', full_text='IoT. IoT.')

    def test_thin_mentions_across_a_long_document_are_passing_mentions(self):
        # Literature reviews cite a term a few times across 200k characters;
        # a thesis that uses the technology mentions it far more densely.
        text = 'IoT. ' + self.FILLER * 3000 + ' IoT. ' + self.FILLER * 3000 + ' IoT, IoT.'
        assert not is_about_term('iot', head='', full_text=text)
