"""Tests for the review-time redundancy analyzer.

Every vector here is hand-built. No SBERT model is loaded anywhere in this
module — that is itself part of what is under test: ``analyze_titles`` must
never encode text on the render path.

Cosine control
--------------
Vectors live in R^384. To place a corpus vector at an exact cosine ``c`` from
the probe, the probe is the first basis vector ``e0`` and the corpus vector is
``c * e0 + sqrt(1 - c^2) * e1``. Both are unit-norm and their dot product is
``c``, which is what cosine similarity reduces to for normalised vectors.
"""

from __future__ import annotations

import math

import pytest
from django.core.files.base import ContentFile

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus
from theses.services import redundancy
from theses.services.redundancy import (
    EMBEDDING_DIM,
    LABEL_CLEAN,
    LABEL_HIGH,
    LABEL_MODERATE,
    LABEL_UNKNOWN,
    REASON_DIMENSION_MISMATCH,
    REASON_MATH_UNAVAILABLE,
    REASON_MISSING_EMBEDDING,
    advisory_for,
    analyze_titles,
    invalidate_cache,
    label_for,
)
from theses.services.title_similarity import THRESHOLD_HIGH, THRESHOLD_MODERATE


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def basis(index: int = 0) -> list[float]:
    """Unit vector along one axis."""
    vector = [0.0] * EMBEDDING_DIM
    vector[index] = 1.0
    return vector


def at_cosine(c: float, *, axis: int = 1) -> list[float]:
    """Unit vector whose dot product with ``basis(0)`` is exactly ``c``."""
    vector = [0.0] * EMBEDDING_DIM
    vector[0] = c
    vector[axis] = math.sqrt(max(0.0, 1.0 - c * c))
    return vector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    """The corpus matrix cache is process-local module state."""
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def isolate_media(settings, tmp_path):
    """Keep test uploads out of the real MEDIA_ROOT.

    The factory below writes a real file per thesis. Without this the suite
    accumulates thousands of stray PDFs under media/theses/ that Django's
    storage then de-duplicates with random suffixes on every run.

    Not autouse: overriding a setting fires ``setting_changed`` receivers that
    reach for the database connection, which would force the pure label-mapping
    tests to need ``django_db``.
    """
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        email='redundancy.faculty@pampangastateu.edu.ph',
        first_name='Redundancy',
        last_name='Reviewer',
        role=Role.FACULTY,
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, faculty_user, isolate_media):
    """Factory creating a Thesis with an explicit title_embedding."""
    counter = {'n': 0}

    def _make(
        title: str = 'A Thesis',
        *,
        title_embedding=None,
        status: str = ThesisStatus.APPROVED,
        save: bool = True,
    ) -> Thesis:
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=title,
            abstract=f'Abstract for {title}',
            authors=['Tester, T.'],
            keywords=['test'],
            program=Program.BSIT.value,
            year=2024,
            file_type=FileType.PDF,
            sha256=(f'{n:x}' + 'b' * 64)[:64],
            status=status,
            uploaded_by=faculty_user,
            title_embedding=title_embedding,
        )
        thesis.uploaded_file.save(
            f'redundancy_{n}.pdf',
            ContentFile(b'%PDF-1.4\n%dummy'),
            save=False,
        )
        if save:
            thesis.save()
        return thesis

    return _make


# ---------------------------------------------------------------------------
# label_for — pure function, exact boundaries
# ---------------------------------------------------------------------------

class TestLabelFor:
    """Boundary behaviour is inclusive-lower, matching title_similarity."""

    def test_exact_moderate_boundary(self):
        assert label_for(THRESHOLD_MODERATE) == LABEL_MODERATE
        assert label_for(0.60) == LABEL_MODERATE

    def test_exact_high_boundary(self):
        assert label_for(THRESHOLD_HIGH) == LABEL_HIGH
        assert label_for(0.85) == LABEL_HIGH

    def test_just_below_boundaries(self):
        assert label_for(0.5999) == LABEL_CLEAN
        assert label_for(0.8499) == LABEL_MODERATE

    def test_extremes(self):
        assert label_for(-1.0) == LABEL_CLEAN
        assert label_for(0.0) == LABEL_CLEAN
        assert label_for(1.0) == LABEL_HIGH

    def test_thresholds_are_imported_not_redeclared(self):
        """redundancy must not fork the cut-offs away from title_similarity."""
        assert THRESHOLD_HIGH == 0.85
        assert THRESHOLD_MODERATE == 0.60


