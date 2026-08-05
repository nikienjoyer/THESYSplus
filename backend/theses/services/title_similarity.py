"""Title Similarity Validation service — Phase 2B.

Implements the approved THESYS+ AI architecture for proposal validation:

* Sentence-BERT (``all-MiniLM-L6-v2``) — reused from Phase 2A.
* Cosine similarity — dot product on L2-normalised embeddings.
* Threshold-based classification (Chapter 1–3):
    - Highly Similar:        score >= 0.85
    - Moderately Similar:    0.60 <= score < 0.85
    - Low Similarity:        score < 0.60

Design notes
------------
* For *title-vs-title* validation we compare a candidate title against
  each thesis's **title only**. Using the full title+abstract+text
  composite (Phase 2A search) would inflate the candidate's score against
  any thesis whose abstract simply mentions related concepts, producing
  false-positive duplicate flags.
* Title embeddings are computed on-the-fly per validation request (the
  corpus is small at demo scale and SBERT title encoding is cheap).
  When the corpus grows, the same surface — ``classify_title()`` — can
  be backed by a precomputed title embedding column without changing
  callers.
* Public surface is intentionally minimal:
    - ``CLASS_HIGH``, ``CLASS_MODERATE``, ``CLASS_LOW`` — classification labels
    - ``THRESHOLD_HIGH``, ``THRESHOLD_MODERATE`` — score cut-offs
    - ``classify(score) -> str``
    - ``recommendation_for(class_label) -> str``
    - ``rank_titles(candidate, queryset, top_k) -> List[ScoredThesis]``
    - ``classify_title(candidate, queryset) -> TitleClassificationResult``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

# Reuse SBERT primitives from the semantic search service — single source
# of truth for the model load + embedding generation.
from .semantic_search import ScoredThesis, embed_text


# ---------------------------------------------------------------------------
# Classification thresholds (Chapter 1–3)
# ---------------------------------------------------------------------------

THRESHOLD_HIGH = 0.85       # >= this → HIGHLY_SIMILAR
THRESHOLD_MODERATE = 0.60   # >= this → MODERATELY_SIMILAR; below → LOW_SIMILARITY

CLASS_HIGH = 'HIGHLY_SIMILAR'
CLASS_MODERATE = 'MODERATELY_SIMILAR'
CLASS_LOW = 'LOW_SIMILARITY'

# Minimum candidate length (in trimmed characters) before we accept a
# request. Two characters is essentially a no-op — block at the service
# boundary, not at the view, so unit tests cover this rule too.
MIN_TITLE_LENGTH = 5


_RECOMMENDATIONS = {
    CLASS_HIGH: (
        'This proposed title appears highly similar to existing studies. '
        'Consider revising the scope, methodology, or target users.'
    ),
    CLASS_MODERATE: (
        'This title shares similarities with existing studies. It may '
        'still be acceptable if the implementation, users, or scope are '
        'sufficiently different.'
    ),
    CLASS_LOW: (
        'This title appears sufficiently distinct from existing thesis '
        'records.'
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(score: float) -> str:
    """Map a cosine score in [-1, 1] to a classification label."""
    if score >= THRESHOLD_HIGH:
        return CLASS_HIGH
    if score >= THRESHOLD_MODERATE:
        return CLASS_MODERATE
    return CLASS_LOW


def recommendation_for(classification: str) -> str:
    """Return the Chapter-defined recommendation message for ``classification``."""
    return _RECOMMENDATIONS.get(classification, _RECOMMENDATIONS[CLASS_LOW])


@dataclass
class TitleClassificationResult:
    """Aggregate result of validating one candidate title."""

    query: str
    classification: str
    similarity_score: float            # max similarity across the corpus
    recommendation: str
    matches: List[ScoredThesis] = field(default_factory=list)


def rank_titles(
    candidate: str,
    queryset: Iterable,
    *,
    top_k: int | None = 5,
) -> List[ScoredThesis]:
    """Score each thesis in ``queryset`` against the candidate **title only**.

    Unlike Phase 2A's ``rank_theses`` which compares against the full
    title+abstract+text composite, this function compares the candidate
    against each thesis's *title* only — the appropriate signal for
    title-similarity / duplicate-detection.

    Args:
        candidate: The proposed thesis title (raw user input).
        queryset: Iterable of ``Thesis`` rows.
        top_k:    Cap on the number of results. ``None`` returns all.

    Returns:
        ``List[ScoredThesis]`` sorted by descending cosine similarity.
    """
    candidate = (candidate or '').strip()
    if len(candidate) < MIN_TITLE_LENGTH:
        return []

    # Lazy NumPy import keeps boot fast.
    import numpy as np

    candidate_vec = np.asarray(embed_text(candidate), dtype=np.float32)

    scored: List[ScoredThesis] = []
    for thesis in queryset:
        title = (getattr(thesis, 'title', '') or '').strip()
        if not title:
            continue
        title_vec = np.asarray(embed_text(title), dtype=np.float32)
        # Both vectors are L2-normalised → cosine == dot product.
        score = float(np.dot(candidate_vec, title_vec))
        score = max(-1.0, min(1.0, score))
        scored.append(ScoredThesis(thesis=thesis, score=score))

    scored.sort(key=lambda s: s.score, reverse=True)
    if top_k is not None:
        return scored[:top_k]
    return scored


def classify_title(
    candidate: str,
    queryset: Iterable,
    *,
    top_k: int = 5,
) -> TitleClassificationResult:
    """Validate ``candidate`` against ``queryset`` and produce the full result.

    Pipeline:
      1. Rank every thesis by cosine similarity of its **title** vs the
         candidate (``rank_titles``).
      2. Take the top score as the overall similarity_score.
      3. Classify (``classify``) using the Chapter 1–3 thresholds.
      4. Attach the recommendation message and top-K matches.

    An empty corpus (or candidate too short) yields an empty result with
    classification = LOW_SIMILARITY and similarity_score = 0.0.
    """
    candidate = (candidate or '').strip()
    matches = rank_titles(candidate, queryset, top_k=top_k)
    top_score = matches[0].score if matches else 0.0
    label = classify(top_score)
    return TitleClassificationResult(
        query=candidate,
        classification=label,
        similarity_score=top_score,
        recommendation=recommendation_for(label),
        matches=matches,
    )
