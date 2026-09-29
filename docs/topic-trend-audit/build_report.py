"""Read-only comparison of the existing TF-IDF/K-Means topic pipeline.

Run from any directory with ``python docs/topic-trend-audit/build_report.py``.
Only the sibling report.md is written. The database transaction is read-only.
This is an audit tool, not a production clustering implementation or test.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thesys.settings")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics import adjusted_rand_score, silhouette_score  # noqa: E402
from sklearn.preprocessing import normalize  # noqa: E402

from theses.services.topic_analysis import (  # noqa: E402
    KEYWORDS_PER_CLUSTER,
    TopicCluster,
    _EXTRA_STOP_WORDS,
    _classify_trend,
    _compose_thesis_text,
    _label_cluster,
    _load_english_stopwords,
    analyze_topics,
    get_topic_trends_queryset,
)


REPORT_PATH = Path(__file__).with_name("report.md")
NOTES_PATH = Path(__file__).with_name("review_notes.md")
K_VALUES = range(5, 13)
SEEDS = (42, *range(11))
# These terms identify delivery format more often than research subject.
# They are removed only from the third, experimental representation.
PLATFORM_TERMS = frozenset({"web", "web-based", "website", "mobile", "app"})


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def md_text(value: object) -> str:
    """Render stored metadata as text, never as Markdown/HTML instructions."""
    value = clean_text(value)
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]])", r"\\\1", value)


def keywords_for(thesis) -> list[str]:
    raw = thesis.keywords or []
    if isinstance(raw, list):
        return [clean_text(item) for item in raw if clean_text(item)]
    return [clean_text(raw)] if clean_text(raw) else []


def read_corpus():
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
        rows = list(get_topic_trends_queryset())
        # Run the unmodified production service on the same frozen rows.
        baseline = analyze_topics(rows)
    return rows, baseline


def corpus_fingerprint(rows) -> str:
    payload = [
        {
            "id": str(row.id),
            "title": row.title,
            "abstract": row.abstract,
            "keywords": row.keywords,
        }
        for row in rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def representations(rows):
    documents = [_compose_thesis_text(row) for row in rows]
    title_texts = [row.title or "" for row in rows]
    abstract_texts = [row.abstract or "" for row in rows]
    keyword_texts = [" ".join(keywords_for(row)) for row in rows]
    common_stopwords = {*_EXTRA_STOP_WORDS, *_load_english_stopwords()}

    matrices = {}
    for family, stopwords in (
        ("current", common_stopwords),
        ("weighted", common_stopwords),
        ("weighted_subject", common_stopwords | PLATFORM_TERMS),
    ):
        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
            stop_words=list(stopwords),
            max_df=0.95,
            min_df=2,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        base = vectorizer.fit_transform(documents)
        if family == "current":
            matrix = base
        else:
            # One fitted vocabulary and IDF scale keep centroid terms
            # comparable across fields. Each field vector is L2-normalized
            # by TfidfVectorizer.transform before the 2:1:2 combination.
            matrix = normalize(
                2 * vectorizer.transform(title_texts)
                + vectorizer.transform(abstract_texts)
                + 2 * vectorizer.transform(keyword_texts)
            )
        matrices[family] = (matrix, vectorizer.get_feature_names_out())
    return matrices


def measure(matrix, k: int):
    runs = []
    reference_model = None
    reference_labels = None
    silhouettes = []
    for seed in SEEDS:
        model = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = model.fit_predict(matrix)
        runs.append(labels)
        if len(set(labels)) > 1 and len(set(labels)) < matrix.shape[0]:
            silhouettes.append(float(silhouette_score(matrix, labels, metric="cosine")))
        if seed == 42:
            reference_model = model
            reference_labels = labels

    stability = [adjusted_rand_score(a, b) for a, b in combinations(runs, 2)]
    sizes = sorted(Counter(int(label) for label in reference_labels).values(), reverse=True)
    if len(reference_labels) != matrix.shape[0] or sum(sizes) != matrix.shape[0]:
        raise RuntimeError(f"k={k}: a candidate did not assign every thesis exactly once")
    return {
        "k": k,
        "stability": statistics.median(stability),
        "silhouette": statistics.median(silhouettes) if silhouettes else float("nan"),
        "sizes": sizes,
        "singleton_count": sizes.count(1),
        "model": reference_model,
        "labels": reference_labels,
    }


def choose_candidate(measurements):
    # A stable but fragmented result is a poor review candidate. Within a
    # representation, prefer no singleton groups, then seed stability, then
    # cosine silhouette. Human subject review still decides suitability.
    eligible = [result for result in measurements if not result["singleton_count"]]
    pool = eligible or measurements
    return max(pool, key=lambda result: (result["stability"], result["silhouette"]))


def top_terms(centroid, feature_names) -> list[str]:
    terms = []
    stems = set()
    for index in centroid.argsort()[::-1][: KEYWORDS_PER_CLUSTER * 3]:
        term = str(feature_names[index])
        stem = re.sub(r"s$", "", term).lower()
        if stem in stems:
            continue
        stems.add(stem)
        terms.append(term)
        if len(terms) == KEYWORDS_PER_CLUSTER:
            break
    return terms


def candidate_clusters(rows, features, measurement):
    _, feature_names = features
    labels = measurement["labels"]
    model = measurement["model"]
    by_cluster = {}
    for index, label in enumerate(labels):
        by_cluster.setdefault(int(label), []).append(index)
    average = len(rows) / len(by_cluster)
    clusters = []
    for cluster_id in sorted(by_cluster, key=lambda cid: (-len(by_cluster[cid]), cid)):
        indices = by_cluster[cluster_id]
        terms = top_terms(model.cluster_centers_[cluster_id], feature_names)
        clusters.append(
            TopicCluster(
                cluster_id=cluster_id,
                topic=_label_cluster(terms, [keywords_for(rows[i]) for i in indices]),
                trend=_classify_trend(len(indices), average, len(rows)),
                thesis_count=len(indices),
                keywords=terms,
                sample_titles=[rows[i].title for i in indices[:5]],
                thesis_ids=[str(rows[i].id) for i in indices],
            )
        )
    counts = Counter(cluster.topic for cluster in clusters)
    for cluster in clusters:
        if counts[cluster.topic] > 1:
            cluster.topic = f"{cluster.topic} (Cluster {cluster.cluster_id + 1})"
    return clusters


def check_membership(rows, clusters, heading: str):
    expected = {str(row.id) for row in rows}
    assigned = [thesis_id for cluster in clusters for thesis_id in cluster.thesis_ids]
    if len(assigned) != len(rows) or set(assigned) != expected:
        raise RuntimeError(f"{heading}: missing or extra thesis assignment")
    if len(assigned) != len(set(assigned)):
        raise RuntimeError(f"{heading}: a thesis appears in more than one group")
    if any(cluster.thesis_count != len(cluster.thesis_ids) for cluster in clusters):
        raise RuntimeError(f"{heading}: displayed count differs from membership")


def abstract_excerpt(text: str, limit: int = 300) -> str:
    value = clean_text(text)
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def member_notes(thesis) -> list[str]:
    notes = []
    if not keywords_for(thesis):
        notes.append("No stored keywords; inspect the source if this affects the topic.")
    if "mswd online financial assistance" in (thesis.title or "").casefold():
        notes.append(
            "Source caveat: the manuscript prints an HTEFinder/OJT abstract under its ABSTRACT heading; "
            "review that source mismatch before relying on the abstract for grouping."
        )
    return notes


def detail_section(name: str, clusters, by_id: dict[str, object]) -> list[str]:
    lines = [f"## {name}", ""]
    for cluster in clusters:
        lines.extend(
            [
                f"### {md_text(cluster.topic)} — {cluster.thesis_count} theses",
                "",
                f"**Cluster ID:** {cluster.cluster_id + 1} · **Size badge:** {cluster.trend} · "
                f"**Leading TF-IDF terms:** {', '.join(md_text(term) for term in cluster.keywords) or 'none'}",
                "",
                "The name is an **unverified suggestion**. For each thesis, mark whether its research "
                "subject fits this group name. Check the source document if stored metadata looks wrong.",
                "",
            ]
        )
        for thesis_id in cluster.thesis_ids:
            thesis = by_id[thesis_id]
            link = f"http://localhost:5173/repository/{thesis_id}"
            lines.extend(
                [
                    f"- **{md_text(thesis.title)}** ([open thesis]({link}); UUID `{thesis_id}`)",
                    f"  - Stored keywords: {', '.join(md_text(kw) for kw in keywords_for(thesis)) or 'none'}",
                    f"  - Abstract evidence: {md_text(abstract_excerpt(thesis.abstract)) or 'none'}",
                    "  - Review: [ ] Fits subject  [ ] Does not fit  [ ] Unclear — notes: ______",
                ]
            )
            for note in member_notes(thesis):
                lines.append(f"  - **Source check:** {md_text(note)}")
        lines.append("")
    return lines


def make_report(rows, baseline, all_results, selected, matrices, fingerprint):
    by_id = {str(row.id): row for row in rows}
    chosen_clusters = {
        family: candidate_clusters(rows, matrices[family], selected[family])
        for family in ("weighted", "weighted_subject")
    }
    check_membership(rows, baseline.clusters, "production baseline")
    for family, clusters in chosen_clusters.items():
        check_membership(rows, clusters, family)

    descriptions = {
        "current": "Current combined title + abstract + stored keywords",
        "weighted": "Same vocabulary; L2-normalized title:abstract:keywords weights 2:1:2",
        "weighted_subject": "2:1:2 weights; web, web-based, website, mobile, app excluded",
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Topic Trend Analysis: read-only cluster review",
        "",
        f"Generated: **{now}**. Approved theses: **{len(rows)}**.",
        f"Corpus SHA-256: `{fingerprint}`",
        "",
        "This fingerprint covers each approved thesis's UUID, title, abstract, and stored keywords "
        "in the production query order. If any of those fields or the approved set changes, rerun "
        "the report before using its conclusions.",
        "",
        "**No live algorithm, thesis record, database value, or embedding was changed.** "
        "All labels below are heuristic suggestions until a human checks every member. "
        "The existing emerging/saturated/underexplored badges describe relative group size.",
        "",
        "## How to review",
        "",
        "1. Compare the three detailed groupings below, prioritizing shared **research subject** "
        "over application platform or technology.",
        "2. For each member, mark whether the proposed group name fits. Open the thesis link "
        "to read its full abstract and keywords; consult its PDF when the stored metadata is doubtful.",
        "3. A specific group name is verified for this snapshot only if every member fits it. "
        "If one does not, record the mismatch instead of accepting the name. This review cannot "
        "verify future uploads or changed metadata.",
        "",
        "The live comparison path is **Trend Analysis → cluster card → thesis detail**. "
        "The thesis links below assume the local frontend is running at `http://localhost:5173` "
        "and that the reviewer is signed in.",
        "",
        "## Comparison method",
        "",
        "All configurations use the production tokenizer, min/max document frequencies, "
        "unigrams/bigrams, `sublinear_tf=True`, K-Means `n_init=10`, and the existing naming rules. "
        "For each family and k=5–12, the audit fits seeds 42 and 0–10. Stability is the median "
        "pairwise adjusted Rand index (ARI) across those runs. Separation is the median cosine "
        "silhouette, calculated within that family's vector space. **Do not compare silhouette "
        "values across different families as though they share one geometry.**",
        "",
        "The two alternative examples below are chosen within their own family by highest "
        "stability among results with no singleton groups, breaking ties with silhouette. "
        "This is a numerical shortlist, not a claim that their subjects or names are more accurate.",
        "",
        "| Representation | k | Seed-42 group sizes | Singletons | Median ARI | Median cosine silhouette |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for family in ("current", "weighted", "weighted_subject"):
        for result in all_results[family]:
            lines.append(
                f"| {descriptions[family]} | {result['k']} | "
                f"{', '.join(map(str, result['sizes']))} | {result['singleton_count']} | "
                f"{result['stability']:.3f} | {result['silhouette']:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Configurations selected for member review",
            "",
            f"- **Production baseline:** k={len(baseline.clusters)}; current live names and members.",
            f"- **Weighted fields:** k={selected['weighted']['k']}; 2:1:2 field weights.",
            f"- **Weighted, subject-oriented:** k={selected['weighted_subject']['k']}; "
            "same weights with five generic platform terms removed.",
            "",
        ]
    )
    if NOTES_PATH.exists():
        notes = NOTES_PATH.read_text(encoding="utf-8")
        marker = f"<!-- corpus-sha256: {fingerprint} -->"
        if notes.startswith(marker):
            lines.extend([notes.removeprefix(marker).strip(), ""])
        else:
            lines.extend(
                [
                    "## Prior review notes",
                    "",
                    "Notes from another corpus snapshot were omitted. Review the current "
                    "members before carrying those observations forward.",
                    "",
                ]
            )
    lines.extend(detail_section("Production baseline", baseline.clusters, by_id))
    lines.extend(detail_section("Weighted fields candidate", chosen_clusters["weighted"], by_id))
    lines.extend(
        detail_section("Weighted, subject-oriented candidate", chosen_clusters["weighted_subject"], by_id)
    )
    lines.extend(["## Full stored abstracts for source checking", ""])
    for row in rows:
        lines.extend(
            [
                f"### {md_text(row.title)}",
                "",
                f"UUID: `{row.id}` · [open thesis](http://localhost:5173/repository/{row.id})",
                "",
                f"Stored keywords: {', '.join(md_text(kw) for kw in keywords_for(row)) or 'none'}",
                "",
                md_text(row.abstract) or "No stored abstract.",
                "",
            ]
        )
        for note in member_notes(row):
            lines.extend([f"**Source check:** {md_text(note)}", ""])
    return "\n".join(lines)


def main():
    rows, baseline = read_corpus()
    if not rows:
        raise RuntimeError("No approved theses are available for comparison")
    fingerprint = corpus_fingerprint(rows)
    matrices = representations(rows)
    all_results = {
        family: [measure(matrix, k) for k in K_VALUES if k < len(rows)]
        for family, (matrix, _) in matrices.items()
    }

    # The independently rebuilt current representation must reproduce the
    # exact production seed-42 partition before its scores are trusted.
    production_by_id = {
        thesis_id: cluster.cluster_id
        for cluster in baseline.clusters
        for thesis_id in cluster.thesis_ids
    }
    expected = [production_by_id[str(row.id)] for row in rows]
    current_k = len(baseline.clusters)
    measured = next(result for result in all_results["current"] if result["k"] == current_k)
    if list(map(int, measured["labels"])) != expected:
        raise RuntimeError("Rebuilt current representation does not match production membership")

    selected = {
        family: choose_candidate(all_results[family])
        for family in ("weighted", "weighted_subject")
    }
    final_rows, _ = read_corpus()
    if corpus_fingerprint(final_rows) != fingerprint:
        raise RuntimeError("Approved corpus changed during the read-only benchmark")
    report = make_report(rows, baseline, all_results, selected, matrices, fingerprint)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(rows)} approved theses, fingerprint {fingerprint})")
    for family in selected:
        result = selected[family]
        print(
            f"{family}: k={result['k']} ARI={result['stability']:.3f} "
            f"cosine_silhouette={result['silhouette']:.3f} sizes={result['sizes']}"
        )


if __name__ == "__main__":
    main()