class TestAdvisoryFor:
    def test_all_four_labels_have_distinct_non_empty_text(self):
        labels = [LABEL_HIGH, LABEL_MODERATE, LABEL_CLEAN, LABEL_UNKNOWN]
        texts = [advisory_for(label) for label in labels]
        assert all(text and text.strip() for text in texts)
        assert all(len(text) <= 300 for text in texts)
        assert len(set(texts)) == 4

    def test_unknown_label_falls_back(self):
        assert advisory_for('not-a-real-label') == advisory_for(LABEL_UNKNOWN)


# ---------------------------------------------------------------------------
# Structural guarantee: no live encoding
# ---------------------------------------------------------------------------

class TestNeverEncodes:
    def test_module_has_no_semantic_search_import(self):
        """The absence of this import is what keeps SBERT off the render path."""
        from pathlib import Path
        source = Path(redundancy.__file__).read_text(encoding='utf-8')
        code_lines = [
            line for line in source.splitlines()
            if line.strip().startswith(('import ', 'from '))
        ]
        assert not any('semantic_search' in line for line in code_lines)

    def test_embedding_dim_matches_semantic_search(self):
        from theses.services.semantic_search import EMBEDDING_DIM as SS_DIM
        assert EMBEDDING_DIM == SS_DIM

    def test_analyze_titles_does_not_call_embed_text(self, make_thesis, monkeypatch):
        from theses.services import semantic_search

        def explode(*args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError('embed_text must never be called at render time')

        monkeypatch.setattr(semantic_search, 'embed_text', explode)

        make_thesis('Approved One', title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is True


# ---------------------------------------------------------------------------
# Empty and degenerate inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_probe_list_returns_empty_map(self, db, django_assert_num_queries):
        with django_assert_num_queries(0):
            assert analyze_titles([]) == {}

    def test_empty_approved_corpus_is_a_measurement_not_a_failure(self, make_thesis):
        probe = make_thesis('Lonely', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)
        result = analyze_titles([probe])[probe.id]

        # "computed" answers "could we measure?", not "was there anything to
        # measure against". Zero overlap over an empty corpus is a real answer.
        assert result.computed is True
        assert result.score == 0.0
        assert result.label == LABEL_CLEAN
        assert result.matched_thesis_id is None
        assert result.matched_title == ''
        assert result.corpus_size == 0
        assert result.reason == ''

    def test_corpus_of_only_the_probe_itself(self, make_thesis):
        probe = make_thesis('Only Approved', title_embedding=basis(0),
                            status=ThesisStatus.APPROVED)
        result = analyze_titles([probe])[probe.id]

        assert result.computed is True
        assert result.score == 0.0
        assert result.label == LABEL_CLEAN
        assert result.matched_thesis_id is None
        assert result.corpus_size == 0


# ---------------------------------------------------------------------------
# Self-exclusion
# ---------------------------------------------------------------------------

class TestSelfExclusion:
    def test_approved_probe_never_matches_itself(self, make_thesis):
        """Even at cosine 1.0 against itself, the match must be the other row."""
        probe = make_thesis('Identical Title', title_embedding=basis(0),
                            status=ThesisStatus.APPROVED)
        other = make_thesis('Distant Title', title_embedding=at_cosine(0.1),
                            status=ThesisStatus.APPROVED)

        result = analyze_titles([probe])[probe.id]

        assert result.matched_thesis_id != probe.id
        assert result.matched_thesis_id == other.id
        assert result.corpus_size == 1

    def test_self_exclusion_holds_for_every_probe_in_a_batch(self, make_thesis):
        a = make_thesis('A', title_embedding=basis(0))
        b = make_thesis('B', title_embedding=basis(1))
        c = make_thesis('C', title_embedding=basis(2))

        results = analyze_titles([a, b, c])

        for thesis in (a, b, c):
            assert results[thesis.id].matched_thesis_id != thesis.id


# ---------------------------------------------------------------------------
# Scoring and labelling through analyze_titles
# ---------------------------------------------------------------------------

class TestScoring:
    @pytest.mark.parametrize('cosine,expected', [
        (0.95, LABEL_HIGH),
        (0.90, LABEL_HIGH),
        (0.70, LABEL_MODERATE),
        (0.65, LABEL_MODERATE),
        (0.30, LABEL_CLEAN),
        (0.00, LABEL_CLEAN),
    ])
    def test_label_matches_score_band(self, make_thesis, cosine, expected):
        make_thesis('Approved', title_embedding=at_cosine(cosine))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]

        assert result.score == pytest.approx(cosine, abs=1e-5)
        assert result.label == expected
        # The label must always be exactly what label_for says about the
        # score that was actually returned.
        assert result.label == label_for(result.score)

    def test_score_is_clamped_to_unit_interval(self, make_thesis):
        make_thesis('Approved', title_embedding=basis(0))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]
        assert -1.0 <= result.score <= 1.0

    def test_matched_title_is_the_stored_title(self, make_thesis):
        make_thesis('The Closest Match', title_embedding=at_cosine(0.95))
        make_thesis('Something Else', title_embedding=at_cosine(0.2))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]
        assert result.matched_title == 'The Closest Match'

    def test_highest_scoring_match_wins(self, make_thesis):
        make_thesis('Low', title_embedding=at_cosine(0.2))
        best = make_thesis('High', title_embedding=at_cosine(0.93))
        make_thesis('Mid', title_embedding=at_cosine(0.5))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]
        assert result.matched_thesis_id == best.id


