"""Review-time redundancy analysis over precomputed title embeddings.

Answers one question for a faculty reviewer at the moment of decision: how
closely does this title overlap the already-approved corpus?

Design constraints
------------------
* **Never encodes text.** This module deliberately has no import edge to
  ``semantic_search``. That absence is the structural guarantee that
  rendering an admin page cannot trigger a synchronous 90 MB SBERT model
  load. A missing ``title_embedding`` is a data-quality problem to be fixed
  by ``manage.py embed_theses --titles-only``, not papered over at render
  time.
* **One matrix multiplication per call.** ``analyze_titles`` takes the whole
  rendered page and computes every probe-to-corpus similarity as a single
  ``P @ M.T``. Encoding K titles against N approved theses pairwise — the
  shape of ``title_similarity.rank_titles`` — is K x N dot products in Python
  plus K + N model calls. One matmul is a single BLAS call.
* **Thresholds are imported, never redeclared.** ``title_similarity`` owns
  the cut-offs, so this surface and ``classify`` can never disagree on the
  same score.
* **Advisory, not authoritative.** Every failure mode degrades the *signal*
  while leaving the review *decision* fully functional. Nothing here raises.

Public surface
--------------
* ``RedundancyResult``            — frozen result record.
* ``analyze_titles(theses)``      — batch entry point, the only one callers need.
* ``label_for(score)``            — score to label.
* ``advisory_for(label)``         — label to reviewer guidance.
* ``invalidate_cache()``          — drop the cached corpus matrix.
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

# Thresholds live in title_similarity — single source of truth for the
# Chapter 1-3 cut-offs. Importing (rather than restating) is what keeps the
# admin badge and the title-validation endpoint from ever disagreeing.
from .title_similarity import THRESHOLD_HIGH, THRESHOLD_MODERATE

logger = logging.getLogger(__name__)

# Must match semantic_search.EMBEDDING_DIM. Declared locally rather than
# imported so this module keeps zero import edges to semantic_search — see
# the module docstring. The test suite asserts the two stay in step.
EMBEDDING_DIM = 384

# Vectors are L2-normalised at write time, so a norm at or below this is a
# zero vector (embed_text returns one for empty/whitespace titles) and
# carries no direction to compare against.
_MIN_NORM = 1e-6

# Score differences below this are treated as ties and resolved by corpus
# order. Sized to the float32 dot-product noise floor (relative error ~1e-7),
# which is orders of magnitude below anything that could move a score across
# the 0.60 / 0.85 label boundaries.
_TIE_EPSILON = 1e-6

# ── Labels ─────────────────────────────────────────────────────────────────
LABEL_CLEAN = 'Clean'
LABEL_MODERATE = 'Moderate'
LABEL_HIGH = 'High Overlap'
LABEL_UNKNOWN = 'Not computed'

# ── Reason codes (empty string when computed successfully) ─────────────────
REASON_MISSING_EMBEDDING = 'missing_title_embedding'
REASON_DIMENSION_MISMATCH = 'dimension_mismatch'
REASON_MATH_UNAVAILABLE = 'vector_math_unavailable'

_ADVISORIES = {
    LABEL_HIGH: (
        'Very close to an existing approved thesis. Compare scope, '
        'methodology, and target users before approving.'
    ),
    LABEL_MODERATE: (
        'Shares substantial wording with an existing thesis. May still be '
        'acceptable if the scope or implementation differ.'
    ),
    LABEL_CLEAN: (
        'No substantial title overlap with the approved corpus.'
    ),
    LABEL_UNKNOWN: (
        'Similarity could not be measured for this record.'
    ),
}


@dataclass(frozen=True)
class RedundancyResult:
    """Outcome of measuring one thesis against the approved corpus.

    ``computed`` answers "could we measure?", not "was there anything to
    measure against". An empty approved corpus yields ``computed=True`` with
    ``score=0.0`` — a real measurement of zero overlap. ``corpus_size`` is
    what stops a green badge over an empty repository from being misread as a
    clean bill of health.
    """

    thesis_id: UUID
    computed: bool
    score: float = 0.0
    label: str = LABEL_UNKNOWN
    matched_thesis_id: Optional[UUID] = None
    matched_title: str = ''
    corpus_size: int = 0
    reason: str = ''


# ---------------------------------------------------------------------------
# Score to label
# ---------------------------------------------------------------------------

def label_for(score: float) -> str:
    """Map a cosine score to a redundancy label.

    Both bounds are inclusive-lower, mirroring ``title_similarity.classify``:
    exactly 0.60 is Moderate, exactly 0.85 is High Overlap.
    """
    if score >= THRESHOLD_HIGH:
        return LABEL_HIGH
    if score >= THRESHOLD_MODERATE:
        return LABEL_MODERATE
    return LABEL_CLEAN


def advisory_for(label: str) -> str:
    """Return reviewer guidance for ``label``.

    Phrased as guidance, never as a verdict — the reviewer decides.
    """
    return _ADVISORIES.get(label, _ADVISORIES[LABEL_UNKNOWN])


# ---------------------------------------------------------------------------
# Vector validation
# ---------------------------------------------------------------------------

def _classify_vector(raw) -> Tuple[Optional[List[float]], str]:
    """Validate a stored ``title_embedding``.

    Returns ``(vector, '')`` when usable, or ``(None, reason_code)``.

    A usable embedding is a list of exactly ``EMBEDDING_DIM`` finite numbers
    whose L2 norm is at least ``_MIN_NORM``. The length check runs first so a
    wrong-dimension vector reports ``dimension_mismatch`` rather than being
    lumped in with absent ones.
    """
    if raw is None or not isinstance(raw, (list, tuple)) or len(raw) == 0:
        return None, REASON_MISSING_EMBEDDING

    if len(raw) != EMBEDDING_DIM:
        return None, REASON_DIMENSION_MISMATCH

    # Element-level checks only after the length check.
    try:
        vector = [float(x) for x in raw]
    except (TypeError, ValueError):
        return None, REASON_MISSING_EMBEDDING

    if any(math.isnan(x) or math.isinf(x) for x in vector):
        return None, REASON_MISSING_EMBEDDING

    norm = math.sqrt(sum(x * x for x in vector))
    if norm < _MIN_NORM:
        # embed_text returns an all-zero vector for an empty or
        # whitespace-only title. There is no direction to compare.
        return None, REASON_MISSING_EMBEDDING

    return vector, ''


def _not_computed(thesis_id: UUID, reason: str) -> RedundancyResult:
    return RedundancyResult(
        thesis_id=thesis_id,
        computed=False,
        score=0.0,
        label=LABEL_UNKNOWN,
        matched_thesis_id=None,
        matched_title='',
        corpus_size=0,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Approved-corpus matrix cache
# ---------------------------------------------------------------------------
# Process-local, like the SBERT model cache in semantic_search._get_model.
# Each worker builds its own copy on first use. There is no cross-process
# coherence problem because the key is re-derived from the database on every
# call — a stale process is only ever one aggregate query away from noticing.

_CacheKey = Tuple[int, Optional[datetime]]

_cache_lock = threading.Lock()
_cache_key: Optional[_CacheKey] = None
_cache_ids: List[UUID] = []
_cache_titles: List[str] = []
_cache_matrix = None  # numpy.ndarray (N, EMBEDDING_DIM) float32


def invalidate_cache() -> None:
    """Drop the cached corpus matrix for this process.

    A test seam and an ops escape hatch. Not needed in normal operation: the
    cache key is derived from the database on every call.
    """
    global _cache_key, _cache_ids, _cache_titles, _cache_matrix
    with _cache_lock:
        _cache_key = None
        _cache_ids = []
        _cache_titles = []
        _cache_matrix = None


def _derive_cache_key() -> _CacheKey:
    """Identify the approved corpus with one aggregate query.

    ``updated_at`` is ``auto_now``, so any save to an approved thesis —
    including a title edit that changes its embedding — advances the maximum
    and invalidates the key. Any insert or delete changes the count.

    Accepted limitation: a delete plus an insert that leave both the count and
    the maximum unchanged yields an unchanged key. ``auto_now`` makes that
    effectively unreachable, and ``invalidate_cache()`` covers it explicitly.
    """
    from django.db.models import Count, Max

    from theses.models import Thesis, ThesisStatus

    agg = (
        Thesis.objects
        .filter(status=ThesisStatus.APPROVED, title_embedding__isnull=False)
        .aggregate(n=Count('id'), latest=Max('updated_at'))
    )
    return (agg['n'] or 0, agg['latest'])


def _load_corpus(np):
    """Return ``(ids, titles, matrix)`` for the approved corpus, cached.

    Rows are ordered by ``('created_at', 'id')``. That deterministic ordering
    is what makes ``argmax`` tie-breaking stable, which in turn is what makes
    batch and single-probe analysis produce identical results.

    Rows whose stored vector is unusable are dropped from the matrix
    entirely, so they can never be returned as a match and never inflate
    ``corpus_size``.
    """
    global _cache_key, _cache_ids, _cache_titles, _cache_matrix

    from theses.models import Thesis, ThesisStatus

    key = _derive_cache_key()

    with _cache_lock:
        if _cache_key == key and _cache_matrix is not None:
            # Return the snapshot under the lock so a concurrent rebuild
            # cannot hand this caller a matrix whose rows and ids came from
            # different loads.
            return _cache_ids, _cache_titles, _cache_matrix

        rows = (
            Thesis.objects
            .filter(status=ThesisStatus.APPROVED, title_embedding__isnull=False)
            .order_by('created_at', 'id')
            .values_list('id', 'title', 'title_embedding')
        )

        ids: List[UUID] = []
        titles: List[str] = []
        vectors: List[List[float]] = []
        for thesis_id, title, raw in rows:
            vector, _reason = _classify_vector(raw)
            if vector is None:
                continue
            ids.append(thesis_id)
            titles.append(title or '')
            vectors.append(vector)

        matrix = (
            np.asarray(vectors, dtype=np.float32)
            if vectors
            else np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        )

        _cache_key = key
        _cache_ids = ids
        _cache_titles = titles
        _cache_matrix = matrix
        return ids, titles, matrix


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------

def analyze_titles(theses: Iterable) -> dict:
    """Measure each thesis in ``theses`` against the approved corpus.

    Args:
        theses: Iterable of ``Thesis`` instances. May be a paginated
                changelist page, a single object, or unsaved instances.
                Only ``id`` and ``title_embedding`` are read.

    Returns:
        ``dict[UUID, RedundancyResult]`` with exactly one entry per distinct
        probe id, so callers can index without a ``KeyError`` guard.

    Never writes, never encodes text, never raises.
    """
    probes = list(theses)
    if not probes:
        return {}

    results: dict = {}
    usable: List[Tuple[UUID, List[float]]] = []
    seen: set = set()

    # ── Phase 1: partition probes by embedding usability ────────────────
    for thesis in probes:
        thesis_id = getattr(thesis, 'id', None)
        if thesis_id in seen:
            continue
        seen.add(thesis_id)

        vector, reason = _classify_vector(getattr(thesis, 'title_embedding', None))
        if vector is None:
            results[thesis_id] = _not_computed(thesis_id, reason)
        else:
            usable.append((thesis_id, vector))

    if not usable:
        return results

    # ── Phase 2: load the approved corpus ────────────────────────────────
    try:
        import numpy as np
        ids, titles, matrix = _load_corpus(np)
    except Exception as exc:
        logger.warning('Redundancy analysis unavailable: %s', exc)
        for thesis_id, _vector in usable:
            results[thesis_id] = _not_computed(thesis_id, REASON_MATH_UNAVAILABLE)
        return results

    corpus_n = len(ids)
    if corpus_n == 0:
        # Nothing to compare against. That is a real measurement of zero
        # overlap, not a failure to measure.
        for thesis_id, _vector in usable:
            results[thesis_id] = RedundancyResult(
                thesis_id=thesis_id,
                computed=True,
                score=0.0,
                label=LABEL_CLEAN,
                matched_thesis_id=None,
                matched_title='',
                corpus_size=0,
                reason='',
            )
        return results

    # ── Phase 3: one matrix multiplication for the whole batch ───────────
    try:
        probe_matrix = np.asarray([v for _id, v in usable], dtype=np.float32)
        # Both sides are L2-normalised, so cosine == dot product.
        scores = probe_matrix @ matrix.T          # (K, N) — the only matmul
    except Exception as exc:
        logger.warning('Redundancy matmul failed: %s', exc)
        for thesis_id, _vector in usable:
            results[thesis_id] = _not_computed(thesis_id, REASON_MATH_UNAVAILABLE)
        return results

    column_of = {thesis_id: index for index, thesis_id in enumerate(ids)}

    # ── Phase 4: exclude each probe from matching itself, by id ──────────
    for row, (thesis_id, _vector) in enumerate(usable):
        own_column = column_of.get(thesis_id)
        if own_column is not None:
            scores[row, own_column] = -np.inf

    # ── Phase 5: reduce, clamp, label ────────────────────────────────────
    for row, (thesis_id, _vector) in enumerate(usable):
        effective_n = corpus_n - (1 if thesis_id in column_of else 0)

        if effective_n == 0:
            # The corpus contains only this thesis.
            results[thesis_id] = RedundancyResult(
                thesis_id=thesis_id,
                computed=True,
                score=0.0,
                label=LABEL_CLEAN,
                matched_thesis_id=None,
                matched_title='',
                corpus_size=0,
                reason='',
            )
            continue

        # Resolve the best match by corpus order, not by float noise.
        #
        # np.argmax alone is not enough. A (K, 384) @ (384, N) product and a
        # (1, 384) @ (384, N) product take different BLAS paths, so the same
        # probe can score the same corpus row differently in the last bits
        # (~1e-8 observed). When two approved theses are near-tied, plain
        # argmax then names whichever one won the rounding — meaning the
        # changelist badge and the change-form panel could cite different
        # "closest matches" for the same thesis.
        #
        # Treating anything within the float32 noise floor as a tie and
        # taking the earliest corpus row makes the choice depend only on the
        # deterministic ('created_at', 'id') ordering.
        row_scores = scores[row]
        best_value = float(np.max(row_scores))
        tied = np.nonzero(row_scores >= best_value - _TIE_EPSILON)[0]
        best = int(tied[0])

        score = float(row_scores[best])
        score = max(-1.0, min(1.0, score))       # clamp numerical noise

        results[thesis_id] = RedundancyResult(
            thesis_id=thesis_id,
            computed=True,
            score=score,
            label=label_for(score),
            matched_thesis_id=ids[best],
            matched_title=titles[best],
            corpus_size=effective_n,
            reason='',
        )

    return results
