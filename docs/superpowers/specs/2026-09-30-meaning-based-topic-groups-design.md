# Meaning-based topic groups, technology tags and subject suggestions

Status: approved by the project owner on 2026-09-30 (options chosen in chat).

## Problem

"Explore text clusters" on the Topic Trend Analysis page mislabels theses. Example: THESYS+ (a thesis-repository
system) is listed under **Internet of Things**.

Root cause, measured on the 52 approved theses:

1. **Membership by shared words.** Groups come from TF-IDF + K-Means over title, abstract and keywords.
   THESYS+ has no stored keywords; its strongest pulls are the words *analysis, topic, similarity, trend*.
   K-Means must put every thesis into one of 8 groups, so THESYS+ and Thesix (both repositories) were merged
   with 4 IoT projects and 3 unrelated theses.
2. **One unchecked name per group.** A group is named from its top six TF-IDF terms via a rule table. The group's
   terms were *water, analysis, irrigation, user, iot, smart*; "iot" was the only rule hit, so all 9 members were
   called "Internet of Things" although 4 were IoT projects.
3. **Technology is not a subject.** The 7 IoT theses are about agriculture, accessibility, commerce and security.
   Any design that forces each thesis into one technology-named group mislabels some of them.

Evidence (agreement with the group-reviewed primary subjects, adjusted Rand index; higher is better):

| Grouping | ARI | Purity | Same groups on re-run |
|---|---|---|---|
| TF-IDF + K-Means, k=8 (current) | 0.10 | 46% | 0.38 (median across seeds) |
| SBERT vectors + agglomerative (cosine, average), k=8 | 0.29 | 54% | 1.00 (deterministic, row-order independent) |

Subject suggestion by nearest reviewed-subject centroid over SBERT vectors, leave-one-out on the 52 theses:
correct first suggestion 65%, correct subject within two suggestions 77% (always-most-common baseline 23%).

## Decisions

1. **Explore text clusters groups by meaning.** Stored SBERT document vectors (`Thesis.embedding_vector`) are
   grouped with agglomerative clustering (cosine distance, average linkage). The group count stays
   `_choose_k(n)` (5–8). TF-IDF still supplies each group's "Top keywords (TF-IDF)".
2. **Group names come from members' reviewed subjects.** The most common confirmed primary subject names the group
   when it covers at least half of the reviewed members and is not tied; otherwise the two most common subjects
   are joined with " · ". A group with no reviewed member keeps the existing keyword naming (`_label_cluster`).
   Identical names still get the existing "(Cluster N)" qualifier.
3. **Technology tags per thesis.** IoT, AI, ML, DL, NLP, OCR, CNN, LLM, AR, VR, GPS, GIS, RFID, QR and SMS, detected
   with the existing evidence rule (`services/acronyms.py` `is_about_term`: one mention in title, keywords or
   abstract, or at least 3 full-text mentions at 1 per 10,000 characters or more). Tags are computed when the search
   vector is generated and stored on `Thesis.technology_tags`, so reading them never loads the full text. Each group
   reports tag counts and each member's tags.
4. **Top-2 subject suggestions for theses awaiting review.** Faculty and administrators see the two subjects whose
   reviewed theses are most similar in meaning. Suggestions never assign a subject; the reviewer still confirms.

## Non-goals

- No change to the reviewed-subjects main view, trend thresholds, or the subject vocabulary.
- No automatic subject assignment.
- No new dependencies (scikit-learn 1.9 already provides `AgglomerativeClustering(metric='cosine')`).
- Non-acronym technologies (geofencing, blockchain, "mobile app", "web-based") are out of scope for tags.

## Acceptance

- On the live corpus, THESYS+'s group is not named "Internet of Things", and group ARI against reviewed subjects
  is at least 0.25 at the default group count.
- The response of `GET /api/v1/theses/topic-trends/` keeps every existing field and adds `technology_tags` and
  `member_tags` per cluster.
- The analysis still reads the corpus in a single database query and never loads `extracted_text`.
- `GET /api/v1/theses/<id>/subject-suggestions/` returns up to two suggestions for faculty and administrators only.
- The methodology document and manuscript wording describe the new grouping and suggestions.
