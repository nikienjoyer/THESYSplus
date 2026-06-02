"""SBERT semantic search service — Phase 2A.

Implements the approved THESYS+ AI architecture:

* Sentence-BERT (``all-MiniLM-L6-v2``) — 90 MB, 384-dim embeddings,
  CPU-friendly, sufficient for thesis-scale corpora.
* Cosine similarity — dot product on L2-normalised embeddings, computed
  with NumPy. No external vector database, no LangChain, no LLM, no RAG.

Design notes
------------
* The model is loaded **once** per process and cached at the module level
  (``_get_model``). Subsequent calls are zero-cost lookups.
* Embeddings produced by ``embed_text`` are L2-normalised so cosine
  similarity reduces to a plain dot product. This is what
  ``encode(..., normalize_embeddings=True)`` does internally.
* Persisted thesis embeddings are stored as plain JSON lists on the
  ``Thesis.embedding_vector`` column. Loading + ranking happens entirely
  in NumPy — no pgvector dependency. For a larger corpus, the same
  service surface (``embed_text``, ``rank_theses``) can be backed by an
  ANN index without changing callers.

Public surface
--------------
* ``MODEL_NAME``               — canonical model identifier.
* ``EMBEDDING_DIM``            — model output dimension (384).
* ``embed_text(text) -> list`` — produce a normalised embedding.
* ``compose_thesis_text(t)``   — canonical thesis content for embedding.
* ``generate_thesis_embedding(thesis)`` — embed + persist on a Thesis row.
* ``rank_theses(query, qs)``   — semantic ranking with cosine similarity.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from django.utils import timezone

logger = logging.getLogger(__name__)

# Lightweight, CPU-friendly model. 384-dim embeddings.
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_DIM = 384

# Maximum characters of extracted_text included in the embedding input.
# all-MiniLM-L6-v2 caps at 256 word-pieces (~1k chars). We feed a generous
# but bounded slice so abstracts dominate the signal and full thesis text
# does not blow the token budget.
EXTRACTED_TEXT_MAX_CHARS = 2000

# Process-local model cache — loaded lazily on first use, then reused.
_model = None
_model_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------

def _get_model():
    """Return the singleton SBERT model, loading it on first call."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            logger.info('Loading SBERT model: %s', MODEL_NAME)
            _model = SentenceTransformer(MODEL_NAME)
            logger.info('SBERT model ready (dim=%d)', EMBEDDING_DIM)
    return _model


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def embed_text(text: str) -> List[float]:
    """Return an L2-normalised SBERT embedding for ``text`` as a list of floats.

    Args:
        text: Free-form text. Empty strings yield a zero vector.

    Returns:
        ``EMBEDDING_DIM``-length list of floats, L2-normalised so that
        cosine similarity == dot product.
    """
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    # vec is a numpy.ndarray (float32). Convert to plain Python list for JSON.
    return [float(x) for x in vec.tolist()]


def compose_thesis_text(thesis) -> str:
    """Build the canonical text used to embed a Thesis record.

    Combines title + abstract + truncated extracted_text per the
    Phase 2A requirements.
    """
    title = (thesis.title or '').strip()
    abstract = (thesis.abstract or '').strip()
    extracted = (thesis.extracted_text or '').strip()[:EXTRACTED_TEXT_MAX_CHARS]
    parts = [p for p in (title, abstract, extracted) if p]
    return '\n\n'.join(parts)


def generate_thesis_embedding(thesis, *, save: bool = True) -> List[float]:
    """Generate (and optionally persist) an embedding for ``thesis``.

    Args:
        thesis: A ``Thesis`` instance (saved or unsaved).
        save: When True, write the vector + status fields back to the DB
              row using a focused ``update_fields`` save.

    Returns:
        The embedding vector (list of floats).
    """
    # Local import to avoid circular dependency (services/text_extractor
    # already imports from this app, and the orchestrator imports both).
    from theses.models import EmbeddingStatus

    text = compose_thesis_text(thesis)
    try:
        vector = embed_text(text)
        thesis.embedding_vector = vector
        thesis.embedding_status = EmbeddingStatus.READY
        thesis.embedding_model = MODEL_NAME
        thesis.embedding_generated_at = timezone.now()
        if save:
            thesis.save(update_fields=[
                'embedding_vector',
                'embedding_status',
                'embedding_model',
                'embedding_generated_at',
                'updated_at',
            ])
        return vector
    except Exception as exc:
        logger.warning('SBERT embedding failed for thesis %s: %s', thesis.id, exc)
        thesis.embedding_status = EmbeddingStatus.FAILED
        if save:
            thesis.save(update_fields=['embedding_status', 'updated_at'])
        raise


# ---------------------------------------------------------------------------
# Cosine similarity ranking
# ---------------------------------------------------------------------------

@dataclass
class ScoredThesis:
    """A thesis paired with its cosine-similarity score against the query."""

    thesis: 'Thesis'  # type: ignore[name-defined]  (forward ref)
    score: float


def rank_theses(query: str, queryset: Iterable, *, top_k: int | None = None) -> List[ScoredThesis]:
    """Score each thesis in ``queryset`` against ``query`` by cosine similarity.

    Theses without a stored embedding (``embedding_vector is None``) are
    skipped — they cannot be ranked semantically. Callers should
    backfill missing embeddings via ``regenerate_thesis_embeddings``.

    Args:
        query: User query string. Empty queries yield an empty list.
        queryset: Iterable of ``Thesis`` rows. May be a Django QuerySet
                  or a plain list.
        top_k: When provided, return only the top-K highest-scoring results.

    Returns:
        ``List[ScoredThesis]`` sorted by descending score.
    """
    if not query or not query.strip():
        return []

    # Lazy NumPy import — keeps dev startup fast when search isn't used.
    import numpy as np

    query_vec = np.asarray(embed_text(query), dtype=np.float32)

    scored: List[ScoredThesis] = []
    for thesis in queryset:
        vec = thesis.embedding_vector
        if not vec:
            continue
        try:
            doc_vec = np.asarray(vec, dtype=np.float32)
        except (TypeError, ValueError):
            continue
        if doc_vec.shape != query_vec.shape:
            continue
        # Both vectors are L2-normalised → cosine == dot product.
        score = float(np.dot(query_vec, doc_vec))
        # Numerical noise can push scores slightly outside [-1, 1].
        score = max(-1.0, min(1.0, score))
        scored.append(ScoredThesis(thesis=thesis, score=score))

    scored.sort(key=lambda s: s.score, reverse=True)
    if top_k is not None:
        return scored[:top_k]
    return scored