# ---------------------------------------------------------------------------
# Corpus membership
# ---------------------------------------------------------------------------

class TestCorpusMembership:
    def test_only_approved_theses_enter_the_corpus(self, make_thesis):
        make_thesis('Pending', title_embedding=at_cosine(0.99),
                    status=ThesisStatus.PENDING_REVIEW)
        make_thesis('Rejected', title_embedding=at_cosine(0.99),
                    status=ThesisStatus.REJECTED)
        approved = make_thesis('Approved', title_embedding=at_cosine(0.3),
                               status=ThesisStatus.APPROVED)

        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)
        result = analyze_titles([probe])[probe.id]

        # The 0.99 rows are not approved, so they must not be reachable.
        assert result.matched_thesis_id == approved.id
        assert result.corpus_size == 1

    def test_approved_row_without_an_embedding_is_not_in_the_corpus(self, make_thesis):
        make_thesis('No Vector', title_embedding=None)
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]
        assert result.corpus_size == 0
        assert result.matched_thesis_id is None

    def test_malformed_corpus_row_is_dropped_not_fatal(self, make_thesis):
        make_thesis('Malformed', title_embedding=[0.1, 0.2, 0.3])
        good = make_thesis('Good', title_embedding=at_cosine(0.4))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        result = analyze_titles([probe])[probe.id]

        assert result.computed is True
        assert result.matched_thesis_id == good.id
        # The malformed row must not inflate the corpus count either.
        assert result.corpus_size == 1


# ---------------------------------------------------------------------------
# Degradation ladder
# ---------------------------------------------------------------------------

