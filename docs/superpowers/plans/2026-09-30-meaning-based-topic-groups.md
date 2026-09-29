# Meaning-Based Topic Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "Explore text clusters" group theses by meaning, name each group after its members' reviewed subjects, show evidence-based technology tags (IoT, AI, NLP…), and suggest the two most likely subjects for theses awaiting review.

**Architecture:** Grouping moves from TF-IDF + K-Means to agglomerative clustering (cosine, average linkage) over the SBERT document vectors already stored on each thesis; TF-IDF keeps supplying each group's keywords. Technology tags reuse the acronym evidence rule (`services/acronyms.py`) and are stored on the thesis when its vector is generated, so the analysis never loads full texts. Subject suggestions use the nearest reviewed-subject centroid over the same vectors.

**Tech Stack:** Django 5 + DRF, scikit-learn 1.9, NumPy, sentence-transformers (all-MiniLM-L6-v2), pytest-django; React 19 + Vite + Tailwind.

**Spec:** `docs/superpowers/specs/2026-09-30-meaning-based-topic-groups-design.md`

## Global Constraints

- Work in `C:\Users\Desktop\Downloads\THESYSplus-main`. Backend commands run from `backend/`; frontend commands from `frontend/`.
- Backend tests: `python -m pytest -q -p no:cacheprovider <path>`. The SBERT model loads on first use (about 10 s).
- Frontend has no test runner: verify with `npx eslint <files>` (no new problems in touched files) and `npm run build`.
- Do not stage `.claude/settings.local.json`, `outputs/`, `docs/topic-trend-audit/` or `frontend/src/pages/LandingPage.jsx`.
- Commit locally at the end of each task. **Never push, migrate the live database, regenerate live vectors or restart the demo backend without the owner's explicit approval** (Task 9 lists these).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No new dependencies.
- Technology tags, exactly and in this order: `IoT, AI, ML, DL, NLP, OCR, CNN, LLM, AR, VR, GPS, GIS, RFID, QR, SMS`.
- Group name rule: most common reviewed subject if it covers at least half of the reviewed members and is not tied; otherwise the two most common subjects (count descending, then name) joined with `' · '`; no reviewed member → existing `_label_cluster`.
- `GET /api/v1/theses/topic-trends/` keeps every existing field; clusters gain `technology_tags` (`[{'tag', 'count'}]`) and `member_tags` (`{thesis_id: [tags]}`).
- `analyze_topics` must still read the corpus in one query and never load `extracted_text` (guarded by `test_extracted_text_is_deferred_and_never_fetched`).

## Review Focus

1. `?k=` larger than the corpus (or `k=1`): must clamp, not crash. → Task 5 `test_k_larger_than_the_corpus_is_clamped`.
2. Two groups whose subject names are identical: both must get the "(Cluster N)" qualifier, never two identical cards. → Task 5 `test_two_groups_with_the_same_subject_name_get_qualifiers`.
3. Rows saved before the tag backfill (`technology_tags` empty, or `None` on in-memory objects): no tags, no crash. → Task 5 `test_technology_tags_are_counted_per_group_and_listed_per_member`.
4. Suggestions when only one subject has reviewed theses, or the thesis is the only member of its subject: return fewer than two, never self-support. → Task 6 tests.
5. The "Reviewed subjects" view reuses the same card component without technology fields: it must render unchanged. → Task 7 Step 6 manual check.

---

### Task 1: Technology tag detection

**Files:**
- Create: `backend/theses/services/technology_tags.py`
- Test: `backend/theses/tests/test_technology_tags.py`

**Interfaces:**
- Consumes: `theses.services.acronyms.is_about_term(query: str, *, head: str, full_text: Optional[str]) -> bool`.
- Produces: `TECHNOLOGY_TAGS: tuple[str, ...]`; `detect_technology_tags(*, title: str = '', abstract: str = '', keywords=None, full_text: str = '') -> list[str]` (tags in `TECHNOLOGY_TAGS` order).

- [ ] **Step 1: Write the failing tests**

