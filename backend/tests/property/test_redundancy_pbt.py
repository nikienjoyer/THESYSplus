"""Property-based tests for review-time redundancy analysis and the audit trail.

Each test names the property it establishes:

* P1  — batch equals single-probe
* P2  — self-exclusion
* P3  — label monotonicity over score
* P4  — boundary exactness at 0.60 / 0.85, and agreement with title_similarity
* P5  — score domain and the not-computed field contract
* P6  — total coverage (one result per probe, so no KeyError is possible)
* P7  — no live encoding
* P8  — total function over malformed input
* P9  — cache coherence across corpus mutations
* P10 — transition stamping
* P11 — no-op invariance
* P12 — audit-to-transition bijection
* P13 — audit durability
* P14 — output escaping

Vectors are generated as random unit vectors in R^384 so the L2-normalisation
precondition of cosine-as-dot-product holds by construction. No SBERT model is
loaded anywhere in this module.

Marked ``property`` so they can be selected or skipped explicitly.
"""

from __future__ import annotations

import math

import pytest
from django.contrib import admin as django_admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.base import ContentFile
from django.test import RequestFactory
from hypothesis import HealthCheck, assume, given, settings as hyp_settings, strategies as st

from accounts.models import Role, User
from audit.models import AuditLog
from theses.admin import ThesisAdmin
from theses.models import EmbeddingStatus, FileType, Program, Thesis, ThesisStatus
from theses.services.redundancy import (
    EMBEDDING_DIM,
    LABEL_CLEAN,
    LABEL_HIGH,
    LABEL_MODERATE,
    LABEL_UNKNOWN,
    analyze_titles,
    invalidate_cache,
    label_for,
)
from theses.services.title_similarity import (
    CLASS_HIGH,
    CLASS_LOW,
    CLASS_MODERATE,
    THRESHOLD_HIGH,
    THRESHOLD_MODERATE,
    classify,
)

pytestmark = pytest.mark.property

# Database-touching properties need these: pytest-django's db fixture is
# function-scoped, and Hypothesis rightly complains unless told otherwise.
DB_SETTINGS = hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=15,
)

PURE_SETTINGS = hyp_settings(max_examples=400)

REVIEW_EVENT_PREFIX = 'thesis.review.'


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

finite_floats = st.floats(
    min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False,
)

score = finite_floats


# Number of axes a generated vector is supported on. Drawing 384 independent
# floats per vector exhausts Hypothesis's per-example data budget long before
# it finds anything interesting. Any pair of unit vectors inside a 6-dimensional
# subspace can realise any cosine in [-1, 1], so the mathematical coverage is
# unchanged while the entropy cost drops by two orders of magnitude.
_AXES = 6

# width=32 keeps every component exactly representable as float32, which is
# the dtype the corpus matrix uses. Without it, normalising in float64 and
# then casting introduces rounding that has nothing to do with the behaviour
# under test.
axis_coefficient = st.floats(
    min_value=-1.0, max_value=1.0,
    allow_nan=False, allow_infinity=False, width=32,
)


@st.composite
def unit_vector(draw):
    """An L2-normalised vector in R^384, supported on ``_AXES`` axes.

    Rejects near-degenerate vectors: a zero vector has no direction, and the
    analyzer treats it as an absent embedding rather than a comparable point.
    """
    coefficients = draw(
        st.lists(axis_coefficient, min_size=_AXES, max_size=_AXES)
    )
    norm = math.sqrt(sum(c * c for c in coefficients))
    assume(norm > 0.1)

    vector = [0.0] * EMBEDDING_DIM
    for index, coefficient in enumerate(coefficients):
        vector[index] = coefficient / norm
    return vector


# Vectors that are structurally wrong in some way.
malformed_vector = st.one_of(
    st.none(),
    st.just([]),
    st.just('not-a-list'),
    st.just({'nope': 1}),
    st.lists(finite_floats, min_size=1, max_size=10),
    st.lists(finite_floats, min_size=385, max_size=400),
    st.just([0.0] * EMBEDDING_DIM),
    st.just([float('nan')] * EMBEDDING_DIM),
    st.just(['x'] * EMBEDDING_DIM),
)

terminal_status = st.sampled_from([ThesisStatus.APPROVED, ThesisStatus.REJECTED])
any_status = st.sampled_from([
    ThesisStatus.PENDING_REVIEW, ThesisStatus.APPROVED, ThesisStatus.REJECTED,
])

