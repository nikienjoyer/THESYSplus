"""Technology tags (theses/services/technology_tags.py)."""

from __future__ import annotations

from theses.services.technology_tags import TECHNOLOGY_TAGS, detect_technology_tags


class TestDetectTechnologyTags:
    def test_keyword_mention_is_enough(self):
        assert detect_technology_tags(title='Smart Farm Monitor', keywords=['Internet of Things']) == ['IoT']

    def test_dense_full_text_mentions_tag_a_thesis(self):
        body = 'The IoT tower reports readings. IoT sensors log humidity. Internet of Things design. ' * 2
        assert detect_technology_tags(title='Fuzzy Logic Indoor Farming', full_text=body) == ['IoT']

    def test_repository_thesis_about_analysis_is_not_iot(self):
        # THESYS+ repeats "analysis" and "similarity"; none of that is IoT.
        tags = detect_technology_tags(
            title='THESYS+: A Semantic-Based Thesis Retrieval and Topic Trend Analysis System',
            abstract=('Topic trend analysis with semantic similarity search. '
                      'Natural language processing ranks theses; analysis of trends '
                      'supports research planning.'),
        )
        assert 'IoT' not in tags
        assert 'NLP' in tags

    def test_several_tags_follow_the_declared_order(self):
        tags = detect_technology_tags(
            title='AnImo: An AI-Driven Agricultural Platform',
            abstract='Artificial intelligence advice from IoT soil sensors.',
        )
        assert tags == ['IoT', 'AI']
        assert TECHNOLOGY_TAGS.index('IoT') < TECHNOLOGY_TAGS.index('AI')

    def test_ambiguous_acronym_counts_only_in_capitals(self):
        assert 'AR' not in detect_technology_tags(abstract='Filters ar applied to photos.')
        assert 'AR' in detect_technology_tags(abstract='An AR chemistry laboratory.')

    def test_no_text_means_no_tags(self):
        assert detect_technology_tags() == []
