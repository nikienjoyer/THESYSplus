"""The shared topic-trend cache key must change whenever grouping input changes."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from theses.services.cached_topic_trends import _cache_key


def _row(**changes):
    base = dict(
        id='1', title='T', abstract='A', keywords=['k'], program='BSIT', year=2024,
        status='approved', embedding_generated_at=dt.datetime(2026, 9, 29, 12, 0),
        primary_subject_id=None, subject_reviewed_at=None, technology_tags=[],
    )
    base.update(changes)
    if base['primary_subject_id'] and 'primary_subject' not in base:
        base['primary_subject'] = SimpleNamespace(name='Education and Learning')
    return SimpleNamespace(**base)


def test_same_rows_same_key():
    assert _cache_key([_row()]) == _cache_key([_row()])


@pytest.mark.parametrize('field,value', [
    ('embedding_generated_at', dt.datetime(2026, 9, 30, 8, 0)),
    ('primary_subject_id', 'EDU'),
    ('subject_reviewed_at', dt.datetime(2026, 9, 30, 8, 0)),
    ('technology_tags', ['IoT']),
])
def test_key_changes_when_a_grouping_input_changes(field, value):
    assert _cache_key([_row(**{field: value})]) != _cache_key([_row()])


def test_key_changes_when_a_subject_is_renamed():
    # Group labels are built from subject names, so a rename must not serve
    # the old labels from cache.
    old = _row(primary_subject_id='EDU', primary_subject=SimpleNamespace(name='Education and learning'))
    new = _row(primary_subject_id='EDU', primary_subject=SimpleNamespace(name='Education and Learning'))
    assert _cache_key([old]) != _cache_key([new])