html_metachar_title = st.text(
    alphabet=st.sampled_from(list('<>"\'&{}0abcscript/=() ')),
    min_size=1, max_size=60,
)

# PostgreSQL text columns reject NUL (0x00) outright, and C0 control
# characters are not meaningful thesis titles. min_codepoint=32 excludes both,
# so the strategy explores titles the column can actually hold.
safe_title = st.text(
    alphabet=st.characters(min_codepoint=32, blacklist_categories=('Cs',)),
    min_size=1, max_size=80,
)

# float32 dot products carry ~1e-7 relative error, and batch vs single-probe
# matmuls take different BLAS paths. Scores agree to within the noise floor,
# not bit-exactly.
SCORE_TOLERANCE = 1e-6


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_corpus_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def isolate_media(settings, tmp_path):
    """Keep test uploads out of the real MEDIA_ROOT.

    Matters most here: Hypothesis runs many examples per test function, each
    creating theses with a real file, so an unisolated MEDIA_ROOT accumulates
    thousands of stray PDFs per run.

    Deliberately not autouse — overriding a setting fires ``setting_changed``
    receivers that reach for the database connection, which would drag the
    pure no-DB label properties into needing ``django_db``. The factory that
    writes files depends on it instead.
    """
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email='pbt.uploader@pampangastateu.edu.ph',
        first_name='PBT',
        last_name='Uploader',
        role=Role.STUDENT,
        password='Test12345!Test',
    )


@pytest.fixture
def reviewer(db):
    return User.objects.create_superuser(
        email='pbt.reviewer@pampangastateu.edu.ph',
        first_name='PBT',
        last_name='Reviewer',
        password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db, uploader, isolate_media):
    counter = {'n': 0}

    def _make(
        title: str = 'Thesis',
        *,
        title_embedding=None,
        status: str = ThesisStatus.APPROVED,
        embedding_status: str = EmbeddingStatus.READY,
        save: bool = True,
    ) -> Thesis:
        counter['n'] += 1
        n = counter['n']
        thesis = Thesis(
            title=title,
            abstract='Abstract.',
            authors=['T.'],
            keywords=['k'],
            program=Program.BSIT.value,
            year=2024,
            file_type=FileType.PDF,
            sha256=f'{n:064x}',
            status=status,
            uploaded_by=uploader,
            title_embedding=title_embedding,
            embedding_status=embedding_status,
        )
        thesis.uploaded_file.save(
            f'pbt_{n}.pdf', ContentFile(b'%PDF-1.4\n%x'), save=False,
        )
        if save:
            thesis.save()
        return thesis

    return _make


@pytest.fixture
def model_admin():
    return ThesisAdmin(Thesis, django_admin.site)


@pytest.fixture
def admin_request(reviewer):
    def _make(user=None):
        request = RequestFactory().post('/admin/theses/thesis/x/change/')
        request.user = user or reviewer
        request.session = {}
        request._messages = FallbackStorage(request)
        return request
    return _make


def review_rows():
    return AuditLog.objects.filter(event_type__startswith=REVIEW_EVENT_PREFIX)


def reset_corpus():
    """Give the current Hypothesis example a hermetic database.

    ``@given`` runs many examples inside a single test function call, so the
    function-scoped ``db`` fixture rolls back once at the end — not between
    examples. Without this, rows created by example N are still approved and
    embedded during example N+1, which quietly invalidates any assertion of
    the form "the corpus holds exactly what I just created".
    """
    Thesis.objects.all().delete()
    AuditLog.objects.all().delete()
    invalidate_cache()


# ---------------------------------------------------------------------------
# P3 / P4 — pure-function properties over score. No database.
# ---------------------------------------------------------------------------

_SEVERITY = {LABEL_CLEAN: 0, LABEL_MODERATE: 1, LABEL_HIGH: 2}


