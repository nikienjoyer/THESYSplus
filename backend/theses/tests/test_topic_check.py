"""Topic check — classify a proposed title as SATURATED / EMERGING / UNDEREXPLORED.

A title is labelled by how many approved theses are related to it (cosine
>= the 35% relevance floor), using the same size rule as the topic groups.
Scores are controlled: no model involved.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from theses.services.topic_analysis import check_title_topic

CANDIDATE = [1.0] + [0.0] * 383


def _thesis_at(score: float, n: int, title: str = ''):
    """A corpus row whose stored vector has cosine ``score`` with the candidate."""
    vector = [0.0] * 384
    vector[0] = score
    vector[1] = (1.0 - score * score) ** 0.5
    return SimpleNamespace(
        id=f'id-{n}', title=title or f'Thesis {n}', year=2024, program='BSIT',
        embedding_vector=vector,
    )


def _corpus(related: int, total: int):
    return ([_thesis_at(0.60, i) for i in range(related)]
            + [_thesis_at(0.10, i) for i in range(related, total)])


def _check(corpus, *, average_size=6.5, grouped_total=None, title='Proposed Thesis Title'):
    with patch('theses.services.semantic_search.embed_text', return_value=CANDIDATE):
        return check_title_topic(
            title, corpus,
            average_size=average_size,
            grouped_total=len(corpus) if grouped_total is None else grouped_total,
        )


@pytest.mark.parametrize('related, trend', [
    (10, 'SATURATED'),    # >= 6.5 * 1.5 = 9.75
    (9, 'EMERGING'),
    (4, 'EMERGING'),
    (3, 'UNDEREXPLORED'),  # <= 6.5 * 0.5 = 3.25
    (0, 'UNDEREXPLORED'),
])
def test_label_follows_group_size_rule(related, trend):
    result = _check(_corpus(related, 52))
    assert result['trend'] == trend
    assert result['related_count'] == related
    assert result['total'] == 52


def test_cutoffs_and_explanation():
    result = _check(_corpus(5, 52))
    assert (result['saturated_at'], result['underexplored_at']) == (10, 3)
    assert result['explanation'].startswith('5 out of 52 uploaded theses are related to this title')
    assert 'at least 35% similar' in result['explanation']
    assert '10 or more' in result['explanation']
    assert '3 or fewer' in result['explanation']


def test_singular_wording():
    assert _check(_corpus(1, 52))['explanation'].startswith(
        '1 out of 52 uploaded theses is related to this title')


def test_floor_is_inclusive():
    corpus = [_thesis_at(0.35, 0), _thesis_at(0.3499, 1)] + _corpus(0, 20)
    assert _check(corpus)['related_count'] == 1


def test_small_corpus_uses_fixed_rule():
    result = _check(_corpus(2, 10), average_size=2.0)
    assert result['trend'] == 'EMERGING'  # fixed rule: >= 2 emerging, >= 5 saturated
    assert (result['saturated_at'], result['underexplored_at']) == (5, 1)
    assert _check(_corpus(5, 10), average_size=2.0)['trend'] == 'SATURATED'


def test_related_list_is_top_five_by_score():
    corpus = [_thesis_at(0.40 + i * 0.05, i) for i in range(8)]
    related = _check(corpus)['related']
    assert [r['title'] for r in related] == ['Thesis 7', 'Thesis 6', 'Thesis 5', 'Thesis 4', 'Thesis 3']
    assert set(related[0]) == {'id', 'title', 'year', 'program', 'similarity', 'title_match'}


def test_closest_theses_shown_below_the_cutoff_but_not_counted():
    result = _check([_thesis_at(0.20, 0), _thesis_at(0.08, 1)] + [_thesis_at(0.02, i) for i in range(2, 20)])
    assert result['related_count'] == 0
    assert [r['title'] for r in result['related'][:2]] == ['Thesis 0', 'Thesis 1']
    assert result['related'][0]['similarity'] == pytest.approx(0.20, abs=1e-4)


def test_exact_name_counts_and_comes_first_even_below_cutoff():
    corpus = [
        _thesis_at(0.60, 0),
        _thesis_at(0.08, 1, 'Thesix: Centralized Web-Based Capstone Repository'),
    ] + _corpus(0, 20)[2:]
    result = _check(corpus, title='THESIX')
    assert result['related_count'] == 2
    assert result['related'][0]['title'].startswith('Thesix')
    assert result['related'][0]['title_match'] is True
    assert result['related'][1]['title_match'] is False


def test_name_match_that_is_also_similar_is_listed_once():
    corpus = [_thesis_at(0.70, 0, 'Thesix: Centralized Web-Based Capstone Repository')] + _corpus(0, 20)[1:]
    result = _check(corpus, title='THESIX')
    assert result['related_count'] == 1
    assert [r['title'] for r in result['related']].count(
        'Thesix: Centralized Web-Based Capstone Repository') == 1


def test_exact_name_hides_below_cutoff_filler():
    corpus = [
        _thesis_at(0.08, 0, 'Thesix: Centralized Web-Based Capstone Repository'),
        _thesis_at(0.17, 1), _thesis_at(0.15, 2),
    ] + [_thesis_at(0.02, i) for i in range(3, 20)]
    related = _check(corpus, title='THESIX')['related']
    assert [r['title'] for r in related] == ['Thesix: Centralized Web-Based Capstone Repository']


def test_exact_name_keeps_theses_that_count_as_related():
    corpus = [
        _thesis_at(0.08, 0, 'Thesix: Centralized Web-Based Capstone Repository'),
        _thesis_at(0.50, 1), _thesis_at(0.17, 2),
    ] + [_thesis_at(0.02, i) for i in range(3, 20)]
    related = _check(corpus, title='THESIX')['related']
    assert [r['title'] for r in related] == [
        'Thesix: Centralized Web-Based Capstone Repository', 'Thesis 1']


# ---------------------------------------------------------------------------
# POST /api/v1/theses/topic-trends/check-title/
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    from accounts.models import Role, User
    return User.objects.create_user(
        email='topiccheck@pampangastateu.edu.ph', first_name='T', last_name='C',
        role=Role.STUDENT, password='Test12345!Test',
    )


def _post(client, title, user=None):
    headers = {}
    if user:
        from auth_service.services import issue_token_pair
        token = issue_token_pair(user, request=None, remember_me=False).access_token
        headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    return client.post(reverse('thesis-topic-check'), data={'title': title},
                       content_type='application/json', **headers)


@pytest.mark.django_db
def test_endpoint_requires_authentication(client):
    assert _post(client, 'A proposed thesis title').status_code == 401


@pytest.mark.django_db
def test_endpoint_rejects_short_title(client, user):
    response = _post(client, 'IoT', user)
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'TITLE_TOO_SHORT'


@pytest.mark.django_db
def test_endpoint_returns_classification(client, user):
    groups = {'clusters': [{'thesis_count': 4}, {'thesis_count': 2}]}
    with patch('theses.services.cached_topic_trends.get_topic_trends_data', return_value=groups):
        response = _post(client, 'A proposed thesis title', user)
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 0
    assert body['trend'] == 'UNDEREXPLORED'
    assert body['average_group_size'] == 3.0