class TestDegradation:
    @pytest.mark.parametrize('bad_vector', [
        None,
        [],
        'not-a-list',
        {'a': 1},
    ])
    def test_absent_embedding(self, make_thesis, bad_vector):
        probe = make_thesis('Probe', title_embedding=bad_vector,
                            status=ThesisStatus.PENDING_REVIEW, save=False)
        result = analyze_titles([probe])[probe.id]

        assert result.computed is False
        assert result.reason == REASON_MISSING_EMBEDDING
        assert result.label == LABEL_UNKNOWN
        assert result.score == 0.0
        assert result.matched_thesis_id is None
        assert result.matched_title == ''
        assert result.corpus_size == 0

    @pytest.mark.parametrize('length', [1, 100, 383, 385, 768])
    def test_wrong_dimension_is_distinguished_from_absent(self, make_thesis, length):
        probe = make_thesis('Probe', title_embedding=[0.1] * length,
                            status=ThesisStatus.PENDING_REVIEW, save=False)
        result = analyze_titles([probe])[probe.id]

        assert result.computed is False
        assert result.reason == REASON_DIMENSION_MISMATCH

    def test_right_length_but_non_finite_is_treated_as_absent(self, make_thesis):
        vector = basis(0)
        vector[5] = float('nan')
        probe = make_thesis('Probe', title_embedding=vector,
                            status=ThesisStatus.PENDING_REVIEW, save=False)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is False
        assert result.reason == REASON_MISSING_EMBEDDING

    def test_zero_vector_is_treated_as_absent(self, make_thesis):
        """embed_text returns an all-zero vector for a whitespace-only title."""
        probe = make_thesis('Probe', title_embedding=[0.0] * EMBEDDING_DIM,
                            status=ThesisStatus.PENDING_REVIEW, save=False)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is False
        assert result.reason == REASON_MISSING_EMBEDDING

    def test_non_numeric_elements_are_treated_as_absent(self, make_thesis):
        probe = make_thesis('Probe', title_embedding=['x'] * EMBEDDING_DIM,
                            status=ThesisStatus.PENDING_REVIEW, save=False)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is False
        assert result.reason == REASON_MISSING_EMBEDDING

    def test_corpus_load_failure_degrades_without_raising(self, make_thesis, monkeypatch):
        make_thesis('Approved', title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        def boom(*args, **kwargs):
            raise RuntimeError('database is on fire')

        monkeypatch.setattr(redundancy, '_load_corpus', boom)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is False
        assert result.reason == REASON_MATH_UNAVAILABLE

    def test_matmul_failure_degrades_without_raising(self, make_thesis, monkeypatch):
        make_thesis('Approved', title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        real_load = redundancy._load_corpus

        def sabotage(np):
            ids, titles, matrix = real_load(np)
            # A matrix with the wrong inner dimension makes the matmul raise.
            return ids, titles, matrix[:, :10]

        monkeypatch.setattr(redundancy, '_load_corpus', sabotage)

        result = analyze_titles([probe])[probe.id]
        assert result.computed is False
        assert result.reason == REASON_MATH_UNAVAILABLE

    def test_degradation_does_not_overwrite_earlier_reasons(self, make_thesis, monkeypatch):
        """A math failure must not relabel a probe that had no vector at all."""
        make_thesis('Approved', title_embedding=at_cosine(0.9))
        no_vector = make_thesis('No Vector', title_embedding=None,
                                status=ThesisStatus.PENDING_REVIEW, save=False)
        usable = make_thesis('Usable', title_embedding=basis(0),
                             status=ThesisStatus.PENDING_REVIEW)

        monkeypatch.setattr(
            redundancy, '_load_corpus',
            lambda np: (_ for _ in ()).throw(RuntimeError('no math')),
        )

        results = analyze_titles([no_vector, usable])

        assert results[no_vector.id].reason == REASON_MISSING_EMBEDDING
        assert results[usable.id].reason == REASON_MATH_UNAVAILABLE

    def test_reason_is_empty_exactly_when_computed(self, make_thesis):
        make_thesis('Approved', title_embedding=at_cosine(0.5))
        good = make_thesis('Good', title_embedding=basis(0),
                           status=ThesisStatus.PENDING_REVIEW)
        bad = make_thesis('Bad', title_embedding=None,
                          status=ThesisStatus.PENDING_REVIEW, save=False)

        results = analyze_titles([good, bad])

        assert results[good.id].computed is True
        assert results[good.id].reason == ''
        assert results[bad.id].computed is False
        assert results[bad.id].reason != ''


# ---------------------------------------------------------------------------
# Total function / total coverage
# ---------------------------------------------------------------------------

class TestTotality:
    def test_every_probe_gets_exactly_one_result(self, make_thesis):
        probes = [
            make_thesis('Good', title_embedding=basis(0)),
            make_thesis('None', title_embedding=None, save=False),
            make_thesis('Short', title_embedding=[0.5] * 10, save=False),
            make_thesis('Zero', title_embedding=[0.0] * EMBEDDING_DIM, save=False),
        ]
        results = analyze_titles(probes)

        assert set(results) == {p.id for p in probes}
        assert len(results) == len(probes)

    def test_duplicate_ids_collapse_to_one_entry(self, make_thesis):
        probe = make_thesis('Dup', title_embedding=basis(0))
        results = analyze_titles([probe, probe, probe])

        assert set(results) == {probe.id}
        assert len(results) == 1

    def test_unsaved_instances_are_accepted(self, make_thesis):
        make_thesis('Approved', title_embedding=at_cosine(0.7))
        unsaved = make_thesis('Unsaved', title_embedding=basis(0), save=False)

        result = analyze_titles([unsaved])[unsaved.id]
        assert result.computed is True

    def test_analysis_writes_nothing(self, make_thesis):
        approved = make_thesis('Approved', title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        before = (approved.updated_at, probe.updated_at, probe.status)
        analyze_titles([probe])
        approved.refresh_from_db()
        probe.refresh_from_db()

        assert (approved.updated_at, probe.updated_at, probe.status) == before


# ---------------------------------------------------------------------------
# Batch equals single
# ---------------------------------------------------------------------------

class TestBatchEqualsSingle:
    def test_batch_and_single_agree(self, make_thesis):
        """Guaranteed by ordering the corpus on ('created_at', 'id')."""
        make_thesis('C1', title_embedding=at_cosine(0.91))
        make_thesis('C2', title_embedding=at_cosine(0.62))
        make_thesis('C3', title_embedding=at_cosine(0.15))

        probes = [
            make_thesis('P1', title_embedding=basis(0),
                        status=ThesisStatus.PENDING_REVIEW),
            make_thesis('P2', title_embedding=at_cosine(0.5),
                        status=ThesisStatus.PENDING_REVIEW),
            make_thesis('P3', title_embedding=basis(3),
                        status=ThesisStatus.PENDING_REVIEW),
        ]

        batch = analyze_titles(probes)

        for probe in probes:
            single = analyze_titles([probe])[probe.id]
            assert batch[probe.id].score == pytest.approx(single.score, abs=1e-9)
            assert batch[probe.id].label == single.label
            assert batch[probe.id].matched_thesis_id == single.matched_thesis_id
            assert batch[probe.id].corpus_size == single.corpus_size

    def test_tied_scores_resolve_deterministically(self, make_thesis):
        """Two corpus rows at identical cosine resolve by corpus order.

        The winner is the first row under the service's ``('created_at', 'id')``
        ordering — which is not necessarily the row created first in wall-clock
        terms. When two rows share a ``created_at`` tick the ordering falls
        back to the UUID primary key, so the expected winner is derived from
        the same ordering rather than assumed from creation sequence.
        """
        make_thesis('First', title_embedding=at_cosine(0.8, axis=1))
        make_thesis('Second', title_embedding=at_cosine(0.8, axis=2))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        expected = (
            Thesis.objects
            .filter(status=ThesisStatus.APPROVED, title_embedding__isnull=False)
            .order_by('created_at', 'id')
            .values_list('id', flat=True)
            .first()
        )

        for _ in range(3):
            invalidate_cache()
            result = analyze_titles([probe])[probe.id]
            assert result.score == pytest.approx(0.8, abs=1e-5)
            assert result.matched_thesis_id == expected


# ---------------------------------------------------------------------------
# Corpus matrix cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_second_call_reuses_the_matrix(self, make_thesis, django_assert_num_queries):
        make_thesis('Approved', title_embedding=at_cosine(0.5))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        analyze_titles([probe])            # cold — aggregate + corpus SELECT

        # Warm: only the aggregate query that derives the cache key.
        with django_assert_num_queries(1):
            analyze_titles([probe])

    def test_new_approved_thesis_invalidates_the_cache(self, make_thesis):
        make_thesis('First', title_embedding=at_cosine(0.2))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        first = analyze_titles([probe])[probe.id]
        assert first.corpus_size == 1

        closer = make_thesis('Closer', title_embedding=at_cosine(0.97))
        second = analyze_titles([probe])[probe.id]

        assert second.corpus_size == 2
        assert second.matched_thesis_id == closer.id

    def test_retitling_an_approved_thesis_invalidates_the_cache(self, make_thesis):
        """A retitle moves max(updated_at) but not the row count.

        The sleep crosses a clock tick. This is the accepted cache-key
        collision the service documents: the key is
        ``(count, max(updated_at))``, so two writes landing inside the same
        ``timezone.now()`` resolution are indistinguishable. On Windows that
        tick is coarse enough (~15 ms) for a create and an immediate retitle
        to collide, which is a test-timing artefact rather than a behaviour a
        reviewer could hit — editing a title and re-rendering a page spans
        far more wall clock than one tick.
        """
        import time

        approved = make_thesis('Original', title_embedding=at_cosine(0.5))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        assert analyze_titles([probe])[probe.id].matched_title == 'Original'

        time.sleep(0.05)
        approved.title = 'Renamed'
        approved.save(update_fields=['title', 'updated_at'])

        assert analyze_titles([probe])[probe.id].matched_title == 'Renamed'

    def test_removing_from_the_corpus_invalidates_the_cache(self, make_thesis):
        approved = make_thesis('Approved', title_embedding=at_cosine(0.9))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        assert analyze_titles([probe])[probe.id].corpus_size == 1

        approved.status = ThesisStatus.REJECTED
        approved.save(update_fields=['status', 'updated_at'])

        assert analyze_titles([probe])[probe.id].corpus_size == 0

    def test_invalidate_cache_forces_a_rebuild(self, make_thesis, django_assert_num_queries):
        make_thesis('Approved', title_embedding=at_cosine(0.5))
        probe = make_thesis('Probe', title_embedding=basis(0),
                            status=ThesisStatus.PENDING_REVIEW)

        analyze_titles([probe])
        invalidate_cache()

        # Cold again: aggregate + corpus SELECT.
        with django_assert_num_queries(2):
            analyze_titles([probe])