class TestLabelMapping:
    """P3, P4 — monotonicity and boundary exactness."""

    @PURE_SETTINGS
    @given(a=score, b=score)
    def test_p3_monotonic_in_score(self, a, b):
        """A higher score can never produce a less severe label."""
        low, high = min(a, b), max(a, b)
        assert _SEVERITY[label_for(low)] <= _SEVERITY[label_for(high)]

    @PURE_SETTINGS
    @given(s=score)
    def test_p3_label_is_always_one_of_three(self, s):
        assert label_for(s) in _SEVERITY

    @PURE_SETTINGS
    @given(s=score)
    def test_p4_agrees_with_title_similarity(self, s):
        """The badge and the validate-title endpoint must never disagree."""
        equivalent = {
            LABEL_HIGH: CLASS_HIGH,
            LABEL_MODERATE: CLASS_MODERATE,
            LABEL_CLEAN: CLASS_LOW,
        }
        assert equivalent[label_for(s)] == classify(s)

    def test_p4_exact_boundaries_are_inclusive_lower(self):
        assert label_for(THRESHOLD_MODERATE) == LABEL_MODERATE
        assert label_for(THRESHOLD_HIGH) == LABEL_HIGH

    @PURE_SETTINGS
    @given(epsilon=st.floats(min_value=1e-9, max_value=0.05,
                            allow_nan=False, allow_infinity=False))
    def test_p4_just_below_each_boundary_drops_a_band(self, epsilon):
        assert label_for(THRESHOLD_MODERATE - epsilon) == LABEL_CLEAN
        assert label_for(THRESHOLD_HIGH - epsilon) == LABEL_MODERATE


# ---------------------------------------------------------------------------
# P5, P6, P8 — result contract and totality
# ---------------------------------------------------------------------------

class TestResultContract:
    """P5, P6, P8."""

    @DB_SETTINGS
    @given(vectors=st.lists(unit_vector(), min_size=1, max_size=6))
    def test_p6_every_probe_gets_exactly_one_result(self, make_thesis, vectors):
        reset_corpus()
        probes = [make_thesis(f'P{i}', title_embedding=v)
                  for i, v in enumerate(vectors)]

        results = analyze_titles(probes)

        assert set(results) == {p.id for p in probes}
        assert len(results) == len(probes)

    @DB_SETTINGS
    @given(vectors=st.lists(unit_vector(), min_size=1, max_size=5))
    def test_p5_computed_results_stay_in_the_unit_interval(self, make_thesis, vectors):
        reset_corpus()
        probes = [make_thesis(f'P{i}', title_embedding=v)
                  for i, v in enumerate(vectors)]

        for result in analyze_titles(probes).values():
            if result.computed:
                assert -1.0 <= result.score <= 1.0
                assert result.label == label_for(result.score)
                assert result.reason == ''

    @DB_SETTINGS
    @given(bad=malformed_vector)
    def test_p5_not_computed_contract(self, make_thesis, bad):
        reset_corpus()
        probe = make_thesis('Bad', title_embedding=bad, save=False)

        result = analyze_titles([probe])[probe.id]

        assert result.computed is False
        assert result.score == 0.0
        assert result.label == LABEL_UNKNOWN
        assert result.matched_thesis_id is None
        assert result.matched_title == ''
        assert result.corpus_size == 0
        assert result.reason != ''

    @DB_SETTINGS
    @given(bad_vectors=st.lists(malformed_vector, min_size=1, max_size=6))
    def test_p8_total_function_over_malformed_input(self, make_thesis, bad_vectors):
        reset_corpus()
        probes = [make_thesis(f'B{i}', title_embedding=v, save=False)
                  for i, v in enumerate(bad_vectors)]

        results = analyze_titles(probes)          # must not raise

        assert set(results) == {p.id for p in probes}


# ---------------------------------------------------------------------------
# P1, P2 — batch equivalence and self-exclusion
# ---------------------------------------------------------------------------

