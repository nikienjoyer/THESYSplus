"""Technology tags (theses/services/technology_tags.py)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus
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



@pytest.fixture
def irrigation_thesis(db):
    user = User.objects.create_user(
        email='tags@pampangastateu.edu.ph', first_name='T', last_name='G',
        role=Role.FACULTY, password='Test12345!Test',
    )
    thesis = Thesis(
        title='AquaFlow: Smart Irrigation', abstract='Arduino IoT sensors water the farm.',
        authors=['T, T.'], keywords=['irrigation'], program=Program.BSIT.value, year=2024,
        adviser='', file_type=FileType.PDF, sha256='c' * 64, extracted_text='',
        status=ThesisStatus.APPROVED, uploaded_by=user,
    )
    thesis.uploaded_file.save('tags.pdf', ContentFile(b'%PDF-1.4'), save=False)
    thesis.save()
    return thesis


def test_generating_the_search_vector_stores_technology_tags(irrigation_thesis):
    from theses.services.semantic_search import generate_thesis_embedding

    with patch('theses.services.semantic_search.embed_text', return_value=[1.0] + [0.0] * 383):
        generate_thesis_embedding(irrigation_thesis)

    irrigation_thesis.refresh_from_db()
    assert irrigation_thesis.technology_tags == ['IoT']