Create `backend/theses/tests/test_technology_tags.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_technology_tags.py`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'theses.services.technology_tags'`.

- [ ] **Step 3: Implement**

Create `backend/theses/services/technology_tags.py`:

```python
"""Technology tags: which technologies a thesis is actually about.

A thesis can be about several technologies at once (the fuzzy-logic farming
app is an IoT project that also uses fuzzy logic), and a technology is not a
research subject (the IoT theses are about agriculture, accessibility,
commerce and security). So tags are a list per thesis, never a group.

Evidence uses the Repository term-rescue rule (services/acronyms.py
``is_about_term``): one mention in the title, keywords or abstract, or at
least three full-text mentions at a density of one per 10,000 characters.
Tags are computed when the search vector is generated and stored on
``Thesis.technology_tags``, so reading them never loads the full text.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .acronyms import is_about_term

TECHNOLOGY_TAGS = (
    'IoT', 'AI', 'ML', 'DL', 'NLP', 'OCR', 'CNN', 'LLM',
    'AR', 'VR', 'GPS', 'GIS', 'RFID', 'QR', 'SMS',
)


def detect_technology_tags(
    *,
    title: str = '',
    abstract: str = '',
    keywords: Optional[Iterable] = None,
    full_text: Optional[str] = '',
) -> List[str]:
    """The technologies this thesis is about, in ``TECHNOLOGY_TAGS`` order."""
    keyword_text = ' ; '.join(str(k) for k in (keywords or []) if isinstance(k, str))
    head = '\n'.join([title or '', keyword_text, abstract or ''])
    return [
        tag for tag in TECHNOLOGY_TAGS
        if is_about_term(tag, head=head, full_text=full_text or '')
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_technology_tags.py`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/theses/services/technology_tags.py backend/theses/tests/test_technology_tags.py
git commit -m "Detect technology tags from acronym evidence" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Store technology tags when the search vector is generated

**Files:**
- Modify: `backend/theses/models.py` (after `embedding_generated_at`, line ~104)
- Create: `backend/theses/migrations/0007_thesis_technology_tags.py` (via `makemigrations`)
- Modify: `backend/theses/services/semantic_search.py` (`generate_thesis_embedding`)
- Test: `backend/theses/tests/test_technology_tags.py` (append)

**Interfaces:**
- Consumes: `detect_technology_tags` (Task 1).
- Produces: `Thesis.technology_tags` (JSON list of str, default `[]`), written by `generate_thesis_embedding` in the same save as the vector.

- [ ] **Step 1: Write the failing test** (append to `backend/theses/tests/test_technology_tags.py`)

```python
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_technology_tags.py -k stores`
Expected: FAIL. `AttributeError: 'Thesis' object has no attribute 'technology_tags'`, or `FieldDoesNotExist`.

- [ ] **Step 3: Add the field and generate the migration**

In `backend/theses/models.py`, directly after `embedding_generated_at = models.DateTimeField(null=True, blank=True)`:

```python
    # Technologies the thesis is about (services/technology_tags.py). Stored
    # with the search vector so the topic analysis never loads the full text.
    technology_tags = models.JSONField(default=list, blank=True)
```

Run: `python manage.py makemigrations theses --name thesis_technology_tags`
Expected: `theses\migrations\0007_thesis_technology_tags.py` containing `migrations.AddField(model_name='thesis', name='technology_tags', field=models.JSONField(blank=True, default=list))` with dependency `('theses', '0006_thesis_processing_job_id')`.

- [ ] **Step 4: Compute tags in `generate_thesis_embedding`**

In `backend/theses/services/semantic_search.py`, add near the other imports:

```python
from .technology_tags import detect_technology_tags
```

In `generate_thesis_embedding`, replace:

```python
        thesis.embedding_generated_at = timezone.now()
        if save:
            thesis.save(update_fields=[
                'embedding_vector',
                'embedding_status',
                'embedding_model',
                'embedding_generated_at',
                'updated_at',
            ])
```

with:

```python
        thesis.embedding_generated_at = timezone.now()
        thesis.technology_tags = detect_technology_tags(
            title=thesis.title, abstract=thesis.abstract,
            keywords=thesis.keywords, full_text=thesis.extracted_text,
        )
        if save:
            thesis.save(update_fields=[
                'embedding_vector',
                'embedding_status',
                'embedding_model',
                'embedding_generated_at',
                'technology_tags',
                'updated_at',
            ])
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_technology_tags.py theses/tests/test_semantic_search.py theses/tests/test_title_embedding.py`
Expected: all pass (`7 passed` in the tags file, the other two unchanged).

- [ ] **Step 6: Commit**

```bash
git add backend/theses/models.py backend/theses/migrations/0007_thesis_technology_tags.py backend/theses/services/semantic_search.py backend/theses/tests/test_technology_tags.py
git commit -m "Store technology tags with the thesis search vector" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Name groups after their members' reviewed subjects

**Files:**
- Modify: `backend/theses/services/topic_analysis.py` (add `_subject_label` after `_label_cluster`)
- Test: `backend/theses/tests/test_topic_analysis.py` (append class)

**Interfaces:**
- Produces: `_subject_label(member_subjects: Sequence[str | None]) -> str | None`.

- [ ] **Step 1: Write the failing tests** (append to `backend/theses/tests/test_topic_analysis.py`)

```python
class TestSubjectLabel:
    ACA = 'Academic services and research'
    AGR = 'Agriculture and growing systems'
    COM = 'Commerce and marketplaces'
    EDU = 'Education and learning'
    HEA = 'Health and medicine'
    PUB = 'Public and community services'

    def test_clear_majority_names_the_group(self):
        from theses.services.topic_analysis import _subject_label
        assert _subject_label([self.EDU] * 8 + [self.HEA] * 2) == self.EDU

    def test_exactly_half_with_a_smaller_runner_up_still_names_it(self):
        from theses.services.topic_analysis import _subject_label
        assert _subject_label([self.EDU, self.EDU, self.HEA, self.PUB]) == self.EDU

    def test_tie_names_both_subjects_alphabetically(self):
        from theses.services.topic_analysis import _subject_label
        assert _subject_label([self.COM] * 3 + [self.AGR] * 3) == f'{self.AGR} · {self.COM}'

    def test_no_majority_names_the_two_most_common(self):
        from theses.services.topic_analysis import _subject_label
        members = [self.ACA] * 5 + [self.PUB] * 3 + [self.EDU] * 2 + [self.HEA] * 2 + [self.AGR, self.COM]
        assert _subject_label(members) == f'{self.ACA} · {self.PUB}'

    def test_members_awaiting_review_are_ignored(self):
        from theses.services.topic_analysis import _subject_label
        assert _subject_label([None, None, self.AGR]) == self.AGR

    def test_no_reviewed_member_returns_none(self):
        from theses.services.topic_analysis import _subject_label
        assert _subject_label([None, None]) is None
        assert _subject_label([]) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_topic_analysis.py -k SubjectLabel`
Expected: 6 failed, `ImportError: cannot import name '_subject_label'`.

- [ ] **Step 3: Implement** (in `topic_analysis.py`, directly after `_label_cluster`)

```python
def _subject_label(member_subjects: Sequence[str | None]) -> str | None:
    """Name a group after its members' confirmed primary subjects.

    Reviewed subjects are the group's own verdict on what each thesis is
    about, so they beat any keyword rule. Members awaiting review (``None``)
    do not vote.

    * The most common subject names the group when it covers at least half
      of the reviewed members and is not tied.
    * Otherwise the two most common subjects are joined with " · ", ordered
      by count and then name so the label is stable across runs.
    * ``None`` when no member is reviewed; the caller falls back to
      ``_label_cluster``.
    """
    reviewed = [subject for subject in member_subjects if subject]
    if not reviewed:
        return None
    ranked = sorted(Counter(reviewed).items(), key=lambda item: (-item[1], item[0]))
    top_name, top_count = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if top_count * 2 >= len(reviewed) and top_count > runner_up:
        return top_name
    return f'{ranked[0][0]} · {ranked[1][0]}'
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_topic_analysis.py -k SubjectLabel`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/theses/services/topic_analysis.py backend/theses/tests/test_topic_analysis.py
git commit -m "Name topic groups after members' reviewed subjects" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Load grouping fields in one query and key the cache on them

**Files:**
- Modify: `backend/theses/services/topic_analysis.py` (`get_topic_trends_queryset`)
- Modify: `backend/theses/services/cached_topic_trends.py` (`_CACHE_SCHEMA_VERSION`, `_cache_key`)
- Test: `backend/theses/tests/test_topic_analysis.py` (add to `TestGetTopicTrendsQueryset`)
- Test: `backend/theses/tests/test_cached_topic_trends.py` (create)

**Interfaces:**
- Consumes: `Thesis.technology_tags`, `embedding_vector`, `embedding_generated_at`, `primary_subject`, `subject_reviewed_at`.
- Produces: queryset rows carrying those fields with `primary_subject` joined; `_cache_key(rows)` that changes when any grouping input changes.

- [ ] **Step 1: Write the failing tests**

Add to class `TestGetTopicTrendsQueryset` in `test_topic_analysis.py`:

```python
    def test_grouping_fields_load_in_the_corpus_query(self, make_thesis, django_assert_num_queries):
        from django.utils import timezone
        from theses.models import ResearchSubject

        thesis = make_thesis('Reviewed Thesis On Farming')
        thesis.primary_subject = ResearchSubject.objects.get(pk='AGR')
        thesis.subject_reviewed_at = timezone.now()
        thesis.technology_tags = ['IoT']
        thesis.embedding_vector = [0.1] * 384
        thesis.save()

        with django_assert_num_queries(1):
            row = get_topic_trends_queryset().get(pk=thesis.pk)
            assert row.primary_subject.name == 'Agriculture and growing systems'
            assert row.subject_reviewed_at is not None
            assert row.technology_tags == ['IoT']
            assert len(row.embedding_vector) == 384
```

Create `backend/theses/tests/test_cached_topic_trends.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_cached_topic_trends.py theses/tests/test_topic_analysis.py -k "cache or grouping_fields"`
Expected:
- the 4 parametrized key tests fail (the key ignores those fields);
- `test_grouping_fields_load_in_the_corpus_query` fails with more than one query (deferred fields reload).

- [ ] **Step 3: Implement**

In `get_topic_trends_queryset`, replace the `.only(...)` call and add `select_related` before it:

```python
        .select_related('primary_subject')
        .only(
            'id', 'title', 'abstract',
            'keywords', 'program', 'year', 'status',
            # Grouping inputs: the stored SBERT vector, the confirmed subject
            # that names each group, and the stored technology tags.
            'embedding_vector', 'embedding_generated_at', 'technology_tags',
            'subject_reviewed_at', 'primary_subject', 'primary_subject__name',
        )
```

In `cached_topic_trends.py`, set `_CACHE_SCHEMA_VERSION = '2'`, and in `_cache_key` replace the `row = (...)` tuple with:

```python
        row = (
            str(thesis.id), thesis.title, thesis.abstract, thesis.keywords,
            thesis.program, thesis.year, thesis.status,
            # Grouping inputs: vectors (regenerated vectors get a new
            # timestamp), reviewed subjects (group names), technology tags.
            thesis.embedding_generated_at, thesis.primary_subject_id,
            thesis.subject_reviewed_at, thesis.technology_tags,
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_cached_topic_trends.py theses/tests/test_topic_analysis.py`
Expected: all pass, including `test_extracted_text_is_deferred_and_never_fetched` (still exactly one query).

- [ ] **Step 5: Commit**

```bash
git add backend/theses/services/topic_analysis.py backend/theses/services/cached_topic_trends.py backend/theses/tests/test_topic_analysis.py backend/theses/tests/test_cached_topic_trends.py
git commit -m "Load grouping fields in one query and key the trend cache on them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Group by meaning and report technology tags

**Files:**
- Modify: `backend/theses/services/topic_analysis.py` (module docstring, `_DocMeta`, `TopicCluster`, new helpers, `analyze_topics`)
- Test: `backend/theses/tests/test_topic_analysis.py` (append class)

**Interfaces:**
- Consumes: `_subject_label` (Task 3); `Thesis.technology_tags` (Task 2; read with `getattr(..., None) or []`); the corpus query from Task 4 (already loads `technology_tags`, `subject_reviewed_at`, `primary_subject__name` and the vector, so reading them adds no queries); `semantic_search.EMBEDDING_DIM`, `semantic_search.embed_text`.
- Produces: `TopicCluster.technology_tags: list[dict]` (`{'tag': str, 'count': int}`, count desc then tag) and `TopicCluster.member_tags: dict[str, list[str]]`; helpers `_reviewed_subject_name(thesis)`, `_document_vector(thesis, text)`, `_group_by_meaning(vectors, k)`, `_tag_summary(member_tag_lists)`. `analyze_topics` keeps its signature; `random_state` is accepted and ignored.

- [ ] **Step 1: Write the failing tests** (append to `backend/theses/tests/test_topic_analysis.py`)

```python
import uuid as _uuid
from datetime import datetime as _datetime
from datetime import timezone as _tz
from types import SimpleNamespace


def _unit(*values):
    vector = [0.0] * 384
    for index, value in enumerate(values):
        vector[index] = value
    return vector


def _doc(title, vector, *, subject=None, tags=None, abstract=None, keywords=None):
    """An in-memory thesis row with a controlled SBERT vector."""
    return SimpleNamespace(
        id=_uuid.uuid4(), title=title,
        abstract=abstract if abstract is not None else f'{title} study abstract.',
        keywords=keywords or [], embedding_vector=vector,
        primary_subject=SimpleNamespace(name=subject) if subject else None,
        subject_reviewed_at=_datetime(2026, 9, 30, tzinfo=_tz.utc) if subject else None,
        technology_tags=tags,
    )


def _group_of(result):
    return {thesis_id: c.cluster_id for c in result.clusters for thesis_id in c.thesis_ids}


class TestMeaningBasedGrouping:
    SHARED = 'Topic trend analysis and data analysis with analysis dashboards and trend charts.'

    def test_groups_follow_meaning_not_shared_words(self):
        # repo_a and iot_a share an identical abstract (TF-IDF would pair them)
        # but their vectors say they are about different things.
        repo_a = _doc('Thesis Repository Portal', _unit(1.0), abstract=self.SHARED)
        repo_b = _doc('Capstone Archive Search', _unit(0.9, 0.1))
        iot_a = _doc('Irrigation Sensor Network', _unit(0.0, 1.0), abstract=self.SHARED)
        iot_b = _doc('Greenhouse Moisture Gateway', _unit(0.1, 0.9))
        group_of = _group_of(analyze_topics([repo_a, iot_a, repo_b, iot_b], k=2))
        assert group_of[str(repo_a.id)] == group_of[str(repo_b.id)]
        assert group_of[str(iot_a.id)] == group_of[str(iot_b.id)]
        assert group_of[str(repo_a.id)] != group_of[str(iot_a.id)]

    def test_group_is_named_after_its_members_reviewed_subject(self):
        docs = [
            _doc('Repository Portal', _unit(1.0), subject='Academic services and research'),
            _doc('Archive Search', _unit(0.95, 0.05), subject='Academic services and research'),
            _doc('Farm Sensor Grid', _unit(0.0, 1.0), subject='Agriculture and growing systems',
                 keywords=['IoT', 'sensors']),
            _doc('Soil Moisture Probe', _unit(0.05, 0.95), subject='Agriculture and growing systems',
                 keywords=['IoT', 'sensors']),
        ]
        topics = {c.topic for c in analyze_topics(docs, k=2).clusters}
        assert topics == {'Academic services and research', 'Agriculture and growing systems'}

    def test_repository_thesis_is_not_labelled_iot(self):
        # The reported bug: THESYS+ (a thesis repository that repeats
        # "analysis") was shown under "Internet of Things".
        thesys = _doc('THESYS+ Semantic Thesis Retrieval', _unit(1.0), abstract=self.SHARED,
                      subject='Academic services and research', tags=['AI', 'NLP'])
        thesix = _doc('Thesix Capstone Repository', _unit(0.95, 0.05),
                      subject='Academic services and research')
        farms = [
            _doc(f'Smart Irrigation Unit {n}', _unit(0.05 * n, 1.0), abstract=self.SHARED,
                 subject='Agriculture and growing systems', tags=['IoT'], keywords=['IoT', 'sensors'])
            for n in range(3)
        ]
        result = analyze_topics([thesys, thesix, *farms], k=2)
        group = next(c for c in result.clusters if str(thesys.id) in c.thesis_ids)
        assert 'Internet of Things' not in group.topic
        assert {t['tag'] for t in group.technology_tags} == {'AI', 'NLP'}

    def test_unreviewed_group_falls_back_to_the_keyword_label(self):
        # Characterization: passes before and after - pins the fallback.
        docs = [
            _doc('Greenhouse Sensor Network', _unit(1.0), keywords=['IoT', 'sensors', 'esp32']),
            _doc('Soil Sensor Network', _unit(0.9, 0.1), keywords=['IoT', 'sensors', 'esp32']),
        ]
        assert analyze_topics(docs, k=1).clusters[0].topic == 'Internet of Things'

    def test_technology_tags_are_counted_per_group_and_listed_per_member(self):
        a = _doc('Farm Sensor Grid', _unit(1.0), tags=['IoT', 'AI'])
        b = _doc('Soil Moisture Probe', _unit(0.9, 0.1), tags=['IoT'])
        c = _doc('Thesis Repository Portal', _unit(0.0, 1.0), tags=None)  # saved before the backfill
        result = analyze_topics([a, b, c], k=2)
        farm = next(cl for cl in result.clusters if str(a.id) in cl.thesis_ids)
        assert farm.technology_tags == [{'tag': 'IoT', 'count': 2}, {'tag': 'AI', 'count': 1}]
        assert farm.member_tags == {str(a.id): ['IoT', 'AI'], str(b.id): ['IoT']}
        repo = next(cl for cl in result.clusters if str(c.id) in cl.thesis_ids)
        assert repo.technology_tags == []
        assert repo.member_tags == {str(c.id): []}

    def test_same_groups_when_rows_are_reordered(self):
        topics = ['Irrigation sensors', 'Repository search', 'Tutoring games']
        docs = []
        for axis, words in enumerate(topics):
            for jitter, variant in ((0.0, 'alpha'), (0.1, 'omega')):
                values = [0.0, 0.0, 0.0]
                values[axis] = 1.0
                values[(axis + 1) % 3] = jitter
                docs.append(_doc(f'{words} {variant}', _unit(*values)))

        def partition(rows):
            return sorted(sorted(c.thesis_ids) for c in analyze_topics(rows, k=3).clusters)

        assert partition(docs) == partition(list(reversed(docs)))

    def test_missing_vector_is_embedded_from_the_topic_text(self):
        from unittest.mock import patch
        stored = _doc('Irrigation Sensor Network', _unit(1.0))
        missing = _doc('Irrigation Sensor Gateway', None)
        other = _doc('Thesis Repository Search', _unit(0.0, 1.0))
        with patch('theses.services.semantic_search.embed_text', return_value=_unit(0.95, 0.05)) as embed:
            result = analyze_topics([stored, missing, other], k=2)
        embed.assert_called_once()
        assert 'Irrigation Sensor Gateway' in embed.call_args.args[0]
        group_of = _group_of(result)
        assert group_of[str(missing.id)] == group_of[str(stored.id)]

    def test_k_larger_than_the_corpus_is_clamped(self):
        docs = [_doc('Irrigation Sensors', _unit(1.0)), _doc('Thesis Repository', _unit(0.0, 1.0))]
        assert analyze_topics(docs, k=10).total_topics == 2

    def test_two_groups_with_the_same_subject_name_get_qualifiers(self):
        docs = [
            _doc('Repository Search Portal', _unit(1.0), subject='Academic services and research'),
            _doc('Repository Archive Index', _unit(0.95, 0.05), subject='Academic services and research'),
            _doc('Grading Portal Records', _unit(0.0, 1.0), subject='Academic services and research'),
            _doc('Grading Sheet Encoder', _unit(0.05, 0.95), subject='Academic services and research'),
        ]
        topics = sorted(c.topic for c in analyze_topics(docs, k=2).clusters)
        assert len(set(topics)) == 2
        assert all(t.startswith('Academic services and research (Cluster ') for t in topics)
```

Also extend the existing endpoint shape check: in `TestTopicTrendsEndpoint.test_endpoint_returns_envelope_shape`, change the per-cluster key tuple to:

```python
            for k in ('cluster_id', 'topic', 'trend', 'thesis_count',
                      'keywords', 'sample_titles', 'thesis_ids',
                      'technology_tags', 'member_tags'):
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_topic_analysis.py -k "MeaningBased or envelope_shape"`
Expected: these fail:
- `test_groups_follow_meaning_not_shared_words` (TF-IDF pairs the identical abstracts);
- `test_group_is_named_after_its_members_reviewed_subject` (rule label "Internet of Things");
- `test_repository_thesis_is_not_labelled_iot`, `test_technology_tags_are_counted_per_group_and_listed_per_member` (`AttributeError: 'TopicCluster' object has no attribute 'technology_tags'`);
- `test_missing_vector_is_embedded_from_the_topic_text` (`embed_text` never called);
- `test_endpoint_returns_envelope_shape` (no `technology_tags` key).

The fallback, reorder and k-clamp tests may already pass; they are guards. If any other test passes unexpectedly, stop and find out why before implementing.

- [ ] **Step 3: Implement**

In `backend/theses/services/topic_analysis.py`:

(a) Replace the first two bullets of the module docstring (the TF-IDF and K-Means bullets) with:

```text
* **Grouping by meaning.** Each thesis's stored Sentence-BERT document vector
  (title, author keywords, abstract and opening text; see
  ``semantic_search.compose_thesis_text``) is grouped with agglomerative
  clustering on cosine distance (average linkage). Unlike K-Means this is
  deterministic: the same corpus always yields the same groups, whatever the
  row order. ``k`` targets ~``6`` theses per group, clamped to ``5–8``.

* **TF-IDF keywords** (``sklearn.feature_extraction.text.TfidfVectorizer``)
  still describe each group: the group's highest mean TF-IDF terms over
  title + abstract + keywords (``extracted_text`` excluded; see
  ``_compose_thesis_text``).

* **Group names** come from members' confirmed primary subjects
  (``_subject_label``); groups with no reviewed member fall back to the
  keyword naming table (``_label_cluster``).

* **Technology tags** (``Thesis.technology_tags``) are counted per group and
  listed per member. A technology is not a subject, so it never names a group.
```

(b) Add two fields to `_DocMeta` (after `keywords`):

```python
    subject: str | None = None
    tags: List[str] = field(default_factory=list)
```

(c) Add two fields to `TopicCluster` (after `thesis_ids`):

```python
    technology_tags: List[dict] = field(default_factory=list)   # [{'tag': 'IoT', 'count': 4}]
    member_tags: dict = field(default_factory=dict)             # thesis id -> ['IoT', 'AI']
```

(d) Add these helpers directly above `def analyze_topics(`:

```python
def _reviewed_subject_name(thesis) -> str | None:
    """The thesis's confirmed primary subject name; ``None`` while awaiting review."""
    if not getattr(thesis, 'subject_reviewed_at', None):
        return None
    subject = getattr(thesis, 'primary_subject', None)
    return getattr(subject, 'name', None) or None