class TestBatchAndSelfExclusion:
    """P1, P2."""

    @DB_SETTINGS
    @given(
        corpus=st.lists(unit_vector(), min_size=1, max_size=5),
        probes=st.lists(unit_vector(), min_size=1, max_size=4),
    )
    def test_p1_batch_equals_single(self, make_thesis, corpus, probes):
        reset_corpus()
        for i, v in enumerate(corpus):
            make_thesis(f'C{i}', title_embedding=v, status=ThesisStatus.APPROVED)
        probe_rows = [
            make_thesis(f'P{i}', title_embedding=v,
                        status=ThesisStatus.PENDING_REVIEW)
            for i, v in enumerate(probes)
        ]

        batch = analyze_titles(probe_rows)

        for probe in probe_rows:
            single = analyze_titles([probe])[probe.id]
            assert batch[probe.id].computed == single.computed
            assert batch[probe.id].score == pytest.approx(
                single.score, abs=SCORE_TOLERANCE,
            )
            assert batch[probe.id].label == single.label
            assert batch[probe.id].corpus_size == single.corpus_size
            # The named match must agree too — that is what stops the
            # changelist badge and the change form citing different theses.
            assert batch[probe.id].matched_thesis_id == single.matched_thesis_id

    @DB_SETTINGS
    @given(vectors=st.lists(unit_vector(), min_size=2, max_size=6))
    def test_p2_no_thesis_is_ever_its_own_match(self, make_thesis, vectors):
        """Holds even when the probe is approved and sits at cosine 1.0."""
        reset_corpus()
        rows = [make_thesis(f'A{i}', title_embedding=v,
                            status=ThesisStatus.APPROVED)
                for i, v in enumerate(vectors)]

        results = analyze_titles(rows)

        for row in rows:
            assert results[row.id].matched_thesis_id != row.id

    @DB_SETTINGS
    @given(vector=unit_vector())
    def test_p2_duplicate_vectors_still_exclude_self(self, make_thesis, vector):
        """Two approved rows with identical vectors must match each other."""
        reset_corpus()
        a = make_thesis('A', title_embedding=list(vector))
        b = make_thesis('B', title_embedding=list(vector))

        results = analyze_titles([a, b])

        assert results[a.id].matched_thesis_id == b.id
        assert results[b.id].matched_thesis_id == a.id


# ---------------------------------------------------------------------------
# P7 — no live encoding
# ---------------------------------------------------------------------------

