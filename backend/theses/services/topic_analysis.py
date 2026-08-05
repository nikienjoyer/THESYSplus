"""Topic Trend Analysis service — Phase 3.

Implements the approved THESYS+ Chapter 1–3 architecture:

* **TF-IDF** (``sklearn.feature_extraction.text.TfidfVectorizer``)
  Vectorises each thesis's combined text (title + abstract +
  truncated extracted_text) and surfaces meaningful, frequently
  occurring research keywords across the corpus.

* **K-Means clustering** (``sklearn.cluster.KMeans``)
  Groups TF-IDF vectors into ``k`` topic clusters. ``k`` is auto-sized
  to the corpus (``5–8``, capped at ``n_theses``).

* **Trend classification** based on cluster size:
    - SATURATED      ≥ 5 theses
    - EMERGING       2–4 theses
    - UNDEREXPLORED  1 thesis

* **Heuristic topic naming** uses a deterministic keyword-to-label
  table built from the THESYS+ research domain (AI, IoT, Web, Mobile,
  Health, Education, Blockchain, NLP, Computer Vision, Data Analytics).
  When no rule matches the cluster's top TF-IDF keywords, the label
  falls back to the highest-weight keyword capitalised.

This service is read-only — it never mutates any Thesis row.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Iterable, List, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# How many TF-IDF keywords surface per cluster
KEYWORDS_PER_CLUSTER = 6

# Trend classification thresholds (chapter-defined, simple)
TREND_SATURATED_MIN = 5     # ≥ this → SATURATED
TREND_EMERGING_MIN = 2      # 2..(SATURATED_MIN-1) → EMERGING; below → UNDEREXPLORED

# Dynamic (mean-relative) scaling — used once the corpus is large enough that
# relative cluster sizes carry signal. Below TREND_DYNAMIC_MIN_CORPUS theses
# the static thresholds above are used instead (cold-start fallback).
TREND_DYNAMIC_MIN_CORPUS = 15   # total theses needed to switch to dynamic mode
TREND_SATURATED_FACTOR = 1.5    # ≥ average_size * this → SATURATED
TREND_UNDEREXPLORED_FACTOR = 0.5  # ≤ average_size * this → UNDEREXPLORED

CLASS_SATURATED = 'SATURATED'
CLASS_EMERGING = 'EMERGING'
CLASS_UNDEREXPLORED = 'UNDEREXPLORED'

# k auto-sizing range
K_MIN = 5
K_MAX = 8

# Truncate per-document extracted_text — protects TF-IDF from being dominated
# by huge OCR dumps and keeps the corpus uniform.
EXTRACTED_TEXT_MAX_CHARS = 2000


# ---------------------------------------------------------------------------
# Heuristic topic naming
# ---------------------------------------------------------------------------
#
# Each rule is (priority, label, keyword_set). The first rule whose
# keyword set has at least one hit in the cluster's top-K keywords wins.
# Order is highest-priority first to keep specific labels (Computer
# Vision) ahead of generic ones (AI Systems).
#
# Keep this list small, deterministic, and easy to defend in a thesis
# defense — every rule maps to a domain noun panelists will recognise.

_TOPIC_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ('Computer Vision',         frozenset({'recognition', 'vision', 'image', 'cnn', 'detection', 'mediapipe', 'face', 'facial', 'opencv'})),
    ('Natural Language Processing', frozenset({'nlp', 'sentiment', 'language', 'tagalog', 'bert', 'tweets', 'embedding', 'embeddings', 'lstm', 'text'})),
    ('AI Systems',              frozenset({'ai', 'deep', 'learning', 'neural', 'prediction', 'transfer', 'classifier', 'classification', 'model'})),
    ('Internet of Things',      frozenset({'iot', 'esp32', 'sensor', 'sensors', 'arduino', 'raspberry', 'mqtt', 'greenhouse'})),
    ('Health Informatics',      frozenset({'health', 'patient', 'patients', 'medical', 'diagnosis', 'retinopathy', 'hypertension', 'diabetic', 'wearable'})),
    ('Educational Technology',  frozenset({'education', 'educational', 'learning', 'lms', 'classroom', 'mathematics', 'curriculum', 'student', 'students', 'adaptive'})),
    ('Blockchain Systems',      frozenset({'blockchain', 'hyperledger', 'credential', 'credentials', 'verification', 'decentralized'})),
    ('Mobile Applications',     frozenset({'mobile', 'flutter', 'android', 'ios', 'app'})),
    ('Computer Vision / IoT',   frozenset({'parking', 'yolov5', 'yolo'})),
    ('Web-Based Systems',       frozenset({'web', 'website', 'inventory', 'management', 'tracking', 'laravel', 'django', 'react', 'vue', 'qr', 'cloud', 'aws', 'lambda'})),
    ('Recommendation Systems',  frozenset({'recommendation', 'recommender', 'tfidf', 'tf-idf', 'collaborative', 'filtering', 'similarity'})),
    ('Data Analytics',          frozenset({'analytics', 'analysis', 'forecast', 'forecasting', 'arima', 'visualization', 'data'})),
    ('Accessibility',           frozenset({'sign', 'accessibility', 'disability', 'assistive'})),
)


def _label_cluster(top_keywords: Sequence[str]) -> str:
    """Pick a human-readable cluster label from its top TF-IDF keywords.

    Uses a deterministic keyword-to-label table; falls back to the
    capitalised top keyword if no rule matches.
    """
    if not top_keywords:
        return 'General Research'

    kw_set = {kw.lower() for kw in top_keywords if kw}
    for label, kws in _TOPIC_RULES:
        if kw_set & kws:
            return label

    # Fallback — capitalise the top keyword
    top = top_keywords[0]
    return top.title() if top else 'General Research'


def _classify_trend(thesis_count: int, average_size: float, total_theses: int) -> str:
    """Map a cluster size to a trend classification.

    Two regimes:

    * **Cold-start fallback** (``total_theses < 15``): the corpus is too small
      for relative statistics to be meaningful, so fall back to the original
      fixed thresholds (``>= 5`` SATURATED, ``>= 2`` EMERGING, else
      UNDEREXPLORED).

    * **Dynamic mean-relative scaling** (``total_theses >= 15``): classify each
      cluster against the average cluster size so the model scales with the
      repository:
        - SATURATED      ``thesis_count >= average_size * 1.5``
        - UNDEREXPLORED  ``thesis_count <= average_size * 0.5``
        - EMERGING       everything in between
    """
    # Cold-start fallback — small corpus uses the original static rules
    if total_theses < TREND_DYNAMIC_MIN_CORPUS:
        if thesis_count >= TREND_SATURATED_MIN:
            return CLASS_SATURATED
        if thesis_count >= TREND_EMERGING_MIN:
            return CLASS_EMERGING
        return CLASS_UNDEREXPLORED

    # Dynamic mean-relative scaling for larger corpora
    if thesis_count >= average_size * TREND_SATURATED_FACTOR:
        return CLASS_SATURATED
    if thesis_count <= average_size * TREND_UNDEREXPLORED_FACTOR:
        return CLASS_UNDEREXPLORED
    return CLASS_EMERGING


# ---------------------------------------------------------------------------
# Domain-specific stop words — drop generic thesis-template noise so it
# doesn't dominate TF-IDF rankings on this small corpus
# ---------------------------------------------------------------------------

_EXTRA_STOP_WORDS = frozenset({
    # generic project-doc fluff
    'study', 'studies', 'thesis', 'paper', 'project', 'proposed', 'proposal',
    'system', 'systems', 'application', 'applications', 'using',
    'based', 'model', 'models', 'method', 'methods', 'methodology',
    'real', 'time', 'real-time',
    # very common verbs / connectors
    'used', 'uses', 'use', 'design', 'develop', 'developed', 'developing',
    'analyze', 'analyse', 'evaluate', 'evaluated',
    'pampanga', 'state', 'university', 'psu', 'ccs', 'philippines',
    # very generic nouns
    'students', 'student', 'classroom',
})


# ---------------------------------------------------------------------------
# Result data model
# ---------------------------------------------------------------------------

@dataclass
class TopicCluster:
    cluster_id: int
    topic: str
    trend: str                    # SATURATED / EMERGING / UNDEREXPLORED
    thesis_count: int
    keywords: List[str] = field(default_factory=list)
    sample_titles: List[str] = field(default_factory=list)
    thesis_ids: List[str] = field(default_factory=list)


@dataclass
class TopicTrendsResult:
    total_theses: int
    total_topics: int
    saturated_count: int
    emerging_count: int
    underexplored_count: int
    clusters: List[TopicCluster] = field(default_factory=list)
    # When the corpus is too small for clustering, we still return a
    # well-formed envelope and surface a status string for the UI.
    status: str = 'ok'
    message: str = ''


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _compose_thesis_text(thesis) -> str:
    """Combine title + abstract + truncated extracted_text + keywords."""
    title = (thesis.title or '').strip()
    abstract = (thesis.abstract or '').strip()
    extracted = (thesis.extracted_text or '').strip()[:EXTRACTED_TEXT_MAX_CHARS]
    keywords = thesis.keywords or []
    keyword_str = ' '.join(str(k) for k in keywords)
    parts = [p for p in (title, abstract, extracted, keyword_str) if p]
    return '\n\n'.join(parts)


def _choose_k(n_documents: int) -> int:
    """Auto-size k for the K-Means run.

    For tiny corpora (< K_MIN) we use n_documents itself so every doc
    is essentially its own cluster — this is intentional: it lets the
    UI still render meaningfully on a freshly seeded repository.
    """
    if n_documents < K_MIN:
        return max(1, n_documents)
    return min(K_MAX, n_documents)


def analyze_topics(
    queryset: Iterable,
    *,
    k: int | None = None,
    keywords_per_cluster: int = KEYWORDS_PER_CLUSTER,
    random_state: int = 42,
) -> TopicTrendsResult:
    """Run TF-IDF + K-Means topic analysis over ``queryset``.

    Args:
        queryset: Iterable of Thesis rows. Caller is responsible for
            filtering to APPROVED only.
        k: Override the auto-chosen cluster count.
        keywords_per_cluster: TF-IDF terms surfaced per cluster.
        random_state: Seed for K-Means (reproducible cluster IDs).

    Returns:
        ``TopicTrendsResult`` with overview stats + per-cluster details.
    """
    # ── Materialise corpus and per-doc metadata ────────────────────────
    theses = list(queryset)
    documents: List[str] = []
    metadata: List[tuple[str, str]] = []      # (id_str, title)
    for t in theses:
        text = _compose_thesis_text(t)
        if not text.strip():
            continue
        documents.append(text)
        metadata.append((str(t.id), t.title))

    n_docs = len(documents)

    if n_docs == 0:
        return TopicTrendsResult(
            total_theses=0, total_topics=0,
            saturated_count=0, emerging_count=0, underexplored_count=0,
            status='empty',
            message='No approved theses available for topic analysis yet.',
        )

    # Single document → degenerate "cluster of one"
    if n_docs == 1:
        # Still useful UI: surface its top TF-IDF keywords.
        keywords = _single_doc_keywords(documents[0], keywords_per_cluster)
        topic = _label_cluster(keywords)
        cluster = TopicCluster(
            cluster_id=0,
            topic=topic,
            trend=_classify_trend(1, average_size=1.0, total_theses=1),
            thesis_count=1,
            keywords=keywords,
            sample_titles=[metadata[0][1]],
            thesis_ids=[metadata[0][0]],
        )
        return TopicTrendsResult(
            total_theses=1,
            total_topics=1,
            saturated_count=0,
            emerging_count=0,
            underexplored_count=1,
            clusters=[cluster],
            status='ok',
        )

    # ── TF-IDF vectorisation ───────────────────────────────────────────
    # Lazy imports keep startup fast when the endpoint is never hit.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans

    # min_df must be ≤ n_docs. For tiny corpora (e.g. 2 docs) min_df=1.
    min_df = 1 if n_docs < 5 else 2
    # max_df guards against words appearing in EVERY doc — they carry no
    # discriminative signal. 0.95 is the sklearn default.
    stop_words = list({*_EXTRA_STOP_WORDS, *_load_english_stopwords()})

    vectorizer = TfidfVectorizer(
        lowercase=True,
        token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b',  # alpha tokens, ≥3 chars
        stop_words=stop_words,
        max_df=0.95,
        min_df=min_df,
        ngram_range=(1, 2),         # surface short bigrams ("face recognition")
        sublinear_tf=True,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(documents)
    except ValueError as exc:
        # All-stopword corpus, etc. Surface a clean empty state.
        logger.warning('TF-IDF vectorisation failed: %s', exc)
        return TopicTrendsResult(
            total_theses=n_docs, total_topics=0,
            saturated_count=0, emerging_count=0, underexplored_count=0,
            status='insufficient_text',
            message='Not enough distinctive vocabulary to extract topics.',
        )
    feature_names = vectorizer.get_feature_names_out()

    # ── K-Means clustering ─────────────────────────────────────────────
    chosen_k = k if k is not None else _choose_k(n_docs)
    chosen_k = max(1, min(chosen_k, n_docs))

    kmeans = KMeans(n_clusters=chosen_k, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(tfidf_matrix)
    centroids = kmeans.cluster_centers_

    # ── Build per-cluster summaries ────────────────────────────────────
    clusters: List[TopicCluster] = []
    saturated = emerging = underexplored = 0

    # Group document indices by cluster id
    doc_indices_by_cluster: dict[int, List[int]] = {}
    for doc_idx, lbl in enumerate(labels):
        doc_indices_by_cluster.setdefault(int(lbl), []).append(doc_idx)

    # Sort cluster IDs by descending size so the UI shows biggest first
    sorted_cluster_ids = sorted(
        doc_indices_by_cluster.keys(),
        key=lambda cid: len(doc_indices_by_cluster[cid]),
        reverse=True,
    )

    # Pre-compute corpus-wide context for mean-relative trend scaling.
    # total_theses = sum of all clustered theses; average_size = mean cluster size.
    total_clustered_theses = sum(len(v) for v in doc_indices_by_cluster.values())
    num_clusters = len(sorted_cluster_ids)
    average_cluster_size = (
        total_clustered_theses / num_clusters if num_clusters else 0.0
    )

    for cluster_id in sorted_cluster_ids:
        member_indices = doc_indices_by_cluster[cluster_id]
        thesis_count = len(member_indices)

        # Top-K TF-IDF features by centroid weight
        centroid = centroids[cluster_id]
        top_feature_indices = centroid.argsort()[::-1][: keywords_per_cluster * 3]
        keywords: List[str] = []
        seen_stems: set[str] = set()
        for fi in top_feature_indices:
            term = feature_names[fi]
            stem = re.sub(r's$', '', term).lower()  # cheap dedupe (plural/singular)
            if stem in seen_stems:
                continue
            seen_stems.add(stem)
            keywords.append(term)
            if len(keywords) >= keywords_per_cluster:
                break

        topic = _label_cluster(keywords)
        trend = _classify_trend(
            thesis_count,
            average_size=average_cluster_size,
            total_theses=total_clustered_theses,
        )
        if trend == CLASS_SATURATED:
            saturated += 1
        elif trend == CLASS_EMERGING:
            emerging += 1
        else:
            underexplored += 1

        sample_titles = [metadata[i][1] for i in member_indices[:5]]
        thesis_ids = [metadata[i][0] for i in member_indices]

        clusters.append(TopicCluster(
            cluster_id=int(cluster_id),
            topic=topic,
            trend=trend,
            thesis_count=thesis_count,
            keywords=keywords,
            sample_titles=sample_titles,
            thesis_ids=thesis_ids,
        ))

    return TopicTrendsResult(
        total_theses=n_docs,
        total_topics=len(clusters),
        saturated_count=saturated,
        emerging_count=emerging,
        underexplored_count=underexplored,
        clusters=clusters,
        status='ok',
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_english_stopwords() -> set[str]:
    """Return the sklearn English stopword list (cached after first call)."""
    global _CACHED_STOPWORDS
    try:
        return _CACHED_STOPWORDS  # type: ignore[name-defined]
    except NameError:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        _CACHED_STOPWORDS = set(ENGLISH_STOP_WORDS)
        return _CACHED_STOPWORDS


def _single_doc_keywords(text: str, k: int) -> List[str]:
    """Cheap term-frequency keyword extraction for a single-doc corpus."""
    tokens = re.findall(r'(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b', text.lower())
    stopwords = {*_EXTRA_STOP_WORDS, *_load_english_stopwords()}
    counts = Counter(t for t in tokens if t not in stopwords)
    return [w for w, _ in counts.most_common(k)]


# ---------------------------------------------------------------------------
# Serialisation helper for the API view
# ---------------------------------------------------------------------------

def to_dict(result: TopicTrendsResult) -> dict:
    """JSON-serialisable view of ``result`` for the REST endpoint."""
    return {
        'total_theses': result.total_theses,
        'total_topics': result.total_topics,
        'saturated_count': result.saturated_count,
        'emerging_count': result.emerging_count,
        'underexplored_count': result.underexplored_count,
        'status': result.status,
        'message': result.message,
        'clusters': [asdict(c) for c in result.clusters],
    }