def _document_vector(thesis, text: str):
    """Unit-length SBERT vector: the stored one, else computed now from ``text``.

    A thesis whose embedding failed or predates Phase 2A still gets grouped,
    from the same title/abstract/keywords text TF-IDF sees.
    """
    import numpy as np
    from .semantic_search import EMBEDDING_DIM, embed_text

    raw = getattr(thesis, 'embedding_vector', None)
    if raw:
        try:
            vector = np.asarray(raw, dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if vector.shape == (EMBEDDING_DIM,) and np.isfinite(vector).all() and norm > 1e-6:
                return vector / norm
        except (TypeError, ValueError):
            pass
    vector = np.asarray(embed_text(text), dtype=np.float32)
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


def _group_by_meaning(vectors, k: int):
    """Deterministic grouping of unit vectors by cosine distance."""
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    if k <= 1:
        return np.zeros(len(vectors), dtype=int)
    return AgglomerativeClustering(n_clusters=k, metric='cosine', linkage='average').fit_predict(vectors)


def _tag_summary(member_tag_lists) -> List[dict]:
    """Tag counts across a group, most common first, then alphabetical."""
    counts = Counter(tag for tags in member_tag_lists for tag in tags)
    return [
        {'tag': tag, 'count': count}
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
```

(e) In `analyze_topics`:

1. Replace the docstring's first line with `Group approved theses by meaning and describe each group.` Document `random_state` as: "Unused since grouping became deterministic; kept so existing callers keep working." Make `del random_state` the first statement of the body.
2. Replace the corpus-materialising block (`theses = list(queryset)` through the end of that `for` loop) with:

```python
    theses = list(queryset)
    kept: List = []
    documents: List[str] = []
    metadata: List[_DocMeta] = []
    for t in theses:
        text = _compose_thesis_text(t)
        if not text.strip():
            continue
        kept.append(t)
        documents.append(text)
        metadata.append(_DocMeta(
            id=str(t.id),
            title=t.title,
            keywords=[str(k) for k in (t.keywords or []) if str(k).strip()],
            subject=_reviewed_subject_name(t),
            tags=[str(tag) for tag in (getattr(t, 'technology_tags', None) or [])],
        ))
```

3. In the `n_docs == 1` branch, replace the topic line and the `TopicCluster(...)` call with:

```python
        topic = _subject_label([metadata[0].subject]) or _label_cluster(
            keywords, member_keywords=[metadata[0].keywords],
        )
        member_tags = {metadata[0].id: metadata[0].tags}
        cluster = TopicCluster(
            cluster_id=0,
            topic=topic,
            trend=_classify_trend(1, average_size=1.0, total_theses=1),
            thesis_count=1,
            keywords=keywords,
            sample_titles=[metadata[0].title],
            thesis_ids=[metadata[0].id],
            technology_tags=_tag_summary(member_tags.values()),
            member_tags=member_tags,
        )
```

4. Change the lazy imports under `# ── TF-IDF vectorisation` to:

```python
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
```

   (`KMeans` is no longer imported.)
5. Replace the whole `# ── K-Means clustering` block (from `chosen_k = ...` through `centroids = kmeans.cluster_centers_`) with:

```python
    # ── Grouping by meaning ────────────────────────────────────────────
    chosen_k = k if k is not None else _choose_k(n_docs)
    chosen_k = max(1, min(chosen_k, n_docs))
    if chosen_k == 1:
        labels = np.zeros(n_docs, dtype=int)
    else:
        vectors = np.vstack([_document_vector(t, doc) for t, doc in zip(kept, documents)])
        labels = _group_by_meaning(vectors, chosen_k)
```

6. In the per-cluster loop, replace `centroid = centroids[cluster_id]` with:

```python
        # The group's mean TF-IDF weights: its most distinctive terms.
        centroid = np.asarray(tfidf_matrix[member_indices].mean(axis=0)).ravel()
```

7. Replace the `topic = _label_cluster(...)` call in the loop with:

```python
        topic = _subject_label([metadata[i].subject for i in member_indices]) or _label_cluster(
            keywords,
            member_keywords=[metadata[i].keywords for i in member_indices],
        )
```

8. Before `clusters.append(TopicCluster(`, add `member_tags = {metadata[i].id: metadata[i].tags for i in member_indices}`. Add these arguments to that `TopicCluster(...)` call:

```python
            technology_tags=_tag_summary(member_tags.values()),
            member_tags=member_tags,
```

- [ ] **Step 4: Run the new tests, then the whole topic file**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_topic_analysis.py -k "MeaningBased or envelope_shape"`
Expected: `10 passed`.

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_topic_analysis.py`
Expected: all pass. If an older test fails (for example `test_clustering_groups_attendance_theses_together` or `test_real_shape_corpus_labels_each_cluster_honestly`), read the failure.
- If the change in grouping method explains it, the grouping must still satisfy the test's stated intent (e.g. attendance theses together). If it does not, the implementation is wrong: debug it.
- Only if the test asserts K-Means-specific membership that contradicts the spec, update that assertion and record the ruling in the commit message.

- [ ] **Step 5: Commit**

```bash
git add backend/theses/services/topic_analysis.py backend/theses/tests/test_topic_analysis.py
git commit -m "Group topics by meaning and report technology tags" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Subject suggestions service and endpoint

**Files:**
- Create: `backend/theses/services/subject_suggestions.py`
- Modify: `backend/theses/views.py` (add `ThesisSubjectSuggestionsView` after `ThesisSubjectReviewView`)
- Modify: `backend/theses/urls.py`
- Test: `backend/theses/tests/test_subject_suggestions.py` (create)

**Interfaces:**
- Produces: `suggest_subjects(thesis, *, limit: int = 2) -> list[dict]` (`{'code', 'name', 'score'}`, best first); `GET /api/v1/theses/<id>/subject-suggestions/` → `{'suggestions': [...]}` (URL name `thesis-subject-suggestions`); 403 `FORBIDDEN` for non-faculty; `{'suggestions': []}` for non-approved theses.

- [ ] **Step 1: Write the failing tests**

Create `backend/theses/tests/test_subject_suggestions.py`:

```python
"""Top-2 subject suggestions (theses/services/subject_suggestions.py) and
GET /api/v1/theses/<id>/subject-suggestions/."""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from theses.models import FileType, Program, ResearchSubject, Thesis, ThesisStatus


def _vec(*values):
    vector = [0.0] * 384
    for index, value in enumerate(values):
        vector[index] = value
    return vector


@pytest.fixture
def faculty(db):
    return User.objects.create_user(
        email='suggest-faculty@pampangastateu.edu.ph', first_name='F', last_name='S',
        role=Role.FACULTY, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(faculty):
    counter = {'n': 0}

    def _make(vector, subject_code=None, status=ThesisStatus.APPROVED):
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=f'Suggestion Thesis {n}', abstract='Abstract.', authors=['T, T.'], keywords=['k'],
            program=Program.BSIT.value, year=2024, adviser='', file_type=FileType.PDF,
            sha256=(f'{n:x}' + 'd' * 64)[:64], extracted_text='', status=status,
            uploaded_by=faculty, embedding_vector=vector,
        )
        if subject_code:
            thesis.primary_subject = ResearchSubject.objects.get(pk=subject_code)
            thesis.subject_reviewed_by = faculty
            thesis.subject_reviewed_at = timezone.now()
        thesis.uploaded_file.save(f'suggest_{n}.pdf', ContentFile(b'%PDF-1.4'), save=False)
        thesis.save()
        return thesis

    return _make


class TestSuggestSubjects:
    def test_closest_subjects_come_first(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        make_thesis(_vec(0.9, 0.1), 'EDU')
        make_thesis(_vec(0.0, 1.0), 'HEA')
        make_thesis(_vec(0.0, 0.0, 1.0), 'AGR')
        target = make_thesis(_vec(0.8, 0.2))
        assert [s['code'] for s in suggest_subjects(target)] == ['EDU', 'HEA']

    def test_a_thesis_never_supports_its_own_suggestion(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        only_health = make_thesis(_vec(0.0, 1.0), 'HEA')
        assert [s['code'] for s in suggest_subjects(only_health)] == ['EDU']

    def test_fewer_than_two_when_few_subjects_are_reviewed(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        target = make_thesis(_vec(0.5, 0.5))
        assert [s['code'] for s in suggest_subjects(target)] == ['EDU']

    def test_no_vector_means_no_suggestions(self, make_thesis):
        from theses.services.subject_suggestions import suggest_subjects
        make_thesis(_vec(1.0), 'EDU')
        assert suggest_subjects(make_thesis(None)) == []


@pytest.mark.django_db
class TestSubjectSuggestionsEndpoint:
    @staticmethod
    def _get(client, user, thesis):
        from auth_service.services import issue_token_pair
        token = issue_token_pair(user, request=None, remember_me=False).access_token
        return client.get(
            reverse('thesis-subject-suggestions', kwargs={'id': str(thesis.id)}),
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def test_faculty_get_suggestions(self, client, faculty, make_thesis):
        make_thesis(_vec(1.0), 'EDU')
        response = self._get(client, faculty, make_thesis(_vec(0.9, 0.1)))
        assert response.status_code == 200
        assert [s['code'] for s in response.json()['suggestions']] == ['EDU']

    def test_students_are_refused(self, client, make_thesis):
        student = User.objects.create_user(
            email='suggest-student@pampangastateu.edu.ph', first_name='S', last_name='T',
            role=Role.STUDENT, password='Test12345!Test',
        )
        assert self._get(client, student, make_thesis(_vec(1.0))).status_code == 403

    def test_unpublished_thesis_gets_no_suggestions(self, client, faculty, make_thesis):
        make_thesis(_vec(1.0), 'EDU')
        pending = make_thesis(_vec(1.0), status=ThesisStatus.PENDING_REVIEW)
        assert self._get(client, faculty, pending).json() == {'suggestions': []}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_subject_suggestions.py`
Expected:
- service tests fail with `ModuleNotFoundError: ... subject_suggestions`;
- endpoint tests fail with `NoReverseMatch: 'thesis-subject-suggestions'`.

- [ ] **Step 3: Implement the service**

Create `backend/theses/services/subject_suggestions.py`:

```python
"""Suggest a primary research subject from the most similar reviewed theses.

Nearest subject centroid over Sentence-BERT document vectors: each subject's
reviewed theses are averaged into one direction, and the subjects closest to
the thesis being reviewed are suggested. On the initial 52 reviewed theses
(leave-one-out) the right subject was first 65% of the time and within two
suggestions 77% of the time, so a suggestion only pre-selects a choice;
faculty or an administrator always confirms the subject.
"""

from __future__ import annotations

from typing import List

SUGGESTION_LIMIT = 2


def _unit(raw):
    """Unit-length float vector, or ``None`` when unusable."""
    import numpy as np
    from .semantic_search import EMBEDDING_DIM

    if raw is None:
        return None
    try:
        vector = np.asarray(raw, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if vector.shape != (EMBEDDING_DIM,) or not np.isfinite(vector).all():
        return None
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-6 else None


def suggest_subjects(thesis, *, limit: int = SUGGESTION_LIMIT) -> List[dict]:
    """Up to ``limit`` subjects as ``{'code', 'name', 'score'}``, best first.

    The thesis itself never counts toward a centroid, so a reviewed thesis is
    only compared with the others. Subjects without usable reviewed vectors
    are never suggested.
    """
    from theses.models import Thesis, ThesisStatus

    target = _unit(getattr(thesis, 'embedding_vector', None))
    if target is None:
        return []

    reviewed = (
        Thesis.objects
        .filter(status=ThesisStatus.APPROVED, primary_subject__isnull=False,
                subject_reviewed_at__isnull=False)
        .exclude(pk=thesis.pk)
        .select_related('primary_subject')
        .only('id', 'embedding_vector', 'primary_subject', 'primary_subject__name')
    )
    totals: dict = {}
    names: dict = {}
    for row in reviewed:
        vector = _unit(row.embedding_vector)
        if vector is None:
            continue
        code = row.primary_subject_id
        totals[code] = totals[code] + vector if code in totals else vector
        names[code] = row.primary_subject.name

    suggestions = []
    for code, total in totals.items():
        centroid = _unit(total)
        if centroid is None:
            continue
        suggestions.append({'code': code, 'name': names[code], 'score': round(float(centroid @ target), 4)})
    suggestions.sort(key=lambda item: (-item['score'], item['code']))
    return suggestions[:limit]
```

- [ ] **Step 4: Implement the endpoint**

In `backend/theses/views.py`, directly after the `ThesisSubjectReviewView` class (its last line is `return Response(ThesisDetailSerializer(thesis).data)` following `select_related('primary_subject', 'subject_reviewed_by', 'uploaded_by').get(pk=uid)`), add:

```python
class ThesisSubjectSuggestionsView(APIView):
    """Two likely primary subjects for an approved thesis.

    Suggestions only - a subject is assigned solely through
    ThesisSubjectReviewView, by faculty or an administrator.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, id, *args, **kwargs):
        if getattr(request.user, 'role', None) not in (Role.FACULTY, Role.ADMINISTRATOR):
            return make_error_response(
                code='FORBIDDEN', message='Only faculty and administrators may review subjects.',
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            uid = uuid.UUID(str(id))
        except (ValueError, TypeError):
            raise NotFound(detail='Thesis not found.')
        try:
            thesis = Thesis.objects.only('id', 'status', 'embedding_vector').get(pk=uid)
        except Thesis.DoesNotExist:
            raise NotFound(detail='Thesis not found.')
        if thesis.status != ThesisStatus.APPROVED:
            return Response({'suggestions': []})

        from .services.subject_suggestions import suggest_subjects
        return Response({'suggestions': suggest_subjects(thesis)})
```

In `backend/theses/urls.py`, add `ThesisSubjectSuggestionsView,` to the `from .views import (...)` list (after `ThesisSubjectReviewView,`), and add after the `'<str:id>/subject/'` path:

```python
    path('<str:id>/subject-suggestions/', ThesisSubjectSuggestionsView.as_view(), name='thesis-subject-suggestions'),
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest -q -p no:cacheprovider theses/tests/test_subject_suggestions.py`
Expected: `7 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/theses/services/subject_suggestions.py backend/theses/views.py backend/theses/urls.py backend/theses/tests/test_subject_suggestions.py
git commit -m "Suggest likely research subjects for faculty review" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend - technology tags on the Trend page, suggestions on thesis detail

**Files:**
- Modify: `frontend/src/pages/TrendAnalysisPage.jsx`
- Modify: `frontend/src/pages/ThesisDetailPage.jsx`

**Interfaces:**
- Consumes: cluster fields `technology_tags` (`[{tag, count}]`) and `member_tags` (`{id: [tag]}`) from Task 5; `GET /theses/<id>/subject-suggestions/` from Task 6. Both are optional: older responses without them must render as before.

- [ ] **Step 1: Record the lint baseline**

Run (in `frontend/`): `npx eslint src/pages/TrendAnalysisPage.jsx src/pages/ThesisDetailPage.jsx`
Expected: note the existing problem count (4 in TrendAnalysisPage, 1 in ThesisDetailPage at the time of writing). The task must not add any.

- [ ] **Step 2: Add the tag components** (in `TrendAnalysisPage.jsx`, directly above `function ClusterThesisRow`)

```jsx
// Technology tags — the technologies a group's theses are actually about
// (IoT, AI, NLP…). The backend only tags a thesis with evidence (a mention
// in its title, keywords or abstract, or dense full-text mentions), so a
// thesis that merely repeats "analysis" is never tagged IoT.
function TechnologyTags({ tags, isDark, label = 'Technologies' }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="mb-3">
      {label && (
        <div className={`text-xs font-semibold uppercase tracking-wider mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
          {label}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {tags.map(({ tag, count }) => (
          <Badge
            key={tag}
            variant="outline"
            className={`text-xs px-2 py-0.5 h-auto ${
              isDark
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20 hover:bg-emerald-500/10'
                : 'bg-emerald-50 text-emerald-700 border-emerald-100 hover:bg-emerald-50'
            }`}
          >
            {tag}
            <span aria-hidden="true">{` ×${count}`}</span>
            <span className="sr-only">{`, ${count} thes${count === 1 ? 'is' : 'es'}`}</span>
          </Badge>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Show tags on the card, the group header and each member row**

(a) In the cluster card, directly above `{cluster.sample_titles && cluster.sample_titles.length > 0 && (`, insert:

```jsx
        <TechnologyTags tags={cluster.technology_tags} isDark={isDark} />
```

(b) In `ClusterDetailView`, the header block ends with the keywords block, then `      </div>` and the blank line before `      {overflowCount > 0 && (`. Insert before that `      </div>`:

```jsx
        {cluster.technology_tags?.length > 0 && (
          <div className="mt-3">
            <TechnologyTags tags={cluster.technology_tags} isDark={isDark} />
          </div>
        )}
```

(c) Change `function ClusterThesisRow({ thesis, isDark })` to `function ClusterThesisRow({ thesis, isDark, tags = [] })`. After its `<p ...>{thesis.program} · {thesis.year}</p>`, add:

```jsx
      {tags.length > 0 && (
        <p className="mt-1 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <span
              key={tag}
              className={`text-[11px] px-1.5 py-0.5 rounded ${isDark ? 'bg-emerald-500/10 text-emerald-300' : 'bg-emerald-50 text-emerald-700'}`}
            >
              {tag}
            </span>
          ))}
        </p>
      )}
```

(d) Replace `<ClusterThesisRow key={thesis.id} thesis={thesis} isDark={isDark} />` with:

```jsx
            <ClusterThesisRow
              key={thesis.id}
              thesis={thesis}
              isDark={isDark}
              tags={cluster.member_tags?.[thesis.id] || []}
            />
```

(e) Replace the header string `'Explore text clusters generated with TF-IDF and K-Means.'` with:

```jsx
'Explore groups of theses with similar meaning. Group names come from reviewed subjects; tags show the technologies each thesis uses.'
```

- [ ] **Step 4: Add subject suggestions to `ThesisDetailPage.jsx`**

(a) After `const [selectedSubject, setSelectedSubject] = useState('');` add:

```jsx
  const [suggestions, setSuggestions] = useState([]);
```

(b) After the effect that loads `/theses/subjects/` (it ends with `}, [isAuthenticated, canReviewSubject]);`), add:

```jsx
  // Top-2 suggestions for a thesis awaiting subject review. They only
  // pre-select the dropdown; the reviewer still confirms.
  const awaitingSubjectReview = thesis?.status === 'approved' && !thesis?.primary_subject;
  useEffect(() => {
    if (!isAuthenticated || !canReviewSubject || !awaitingSubjectReview) return;
    let cancelled = false;
    client.get(`/theses/${id}/subject-suggestions/`)
      .then((res) => { if (!cancelled) setSuggestions(res.data?.suggestions || []); })
      .catch(() => { if (!cancelled) setSuggestions([]); });
    return () => { cancelled = true; };
  }, [isAuthenticated, canReviewSubject, awaitingSubjectReview, id]);
```

(c) Directly above `{thesis.subject_reviewed_at && (` inside the review block, add:

```jsx
                    {awaitingSubjectReview && suggestions.length > 0 && (
                      <div className="mt-2">
                        <p className={`text-xs mb-1.5 ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                          Suggested from similar reviewed theses. Check the thesis before confirming.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {suggestions.map((s) => (
                            <button
                              key={s.code}
                              type="button"
                              onClick={() => setSelectedSubject(s.code)}
                              aria-pressed={selectedSubject === s.code}
                              className={`rounded-full border px-3 py-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                                selectedSubject === s.code
                                  ? 'bg-blue-600 border-blue-600 text-white'
                                  : isDark
                                    ? 'border-white/15 text-gray-200 hover:bg-white/[0.06]'
                                    : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                              }`}
                            >
                              {s.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
```

- [ ] **Step 5: Lint and build**

Run (in `frontend/`): `npx eslint src/pages/TrendAnalysisPage.jsx src/pages/ThesisDetailPage.jsx`
Expected: the same problem count as Step 1, and none on lines this task added.

Run: `npm run build`
Expected: `✓ built`.

- [ ] **Step 6: Manual check** (signed in as faculty). The local dev frontend cannot reach the demo backend (it only accepts the Vercel origin), so without a separate local dev backend, do this check on the live site after Task 9 Step 5.

1. Trend Analysis → Explore text clusters: cards show "Technologies" chips such as `IoT ×3`. A group's detail page lists each thesis with its tags.
2. Trend Analysis → Reviewed subjects: cards render exactly as before, with no Technologies row.
3. A thesis awaiting subject review: two suggestion chips appear. Clicking one selects it in the dropdown without saving; "Confirm subject" saves.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/TrendAnalysisPage.jsx frontend/src/pages/ThesisDetailPage.jsx
git commit -m "Show technology tags on topic groups and subject suggestions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Methodology and manuscript wording

**Files:**
- Modify: `docs/reviewed-subject-methodology.md`

- [ ] **Step 1: Replace the "Explore text clusters" paragraph** (the one starting `**Explore text clusters** retains the existing TF-IDF and K-Means endpoint`) with:

```markdown
**Explore text clusters** groups approved theses by meaning. Each thesis's title, author keywords, abstract and opening text are encoded with Sentence-BERT (all-MiniLM-L6-v2), and the vectors are grouped by agglomerative clustering on cosine distance with average linkage, which returns the same groups for the same corpus every time. Each group is named after its members' confirmed primary subjects: the most common subject when it covers at least half of the reviewed members and is not tied, otherwise the two most common subjects. A group with no reviewed member keeps the keyword naming table. TF-IDF still lists each group's top keywords. Technology tags (for example IoT, AI and NLP) are listed per thesis when the technology is named in its title, keywords or abstract, or at least three times and at least once per 10,000 characters in its full text. On the initial 52 theses the groups agree with the reviewed subjects roughly three times as closely as the earlier TF-IDF and K-Means groups (adjusted Rand index 0.29 versus 0.10). The groups remain exploratory; reviewed subjects are the authoritative classification.

For a thesis awaiting subject review, faculty and administrators see the two subjects whose reviewed theses are most similar in meaning (nearest subject centroid over Sentence-BERT vectors). In a leave-one-out test on the initial 52 theses, the correct subject was the first suggestion 65% of the time and among the two suggestions 77% of the time. A suggestion never assigns a subject.
```

- [ ] **Step 2: Replace the last two sentences of the "Manuscript wording" quote** (from `A separate exploratory view retains TF-IDF vectorization` to the end of the quote) with:

```markdown
> A separate exploratory view groups approved theses by meaning: Sentence-BERT document vectors are grouped by agglomerative clustering on cosine distance, each group is named after its members' confirmed primary subjects, and TF-IDF lists each group's top keywords. Technology tags such as IoT or AI are shown per thesis when the technology is evidenced in its metadata or full text, so a technology never names a group. For theses awaiting subject review, the two most similar subjects are suggested to faculty, who confirm the final subject.
```

- [ ] **Step 3: Commit**

```bash
git add docs/reviewed-subject-methodology.md
git commit -m "Describe meaning-based topic groups and subject suggestions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Full verification, backfill and release

**Files:** none changed. This task only runs checks and, with the owner's approval, releases.

- [ ] **Step 1: Full backend suite**

Run (in `backend/`): `python -m pytest -q -p no:cacheprovider`
Expected: all pass (previous baseline 1337 passed, 3 skipped, plus this plan's new tests). Name any failure in the report, including ones this plan did not cause.

- [ ] **Step 2: Frontend lint and build**

Run (in `frontend/`): `npx eslint src/pages/TrendAnalysisPage.jsx src/pages/ThesisDetailPage.jsx`, then `npm run build`
Expected: no new ESLint problems; `✓ built`.

- [ ] **Step 3: Ask the owner for approval to release.** Wait for an explicit yes. Then, in order:

```bash
python manage.py migrate
python manage.py embed_theses --regenerate
```

Expected: `Applying theses.0007_thesis_technology_tags... OK`, then `Done: 52 embedded, 0 failed.` (count = approved plus other theses). The regeneration fills `technology_tags`.

- [ ] **Step 4: Evaluate on the live corpus (read-only)**

Run (in `backend/`) `python manage.py shell` with:

```python
from sklearn.metrics import adjusted_rand_score
from theses.services.topic_analysis import analyze_topics, get_topic_trends_queryset
rows = list(get_topic_trends_queryset())
result = analyze_topics(rows)
group_of = {tid: c.cluster_id for c in result.clusters for tid in c.thesis_ids}
subject_of = {str(t.id): t.primary_subject_id for t in rows}
ids = list(group_of)
print('ARI vs reviewed subjects:', round(adjusted_rand_score([subject_of[i] for i in ids], [group_of[i] for i in ids]), 3))
for c in result.clusters:
    print(f'[{c.thesis_count}] {c.topic} | {c.technology_tags}')
thesys = next(t for t in rows if t.title.startswith('THESYS+'))
print('THESYS+ group:', next(c.topic for c in result.clusters if str(thesys.id) in c.thesis_ids))
```

Expected: ARI at least 0.25 (about 0.29). The THESYS+ group is "Academic services and research", and no group name contains "Internet of Things". IoT counts appear only as tags.

- [ ] **Step 5: Restart the backend, push, confirm the deploy** (after the owner's approval in Step 3)

In PowerShell, from the repo root:

```powershell
.\backend\scripts\stop_demo_backend.ps1
.\backend\scripts\start_demo_backend.ps1 -NgrokHost province-veal-eleven.ngrok-free.dev
```

```bash
git push origin main
```

Expected:
- the start script prints `THESYSplus demo backend running on 127.0.0.1:8000 ...`;
- within about 2 minutes, the script `https://thesysplus.vercel.app/` loads (`/assets/index-*.js`) contains `Technologies` and `subject-suggestions`.