class TestNoLiveEncoding:
    """P7."""

    @DB_SETTINGS
    @given(vectors=st.lists(unit_vector(), min_size=1, max_size=4))
    def test_p7_embed_text_is_never_called(self, make_thesis, monkeypatch, vectors):
        reset_corpus()
        from theses.services import semantic_search

        def explode(*args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError('the render path must not encode text')

        monkeypatch.setattr(semantic_search, 'embed_text', explode)

        probes = [make_thesis(f'P{i}', title_embedding=v)
                  for i, v in enumerate(vectors)]

        results = analyze_titles(probes)          # must not raise
        assert len(results) == len(probes)


# ---------------------------------------------------------------------------
# P9 — cache coherence
# ---------------------------------------------------------------------------

class TestCacheCoherence:
    """P9."""

    @DB_SETTINGS
    @given(
        initial=st.lists(unit_vector(), min_size=1, max_size=4),
        added=unit_vector(),
        probe_vector=unit_vector(),
    )
    def test_p9_adding_to_the_corpus_is_reflected(
        self, make_thesis, initial, added, probe_vector,
    ):
        reset_corpus()
        for i, v in enumerate(initial):
            make_thesis(f'C{i}', title_embedding=v)
        probe = make_thesis('Probe', title_embedding=probe_vector,
                            status=ThesisStatus.PENDING_REVIEW)

        before = analyze_titles([probe])[probe.id]
        assert before.corpus_size == len(initial)

        make_thesis('Added', title_embedding=added)
        after = analyze_titles([probe])[probe.id]

        assert after.corpus_size == len(initial) + 1

    @DB_SETTINGS
    @given(
        corpus=st.lists(unit_vector(), min_size=1, max_size=4),
        probe_vector=unit_vector(),
    )
    def test_p9_unapproving_is_reflected(self, make_thesis, corpus, probe_vector):
        reset_corpus()
        rows = [make_thesis(f'C{i}', title_embedding=v)
                for i, v in enumerate(corpus)]
        probe = make_thesis('Probe', title_embedding=probe_vector,
                            status=ThesisStatus.PENDING_REVIEW)

        assert analyze_titles([probe])[probe.id].corpus_size == len(rows)

        rows[0].status = ThesisStatus.REJECTED
        rows[0].save(update_fields=['status', 'updated_at'])

        assert analyze_titles([probe])[probe.id].corpus_size == len(rows) - 1


# ---------------------------------------------------------------------------
# P10, P11, P12, P13 — review provenance and audit
# ---------------------------------------------------------------------------

class TestReviewProvenance:
    """P10, P11, P12, P13."""

    @DB_SETTINGS
    @given(previous=any_status, new=terminal_status)
    def test_p10_terminal_transition_stamps(
        self, model_admin, admin_request, make_thesis, reviewer, previous, new,
    ):
        assume(previous != new)
        thesis = make_thesis('T', status=previous)

        thesis.status = new
        model_admin.save_model(admin_request(), thesis, None, True)

        thesis.refresh_from_db()
        assert thesis.reviewed_by == reviewer
        assert thesis.reviewed_at is not None

    @DB_SETTINGS
    @given(previous=terminal_status)
    def test_p10_reopening_clears(
        self, model_admin, admin_request, make_thesis, previous,
    ):
        from django.utils import timezone

        thesis = make_thesis('T', status=previous)
        Thesis.objects.filter(pk=thesis.pk).update(
            reviewed_at=timezone.now(),
        )
        thesis.refresh_from_db()

        thesis.status = ThesisStatus.PENDING_REVIEW
        model_admin.save_model(admin_request(), thesis, None, True)

        thesis.refresh_from_db()
        assert thesis.reviewed_by is None
        assert thesis.reviewed_at is None

    @DB_SETTINGS
    @given(status=any_status, new_title=safe_title)
    def test_p11_no_op_save_changes_nothing_reviewable(
        self, model_admin, admin_request, make_thesis, status, new_title,
    ):
        thesis = make_thesis('Original', status=status)
        before = (thesis.reviewed_by_id, thesis.reviewed_at)
        audit_before = review_rows().count()

        thesis.title = new_title
        model_admin.save_model(admin_request(), thesis, None, True)

        thesis.refresh_from_db()
        assert (thesis.reviewed_by_id, thesis.reviewed_at) == before
        assert review_rows().count() == audit_before

    @DB_SETTINGS
    @given(sequence=st.lists(any_status, min_size=1, max_size=8))
    def test_p12_one_audit_row_per_real_transition(
        self, model_admin, admin_request, make_thesis, sequence,
    ):
        reset_corpus()
        thesis = make_thesis('Churned', status=ThesisStatus.PENDING_REVIEW)
        request = admin_request()

        expected = 0
        current = ThesisStatus.PENDING_REVIEW
        for target in sequence:
            if target != current:
                expected += 1
            thesis.refresh_from_db()
            thesis.status = target
            model_admin.save_model(request, thesis, None, True)
            current = target

        assert review_rows().count() == expected

    @DB_SETTINGS
    @given(new=terminal_status)
    def test_p13_review_survives_a_failing_audit_write(
        self, model_admin, admin_request, make_thesis, monkeypatch, new,
    ):
        def boom(*args, **kwargs):
            raise RuntimeError('audit unavailable')

        monkeypatch.setattr(AuditLog.objects, 'create', boom)
        thesis = make_thesis('T', status=ThesisStatus.PENDING_REVIEW)

        thesis.status = new
        model_admin.save_model(admin_request(), thesis, None, True)

        thesis.refresh_from_db()
        assert thesis.status == new


# ---------------------------------------------------------------------------
# P14 — output escaping
# ---------------------------------------------------------------------------

class TestOutputEscaping:
    """P14."""

    @DB_SETTINGS
    @given(title=html_metachar_title, vector=unit_vector())
    def test_p14_overlap_badge_emits_no_title_characters(
        self, model_admin, make_thesis, title, vector,
    ):
        reset_corpus()
        probe = make_thesis(title, title_embedding=vector)

        markup = str(model_admin.overlap_badge(probe))

        # The badge renders only the label and a percentage; nothing from the
        # title should reach it at all.
        assert '<script' not in markup.lower()
        assert markup.count('<span') == 1

    @DB_SETTINGS
    @given(matched_title=html_metachar_title, vector=unit_vector())
    def test_p14_panel_escapes_the_matched_title(
        self, model_admin, make_thesis, matched_title, vector,
    ):
        """The panel renders another thesis's title, never typed by this reviewer."""
        reset_corpus()
        make_thesis(matched_title, title_embedding=list(vector),
                    status=ThesisStatus.APPROVED)
        probe = make_thesis('Probe', title_embedding=list(vector),
                            status=ThesisStatus.PENDING_REVIEW)

        markup = str(model_admin.redundancy_analysis(probe))

        # No raw angle bracket or quote may originate from the title.
        for char in ('<script', '</script', 'onmouseover='):
            assert char not in markup.lower()
        # Braces in a title must not break format_html substitution either;
        # reaching this line without an exception is the assertion.
        assert 'Closest approved match' in markup or 'No other approved' in markup
