"""Topic Trend Analysis service — Phase 3.

Implements the approved THESYS+ Chapter 1–3 architecture:

* **TF-IDF** (``sklearn.feature_extraction.text.TfidfVectorizer``)
  Vectorises each thesis's combined text (title + abstract +
  keywords) and surfaces meaningful, frequently occurring research
  keywords across the corpus. The full ``extracted_text`` is NOT part
  of the corpus — see ``_compose_thesis_text`` for why.

* **K-Means clustering** (``sklearn.cluster.KMeans``)
  Groups TF-IDF vectors into ``k`` topic clusters. ``k`` targets
  ~``6`` theses per cluster, clamped to ``5–8``; corpora smaller than
  ``5`` use one cluster per thesis. See ``_choose_k``.

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

# Target cluster density: k is sized to aim for roughly this many theses per
# cluster before the [K_MIN, K_MAX] clamp applies. See _choose_k.
TARGET_DOCS_PER_CLUSTER = 6

# Cluster labels used when no rule and no author keyword can name the cluster.
# These strings are user-visible — they reach the public landing page.
LABEL_OTHER = 'Other / Mixed Topics'
LABEL_GENERAL = 'General Research'


# ---------------------------------------------------------------------------
# Heuristic topic naming
# ---------------------------------------------------------------------------
#
# Each rule is (label, keyword_set). Every rule is scored against the
# cluster's top keywords (see ``_label_cluster``) and the highest scorer wins;
# rule ORDER breaks ties, so specific labels (Computer Vision) stay ahead of
# generic ones (AI Systems).
#
# Keep this list small, deterministic, and easy to defend in a thesis
# defense — every rule maps to a domain noun panelists will recognise.
#
# TWO CONSTRAINTS ON ANYTHING ADDED HERE:
#
# 1. A token must NOT be a stop word. sklearn strips stop words before it
#    assembles n-grams, so a stopped token can never be emitted and the rule
#    entry becomes dead code that silently makes the rule mean less than it
#    looks like. ``test_no_rule_token_is_a_stop_word`` enforces this — it
#    caught 'model', 'student', 'students' and 'classroom' already.
# 2. A token must be discriminative. 'learning' was in BOTH 'AI Systems' and
#    'Educational Technology' and is ambiguous between them: in a machine
#    learning paper it means one thing, in an e-learning paper the opposite.
#    Bare 'learning' is therefore in neither set now; 'machine learning' and
#    'deep learning' carry the AI sense explicitly.
#
# Hyphenated tokens stay whole ('web-based', 'e-learning'): the tokenizer's
# character class includes the hyphen, so 'web-based' is one token and is not
# affected by 'based' being a stop word.

_TOPIC_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ('Computer Vision',         frozenset({'recognition', 'vision', 'image', 'cnn', 'detection', 'mediapipe', 'face', 'facial', 'opencv'})),
    ('Natural Language Processing', frozenset({'nlp', 'sentiment', 'language', 'tagalog', 'bert', 'tweets', 'embedding', 'embeddings', 'lstm', 'text'})),
    ('AI Systems',              frozenset({'ai', 'deep', 'machine learning', 'deep learning', 'neural', 'prediction', 'transfer', 'classifier', 'classification'})),
    ('Internet of Things',      frozenset({'iot', 'esp32', 'sensor', 'sensors', 'arduino', 'raspberry', 'mqtt', 'greenhouse'})),
    ('Health Informatics',      frozenset({'health', 'patient', 'patients', 'medical', 'diagnosis', 'retinopathy', 'hypertension', 'diabetic', 'wearable'})),
    ('Educational Technology',  frozenset({'education', 'educational', 'lms', 'mathematics', 'curriculum', 'adaptive', 'game', 'educational game', 'gamification', 'unity', 'interactive', 'quiz', 'flashcards', 'module', 'tutorial', 'e-learning'})),
    ('Blockchain Systems',      frozenset({'blockchain', 'hyperledger', 'credential', 'credentials', 'verification', 'decentralized'})),
    ('Mobile Applications',     frozenset({'mobile', 'flutter', 'android', 'ios', 'app'})),
    ('Computer Vision / IoT',   frozenset({'parking', 'yolov5', 'yolo'})),
    ('Web-Based Systems',       frozenset({'web', 'web-based', 'website', 'inventory', 'management', 'monitoring', 'tracking', 'laravel', 'django', 'react', 'vue', 'qr', 'cloud', 'aws', 'lambda'})),
    ('Recommendation Systems',  frozenset({'recommendation', 'recommender', 'tfidf', 'tf-idf', 'collaborative', 'filtering', 'similarity'})),
    ('Data Analytics',          frozenset({'analytics', 'analysis', 'forecast', 'forecasting', 'arima', 'visualization', 'data'})),
    ('Accessibility',           frozenset({'sign', 'accessibility', 'disability', 'assistive'})),
)


def _best_rule_label(top_keywords: Sequence[str]) -> str | None:
    """Score every rule against ``top_keywords``; return the best, or None.

    Replaces first-hit matching, which returned on the first rule with ANY
    overlap. That let one coincidental word outvote five relevant ones: a
    cluster of ['game', 'educational', 'educational game', 'interactive',
    'learning', 'unity'] was labelled 'AI Systems' purely because 'learning'
    appeared in that rule set and AI Systems is declared earlier.

    Weighting: ``top_keywords`` arrives sorted by centroid weight, so position
    is meaningful. Rank 1 of 6 scores 6, rank 6 scores 1 — a rule matching the
    cluster's defining term beats a rule matching its sixth-most-important one.

    Matching: each keyword contributes ``{keyword} | set(keyword.split())``, so
    the unigram rule token 'game' matches the bigram keyword 'educational
    game', and the bigram rule token 'machine learning' matches it exactly. A
    keyword scores a given rule at most once however many of its tokens hit,
    so a rule cannot win by listing synonyms.

    Ties: rules are walked in declaration order and the comparison is strict
    ``>``, so the earliest rule holds a tie. Determinism comes free — no
    secondary sort, and no dependence on frozenset iteration order.
    """
    weighted: list[tuple[int, set[str]]] = []
    total = len(top_keywords)
    for index, keyword in enumerate(top_keywords):
        if not keyword:
            continue
        lowered = str(keyword).lower()
        weighted.append((total - index, {lowered} | set(lowered.split())))

    best_label: str | None = None
    best_score = 0
    for label, tokens in _TOPIC_RULES:
        score = sum(
            weight for weight, match_set in weighted if match_set & tokens
        )
        if score > best_score:
            best_score = score
            best_label = label

    return best_label


def _label_cluster(
    top_keywords: Sequence[str],
    member_keywords: Sequence[Sequence[str]] | None = None,
) -> str:
    """Pick a human-readable cluster label.

    Three steps, most trustworthy source first:

    1. ``_TOPIC_RULES`` — a deterministic domain table, scored so the label
       reflects the whole keyword list rather than its luckiest single word.
       See ``_best_rule_label``.
    2. The most common keyword the cluster's own authors chose. A phrase a
       student wrote to describe their thesis ("swarm robotics") is a real
       topic name; it just isn't in the rule table yet.
    3. ``LABEL_OTHER`` — an honest admission.

    A raw TF-IDF term is deliberately NOT a candidate. That used to be
    step 2, and because the vectoriser emits whatever n-gram carries
    statistical weight, the chart ended up with bar labels like "Support",
    "Yielded Overall" and "Ventura Bacolor" — corpus artefacts presented to
    the public landing page as research topics. "Other / Mixed Topics" is
    less informative and much more truthful.

    Args:
        top_keywords: Cluster's top TF-IDF terms, highest weight first.
        member_keywords: One keyword list per thesis in the cluster.
            Optional so existing single-argument callers keep working.
    """
    rule_label = _best_rule_label(top_keywords)
    if rule_label is not None:
        return rule_label

    # Step 2 — the authors' own vocabulary.
    #
    # Counting is done on a lowercased key so "Face Recognition" and
    # "face recognition" are one topic rather than two, while the display
    # form comes from .title() so the label reads consistently regardless of
    # how any individual student capitalised it.
    counts: Counter[str] = Counter()
    for keyword_list in member_keywords or ():
        for keyword in keyword_list or ():
            normalised = str(keyword).strip().lower()
            if normalised:
                counts[normalised] += 1

    if counts:
        # Sort by descending count, then alphabetically. The alphabetical
        # leg is not cosmetic: Counter.most_common breaks ties by insertion
        # order, which follows cluster membership order, so two runs over
        # the same corpus could otherwise disagree on the label.
        winner = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return winner.title()

    if not top_keywords:
        return LABEL_GENERAL
    return LABEL_OTHER


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

    # ── Title-page / approval-sheet boilerplate ────────────────────────
    # Every manuscript in this repository carries the same front matter, so
    # these terms describe the TEMPLATE rather than the research. They were
    # previously ranking high enough to become cluster labels ("Capstone",
    # "Honorio Ventura", "Dhvsu Edu"), which grouped theses by the document
    # format they share instead of the topic they differ on.
    #
    # Institution names, including the university's full legal name and its
    # email domain — the abstract and title page both repeat them.
    'dhvsu', 'honorio', 'ventura', 'don', 'bacolor', 'edu',
    # Degree / submission boilerplate.
    'capstone', 'bachelor', 'degree', 'partial', 'fulfillment',
    'requirements', 'college', 'faculty', 'adviser', 'presented', 'submitted',
})


# ---------------------------------------------------------------------------
# Result data model
# ---------------------------------------------------------------------------

@dataclass
class _DocMeta:
    """Per-document sidecar, parallel to the ``documents`` list by index.

    A dataclass rather than a tuple: this used to be ``(id_str, title)`` and
    is read by index in three places, so a third positional slot would leave
    ``metadata[i][2]`` at the call sites with nothing naming what it holds.

    ``keywords`` is the author's own keyword list, kept separate from the
    TF-IDF terms in ``TopicCluster.keywords``. The two are not
    interchangeable: these are human-chosen phrases ("swarm robotics"),
    those are corpus-derived n-grams.
    """
    id: str
    title: str
    keywords: List[str] = field(default_factory=list)


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

def get_topic_trends_queryset():
    """Single source of truth for the topic-trend-analysis queryset.

    Both ``ThesisTopicTrendsView`` and ``ThesisAnalyticsView`` must feed
    ``analyze_topics()`` with the *exact* same rows in the *exact* same
    order — K-Means clustering (even with a fixed ``random_state``) is
    sensitive to input row order, so two independently-built querysets
    over the identical underlying data can silently produce different
    cluster compositions, and therefore different SATURATED / EMERGING /
    UNDEREXPLORED counts on the two pages. Routing both views through
    this one helper eliminates that drift by construction.

    Ordered by ``created_at`` with ``id`` as a tie-break, since
    ``created_at`` alone is not guaranteed unique (e.g. bulk-seeded rows
    sharing a timestamp), and Django querysets without an explicit
    ``order_by()`` have no guaranteed row order at all.

    Lazy-imports the ``Thesis``/``ThesisStatus`` models (matching this
    module's existing lazy-import style for heavy/app-coupled
    dependencies) to keep this service module import-safe regardless of
    Django app-registry readiness.
    """
    from theses.models import Thesis, ThesisStatus

    return (
        Thesis.objects
        .filter(status=ThesisStatus.APPROVED)
        # ``extracted_text`` is deliberately absent. It is the largest column
        # on the table (a full manuscript per row) and nothing downstream
        # reads it any more — ``_compose_thesis_text`` dropped it, and both
        # callers pass this queryset straight into ``analyze_topics`` without
        # touching rows themselves.
        #
        # Worth stating why that check mattered: a deferred field is not an
        # error to access, it is a silent per-row follow-up query. Removing a
        # column from ``.only()`` while some consumer still reads it would
        # trade one large fetch for N small ones — slower than the problem it
        # was meant to solve, and invisible in tests.
        .only(
            'id', 'title', 'abstract',
            'keywords', 'program', 'year', 'status',
        )
        .order_by('created_at', 'id')
    )


def _compose_thesis_text(thesis) -> str:
    """Combine title + abstract + keywords into the document TF-IDF sees.

    ``extracted_text`` is deliberately EXCLUDED. It used to contribute its
    first 2000 characters, but on this corpus those 2000 characters are the
    cover page and approval sheet — the university's name, the degree
    boilerplate, the adviser's signature block. Every manuscript carries the
    same front matter, so feeding it to TF-IDF clustered theses by the
    template they share rather than the research they differ on, and surfaced
    labels like "Capstone" and "Honorio Ventura".

    The three fields kept here are the ones a student wrote *about their own
    work*: the title, the abstract, and the keywords they chose. That is the
    highest signal-to-noise text available per thesis.
    """
    title = (thesis.title or '').strip()
    abstract = (thesis.abstract or '').strip()
    keywords = thesis.keywords or []
    keyword_str = ' '.join(str(k) for k in keywords)
    parts = [p for p in (title, abstract, keyword_str) if p]
    return '\n\n'.join(parts)


def _choose_k(n_documents: int) -> int:
    """Auto-size k for the K-Means run, targeting ~6 theses per cluster.

    For tiny corpora (< K_MIN) we use n_documents itself so every doc
    is essentially its own cluster — this is intentional: it lets the
    UI still render meaningfully on a freshly seeded repository.

    Above that, k is derived from a target cluster density and then clamped
    into the documented ``[K_MIN, K_MAX]`` band:

        30 docs → 5    48 docs → 8    200 docs → 8 (K_MAX ceiling)

    This replaces ``min(K_MAX, n_documents)``, which claimed to auto-size but
    returned K_MAX for every corpus past 8 documents — so k was a constant in
    practice and the "auto-sized to the corpus" docs were untrue. 200 docs
    still returns 8, but now because K_MAX is a deliberate cap rather than
    because the expression collapsed.
    """
    if n_documents < K_MIN:
        return max(1, n_documents)
    return max(K_MIN, min(K_MAX, n_documents // TARGET_DOCS_PER_CLUSTER))


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
    metadata: List[_DocMeta] = []
    for t in theses:
        text = _compose_thesis_text(t)
        if not text.strip():
            continue
        documents.append(text)
        metadata.append(_DocMeta(
            id=str(t.id),
            title=t.title,
            keywords=[str(k) for k in (t.keywords or []) if str(k).strip()],
        ))

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
        topic = _label_cluster(keywords, member_keywords=[metadata[0].keywords])
        cluster = TopicCluster(
            cluster_id=0,
            topic=topic,
            trend=_classify_trend(1, average_size=1.0, total_theses=1),
            thesis_count=1,
            keywords=keywords,
            sample_titles=[metadata[0].title],
            thesis_ids=[metadata[0].id],
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

        topic = _label_cluster(
            keywords,
            member_keywords=[metadata[i].keywords for i in member_indices],
        )
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

        sample_titles = [metadata[i].title for i in member_indices[:5]]
        thesis_ids = [metadata[i].id for i in member_indices]

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
