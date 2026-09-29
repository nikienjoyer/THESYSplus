"""Title Similarity Validation service — Phase 2B.

Implements the approved THESYS+ AI architecture for proposal validation:

* Sentence-BERT (``all-MiniLM-L6-v2``) — reused from Phase 2A.
* Cosine similarity — dot product on L2-normalised embeddings.
* Threshold-based classification (Chapter 1–3):
    - Highly Similar:        score >= 0.85
    - Moderately Similar:    0.60 <= score < 0.85
    - Low Similarity:        0.35 <= score < 0.60
* Relevance floor: a thesis title scoring below 0.35 is not a meaningful
  match. It is dropped from ``matches``; if nothing reaches the floor the
  result carries ``has_meaningful_match = False`` and a neutral message.

Design notes
------------
* For *title-vs-title* validation we compare a candidate title against
  each thesis's **title only**. Using the full title+abstract+text
  composite (Phase 2A search) would inflate the candidate's score against
  any thesis whose abstract simply mentions related concepts, producing
  false-positive duplicate flags.
* Stored title embeddings are reused when they match the current title and
  model; only missing or stale vectors are encoded on the request path.
* Public surface is intentionally minimal:
    - ``CLASS_HIGH``, ``CLASS_MODERATE``, ``CLASS_LOW`` — classification labels
    - ``THRESHOLD_HIGH``, ``THRESHOLD_MODERATE`` — score cut-offs
    - ``THRESHOLD_MEANINGFUL`` — minimum score for a displayed match
    - ``classify(score) -> str``
    - ``recommendation_for(class_label) -> str``
    - ``rank_titles(candidate, queryset, top_k) -> List[ScoredThesis]``
    - ``classify_title(candidate, queryset) -> TitleClassificationResult``

Exact title / name matches (``title_match.py``) are surfaced even below the
relevance floor, ahead of the semantic matches. They never change the
similarity score or the risk classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

# Reuse SBERT primitives from the semantic search service — single source
# of truth for the model load + embedding generation.
from .semantic_search import EMBEDDING_DIM, ScoredThesis, embed_text, title_source_hash
from .title_match import build_title_matcher
from common.performance import timed_stage


# ---------------------------------------------------------------------------
# Classification thresholds (Chapter 1–3)
# ---------------------------------------------------------------------------

THRESHOLD_HIGH = 0.85       # >= this → HIGHLY_SIMILAR
THRESHOLD_MODERATE = 0.60   # >= this → MODERATELY_SIMILAR; below → LOW_SIMILARITY
# Relevance floor. Below this a title comparison is noise, not a match:
# unrelated text such as "hello hi my name is Valerie" scores ~0.23
# against the approved corpus. Inclusive — a score of exactly 0.35 counts.
THRESHOLD_MEANINGFUL = 0.35

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

# Shown when no thesis title reaches THRESHOLD_MEANINGFUL. Deliberately
# neutral: a low score against everything says nothing about whether the
# input is a valid, original, or suitable thesis title.
NO_MEANINGFUL_MATCH_RECOMMENDATION = (
    'No existing thesis title reached the minimum similarity for a '
    'meaningful comparison. This result does not confirm that the text is '
    'a suitable or original thesis title.'
)

# Shown instead of the "sufficiently distinct" message when the proposed text
# is an exact title/name match for an existing thesis but scores LOW
# semantically (a short name scores far below the long title that carries it).
TITLE_NAME_MATCH_RECOMMENDATION = (
    'An existing thesis already uses this name or title. '
    'Review it before proceeding.'
)


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
    similarity_score: float            # raw max similarity across the corpus
    recommendation: str
    matches: List[ScoredThesis] = field(default_factory=list)  # >= floor only
    has_meaningful_match: bool = False


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

    with timed_stage('title_query_encode'):
        candidate_vec = np.asarray(embed_text(candidate), dtype=np.float32)

    scored: List[ScoredThesis] = []
    with timed_stage('title_corpus_rank'):
        for thesis in queryset:
            title = (getattr(thesis, 'title', '') or '').strip()
            if not title:
                continue
            raw = getattr(thesis, 'title_embedding', None)
            stored_hash = getattr(thesis, 'title_embedding_source_hash', '')
            if stored_hash == title_source_hash(getattr(thesis, 'title', '') or ''):
                try:
                    title_vec = np.asarray(raw, dtype=np.float32)
                    if (title_vec.shape != (EMBEDDING_DIM,)
                            or not np.isfinite(title_vec).all()
                            or float(np.linalg.norm(title_vec)) < 1e-6):
                        raise ValueError('unusable title vector')
                except (TypeError, ValueError):
                    title_vec = np.asarray(embed_text(title), dtype=np.float32)
            else:
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
      2. Take the raw top score as the overall similarity_score.
      3. Classify (``classify``) using the Chapter 1–3 thresholds.
      4. Keep the top-K semantic matches scoring >= ``THRESHOLD_MEANINGFUL``,
         plus every exact title/name match from the whole corpus (even below
         the floor). Title matches come first, then semantic matches; the
         list is deduplicated and capped at ``top_k``.
      5. Attach the recommendation: the title-name message when a title match
         exists and the class is LOW, otherwise the class message, or the
         neutral no-match message when nothing survives.

    An empty corpus (or candidate too short) yields an empty result with
    classification = LOW_SIMILARITY, similarity_score = 0.0 and
    has_meaningful_match = False.
    """
    candidate = (candidate or '').strip()
    corpus = list(queryset)
    all_ranked = rank_titles(candidate, corpus, top_k=None)
    top_score = all_ranked[0].score if all_ranked else 0.0
    label = classify(top_score)

    # A title match may rank outside the semantic top-K, so scan the whole
    # ranked corpus. ``all_ranked`` is score-descending, so title matches
    # keep highest-score-first order.
    matcher = build_title_matcher(candidate, [t.title for t in corpus])
    title_matches = []
    for s in all_ranked:
        if matcher.matches(s.thesis.title):
            s.title_match = True
            title_matches.append(s)

    # Compare at the API's 4-dp precision: float32 dot products land a
    # hair under the floor (0.35 → 0.3499999) while displaying as 35.0%.
    semantic = [
        s for s in all_ranked[:top_k]
        if round(s.score, 4) >= THRESHOLD_MEANINGFUL and not s.title_match
    ]
    matches = (title_matches + semantic)[:top_k]
    has_match = bool(matches)
    if not has_match:
        recommendation = NO_MEANINGFUL_MATCH_RECOMMENDATION
    elif title_matches and label == CLASS_LOW:
        recommendation = TITLE_NAME_MATCH_RECOMMENDATION
    else:
        recommendation = recommendation_for(label)
    return TitleClassificationResult(
        query=candidate,
        classification=label,
        similarity_score=top_score,
        recommendation=recommendation,
        matches=matches,
        has_meaningful_match=has_match,
    )
