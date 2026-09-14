# Requirements Document

## Introduction

Faculty thesis moderation happens in the Django admin. Today the changelist exposes three bulk
actions (`approve_theses`, `reject_theses`, `mark_pending_review`) that let one click set the status
of an arbitrary selection, which contradicts the rule that every manuscript receives an individual
evaluation. Two further gaps follow from the same surface: the reviewer sees no redundancy signal at
the moment of decision, and no durable record of who decided what is written anywhere.

This feature closes all three gaps. Bulk status mutation is removed so a status change can only be
made through the per-object change form. The changelist and change form gain an advisory redundancy
signal computed from precomputed title embeddings, never from a live encode on the render path. And
the per-object save becomes transition-aware: it re-reads the pre-save status from the database,
stamps or clears review provenance under a single rule, and writes exactly one append-only audit row
per real status transition.

The redundancy signal is advisory. Every failure mode in its computation degrades the signal while
leaving the review decision fully functional.

These requirements are derived from `design.md` in this directory and do not extend beyond it.

## Glossary

### Domain terms

- **Redundancy signal**: The advisory overlap measurement shown to a reviewer at decision time,
  consisting of a score, a label, the closest matched approved thesis, the corpus size, and an
  advisory note. It is guidance, never a verdict, and never gates the review decision.
- **Approved corpus**: The set of `Thesis` rows where `status = 'approved'` AND
  `title_embedding IS NOT NULL`. This is the only set a probe is compared against.
- **Probe**: A `Thesis` instance passed to `analyze_titles` for measurement. A probe may be a
  rendered changelist row, a single change-form object, or an unsaved instance. A probe may or may
  not itself be a member of the Approved corpus.
- **Title embedding**: The 384-float L2-normalised SBERT vector of a thesis `title` alone, stored in
  `Thesis.title_embedding`. Used for title-vs-title redundancy measurement.
- **Usable embedding**: A `title_embedding` that is a list of exactly 384 finite numbers whose L2
  norm is at least 1e-6.
- **Composite embedding**: The pre-existing 384-float vector of title + abstract + extracted text +
  keywords, stored in `Thesis.embedding_vector`. Used for semantic search. Distinct from the Title
  embedding because the composite inflates title-vs-title similarity for any thesis whose abstract
  merely mentions related concepts.
- **Terminal status**: `approved` or `rejected`. A transition into a Terminal status stamps review
  provenance.
- **Transition**: A save where the pre-save status read from the database differs from the submitted
  status. A create is a Transition from `NULL`.
- **No-op save**: A save where the pre-save status read from the database equals the submitted
  status, regardless of what other fields changed.
- **Computed**: A `RedundancyResult` where the overlap could be measured (`computed = True`). An
  empty Approved corpus is a Computed measurement of zero overlap.
- **Not computed**: A `RedundancyResult` where the overlap could not be measured
  (`computed = False`), carrying a non-empty machine reason code and rendered as a grey badge.
- **Advisory**: The label-specific guidance sentence returned by `advisory_for(label)` and rendered
  in the change-form panel.

### System names

- **Thesis_Model**: The `theses.models.Thesis` Django model and its `Meta`.
- **Thesis_Admin**: The `theses.admin.ThesisAdmin` `ModelAdmin`, including `save_model` and its
  helpers.
- **Thesis_Changelist**: The admin changelist surface for `Thesis_Admin`, including the
  `_RedundancyChangeList` page-batching hook, `overlap_badge`, and `preview_link`.
- **Thesis_Change_Form**: The admin per-object change form for `Thesis_Admin`, including the
  read-only `redundancy_analysis` panel.
- **Redundancy_Analyzer**: The new `theses/services/redundancy.py` module, whose public surface is
  `analyze_titles`, `label_for`, `advisory_for`, `invalidate_cache`, and `RedundancyResult`.
- **Threshold_Source**: The existing `theses/services/title_similarity.py` module, which owns
  `THRESHOLD_HIGH = 0.85` and `THRESHOLD_MODERATE = 0.60`.
- **Embedding_Service**: The existing `theses/services/semantic_search.py` module, extended with
  `generate_title_embedding`, and owning `embed_text`, `generate_thesis_embedding`, and
  `EMBEDDING_DIM = 384`.
- **Thesis_Upload_Service**: `theses/views.py` → `ThesisUploadView.post`.
- **Embed_Theses_Command**: The `python manage.py embed_theses` management command.
- **Review_Audit_Writer**: `common.audit_logger.write`, which persists one `audit.AuditLog` row and
  swallows and logs its own exceptions.

## Requirements

### Requirement 1: Individual Evaluation Only

**User Story:** As a program chair, I want every thesis status change to require its own form
submission, so that no reviewer can approve or reject a selection of manuscripts without evaluating
each one.

#### Acceptance Criteria

1. THE Thesis_Admin SHALL define the class attribute `actions` with the value `None`, such that
   `Thesis_Admin.actions is None` evaluates true, and SHALL NOT define `actions` as an empty list,
   an empty tuple, or any other sequence, because Django re-adds the site-wide `delete_selected`
   default to a non-`None` sequence.
2. WHEN `Thesis_Admin.get_actions(request)` is called for any request, including one from a
   superuser, one from a staff user holding `delete_thesis` permission, and one from a staff user
   holding no model permissions, THE Thesis_Admin SHALL return a mapping of length 0 that contains
   no key named `delete_selected`, `approve_theses`, `reject_theses`, or `mark_pending_review`.
3. WHEN the Thesis_Changelist page is rendered for any staff user, THE Thesis_Changelist SHALL emit
   no action selector control and no selectable action option, including none named
   `delete_selected`, `approve_theses`, `reject_theses`, or `mark_pending_review`.
4. THE Thesis_Admin SHALL expose no attribute named `approve_theses`, `reject_theses`, or
   `mark_pending_review`, such that an attribute lookup for each of those three names on the
   `Thesis_Admin` class raises `AttributeError` and `hasattr` returns false for each.
5. THE Thesis_Admin SHALL write a `Thesis.status` value only from `save_model` invoked by a
   Thesis_Change_Form submission, and SHALL contain in `theses/admin.py` no other status-writing
   call path, including no queryset `update` and no bulk save of `status`.
6. WHEN a staff user holding `delete_thesis` permission requests the per-object delete URL for a
   single thesis, THE Thesis_Admin SHALL render the per-object delete confirmation page naming
   exactly that one thesis.
7. WHEN a staff user holding `delete_thesis` permission confirms the per-object delete confirmation
   page for one thesis, THE Thesis_Admin SHALL delete exactly that one thesis row and SHALL leave
   every other thesis row unchanged.
8. WHEN the Thesis_Change_Form is rendered for a staff user holding `delete_thesis` permission, THE
   Thesis_Change_Form SHALL render a delete control targeting the per-object delete confirmation
   page for that thesis, so that disabling the action machinery removes bulk delete only.
9. WHERE a `Thesis.status` write originates outside Thesis_Admin — including Thesis_Upload_Service
   setting the initial `pending_review` value on create, the Embed_Theses_Command, a database
   migration, a Django shell session, and any non-admin API path — THE Thesis_Admin SHALL neither
   block nor alter that write, and criteria 1 through 8 SHALL NOT constrain it.

### Requirement 2: Preserved Embedding Repair On Approval

**User Story:** As a repository owner, I want an approved thesis whose embedding failed at upload
time to be repaired at approval, so that an approved manuscript is never permanently invisible to
semantic search and redundancy analysis.

#### Acceptance Criteria

1. WHEN a Transition whose new status is `approved` is persisted, for every pre-save status in
   {`pending_review`, `rejected`, NULL on create}, THE Thesis_Admin SHALL invoke
   `_retry_embedding_if_needed` exactly once for that thesis, after `super().save_model(...)`
   returns and before `Review_Audit_Writer` is invoked.
2. WHERE the thesis `embedding_status` equals `ready`, WHEN `_retry_embedding_if_needed` runs, THE
   Thesis_Admin SHALL return without calling `generate_thesis_embedding` or
   `generate_title_embedding`, without mutating any of `embedding_status`, `embedding_vector`,
   `embedding_model`, `embedding_generated_at`, `title_embedding`, or
   `title_embedding_generated_at`, and without displaying any message.
3. WHERE the thesis `embedding_status` is `not_started`, `processing`, or `failed`, WHEN
   `_retry_embedding_if_needed` runs, THE Thesis_Admin SHALL call `generate_thesis_embedding`
   exactly once and then `generate_title_embedding` exactly once for that thesis.
4. WHEN both `generate_thesis_embedding` and `generate_title_embedding` return without raising, THE
   Thesis_Admin SHALL display exactly one message for that invocation, at info level, whose text
   contains the substring `regenerated`.
5. IF either `generate_thesis_embedding` or `generate_title_embedding` raises any exception, THEN
   THE Thesis_Admin SHALL log exactly one warning, SHALL display exactly one message for that
   invocation at warning level whose text contains the substring `semantic search`, and SHALL
   display no info-level message for that invocation.
6. IF embedding repair raises any exception, THEN THE Thesis_Admin SHALL leave the persisted
   `Thesis.status` equal to `approved`, leave `reviewed_by` equal to `request.user` and
   `reviewed_at` non-NULL, and SHALL still invoke `Review_Audit_Writer` for that Transition.
7. WHEN a save whose new status is `rejected` or `pending_review` is persisted, or a No-op save
   whose submitted status is `approved` is persisted, THE Thesis_Admin SHALL not invoke
   `_retry_embedding_if_needed` and SHALL leave `embedding_status`, `embedding_vector`,
   `embedding_model`, `embedding_generated_at`, `title_embedding`, and
   `title_embedding_generated_at` equal to their pre-save stored values.
8. IF `generate_thesis_embedding` persists successfully and `generate_title_embedding` then raises
   within the same `_retry_embedding_if_needed` invocation, THEN THE Thesis_Admin SHALL retain the
   values `generate_thesis_embedding` wrote, SHALL leave `title_embedding` and
   `title_embedding_generated_at` at their pre-invocation values, and SHALL report the outcome only
   through the single warning-level message required by criterion 5.
9. WHEN a request served after a Transition into `approved` reads that thesis, for each of the
   repair outcomes success, exception, and partial completion, THE Thesis_Admin SHALL report
   `Thesis.status` equal to `approved` and SHALL have caused exactly one `AuditLog` row with
   `event_type` equal to `thesis.review.approved` to exist for that Transition.

### Requirement 3: Title Embedding Storage

**User Story:** As a developer, I want the title-only embedding persisted in its own nullable
column, so that review-time redundancy analysis reads a precomputed vector instead of encoding text
on the render path.

#### Acceptance Criteria

1. THE Thesis_Model SHALL define a `title_embedding` JSON field with `null=True` and `blank=True`.
2. THE Thesis_Model SHALL define a `title_embedding_generated_at` datetime field with `null=True`
   and `blank=True`.
3. THE migration that introduces these columns SHALL contain exactly two `AddField` operations and
   zero data-migration operations, and its reverse SHALL consist of exactly two `RemoveField`
   operations that drop both columns together with every stored title embedding and timestamp value,
   leaving every other `Thesis` column, index, constraint, and row unchanged.
4. WHEN that migration is applied to a database holding existing thesis rows, including a
   re-application after a reverse, THE Thesis_Model SHALL leave `title_embedding` and
   `title_embedding_generated_at` NULL for every pre-existing row and SHALL leave every other column
   value of those rows unchanged.
5. WHERE the thesis `title` contains at least one non-whitespace character, WHEN
   `generate_title_embedding` completes successfully for a thesis, THE Embedding_Service SHALL store
   in `title_embedding` a list of exactly `EMBEDDING_DIM` (384) floats whose L2 norm equals 1.0
   within a tolerance of 1e-3.
6. WHEN `generate_title_embedding` completes successfully for a thesis, THE Embedding_Service SHALL
   persist the row with a focused update limited to `title_embedding`,
   `title_embedding_generated_at` set to the UTC time of that encode, and `updated_at`, leaving
   `embedding_vector`, `embedding_status`, `embedding_model`, `embedding_generated_at`, and every
   other column of that row unchanged, so the write advances `updated_at`.
7. WHEN a thesis upload reaches the embedding step, THE Thesis_Upload_Service SHALL call
   `generate_thesis_embedding` and `generate_title_embedding` inside separate exception-handling
   blocks.
8. IF `generate_thesis_embedding` raises during upload, THEN THE Thesis_Upload_Service SHALL still
   call `generate_title_embedding` and still return HTTP 201.
9. IF `generate_title_embedding` raises during upload, THEN THE Thesis_Upload_Service SHALL still
   return HTTP 201 and leave both `title_embedding` and `title_embedding_generated_at` NULL.
10. WHERE `--titles-only` is supplied and `--regenerate` is absent, THE Embed_Theses_Command SHALL
    select only theses whose `title_embedding` is NULL, SHALL NOT select a thesis whose stored
    `title_embedding` predates a later change to its `title`, and SHALL write only
    `title_embedding`, `title_embedding_generated_at`, and `updated_at`.
11. WHERE `--titles-only` and `--regenerate` are both supplied, THE Embed_Theses_Command SHALL
    select all theses, SHALL overwrite any previously stored `title_embedding` and
    `title_embedding_generated_at`, and SHALL leave `embedding_vector`, `embedding_status`,
    `embedding_model`, and `embedding_generated_at` unchanged for every row.
12. WHERE `--titles-only` is absent, THE Embed_Theses_Command SHALL retain its existing selection
    predicate, write the composite embedding only, and leave `title_embedding` and
    `title_embedding_generated_at` unchanged for every row.
13. IF a per-row encode raises while the Embed_Theses_Command runs, THEN THE Embed_Theses_Command
    SHALL count that row as failed, continue with the remaining rows, let no exception escape the
    command, and report success and failure tallies whose sum equals the number of selected rows.
14. WHERE a thesis `title` is empty or contains only whitespace, WHEN `generate_title_embedding`
    runs for that thesis, THE Embedding_Service SHALL store a `title_embedding` of exactly 384
    floats each equal to 0.0, SHALL set `title_embedding_generated_at` as specified in criterion 6,
    and SHALL raise no exception. Because that stored vector is not a Usable embedding, the
    consequence is that the thesis is excluded from the Approved corpus matrix under Requirement 5
    criterion 8, and its own probe result is `computed = False` with
    `reason = 'missing_title_embedding'` under Requirement 5 criterion 12.
15. WHEN a thesis `title` is changed by any surface other than `generate_title_embedding`, THE
    Thesis_Model SHALL leave the stored `title_embedding` and `title_embedding_generated_at`
    unchanged, so the stored vector may describe a superseded title until `generate_title_embedding`
    runs for that thesis or `embed_theses --titles-only --regenerate` is run.
16. THE Thesis_Model SHALL leave `title_embedding_generated_at` NULL for every row whose
    `title_embedding` is NULL, SHALL NOT define a database constraint enforcing that relationship,
    and SHALL NOT guarantee the converse; THE Redundancy_Analyzer and THE Embed_Theses_Command SHALL
    therefore test title-embedding presence by reading `title_embedding` and SHALL NOT read
    `title_embedding_generated_at` as a presence test.

### Requirement 4: Review-Time Redundancy Measurement

**User Story:** As a faculty reviewer, I want to see how closely a submitted title overlaps the
approved corpus at the moment I decide, so that I can judge redundancy without running a separate
tool.

#### Acceptance Criteria

1. THE Redundancy_Analyzer SHALL build the Approved corpus from theses where `status = 'approved'`
   AND `title_embedding IS NOT NULL`.
2. WHEN `analyze_titles` is called with K probes (K >= 1) carrying a Usable embedding and the
   Approved corpus holds N >= 1 rows carrying a Usable embedding, THE Redundancy_Analyzer SHALL
   produce all K x N similarities by invoking the vector-math multiplication operation exactly once,
   on a (K, 384) operand and a (384, N) operand, with that invocation count remaining 1 for every
   value of K and every value of N.
3. THE Redundancy_Analyzer SHALL compute scores exclusively from stored `title_embedding` values.
4. WHILE `Embedding_Service.embed_text` is replaced by a callable that raises, THE
   Redundancy_Analyzer SHALL return a result for every probe without raising.
5. THE `theses/services/redundancy.py` module SHALL contain zero import statements referencing
   `semantic_search`.
6. THE Redundancy_Analyzer SHALL obtain `THRESHOLD_HIGH` and `THRESHOLD_MODERATE` by importing them
   from the Threshold_Source.
7. WHEN `label_for(score)` is called with a score below 0.60, THE Redundancy_Analyzer SHALL return
   the label `Clean`.
8. WHEN `label_for(score)` is called with a score greater than or equal to 0.60 and less than 0.85,
   THE Redundancy_Analyzer SHALL return the label `Moderate`.
9. WHEN `label_for(score)` is called with a score greater than or equal to 0.85, THE
   Redundancy_Analyzer SHALL return the label `High Overlap`.
10. WHEN `label_for(0.60)` is called, THE Redundancy_Analyzer SHALL return `Moderate`, and WHEN
    `label_for(0.85)` is called, THE Redundancy_Analyzer SHALL return `High Overlap`.
11. THE Redundancy_Analyzer SHALL produce, for every score in [-1.0, 1.0], a label whose severity
    ordering matches the classification returned by `title_similarity.classify` for that same score,
    where `Clean` corresponds to `LOW_SIMILARITY`, `Moderate` to `MODERATELY_SIMILAR`, and
    `High Overlap` to `HIGHLY_SIMILAR`.
12. THE Redundancy_Analyzer SHALL return, for every result, a `matched_thesis_id` that differs from
    that result's `thesis_id`, including when the probe is itself a member of the Approved corpus at
    cosine 1.0.
13. WHEN `analyze_titles` is called with an iterable of probes that may contain repeated ids, THE
    Redundancy_Analyzer SHALL return a mapping whose key set equals the set of distinct probe ids
    and whose length equals the count of distinct probe ids in that iterable.
14. WHERE a result has `computed = True`, THE Redundancy_Analyzer SHALL return a `score` in the
    closed interval [-1.0, 1.0] and a `label` equal to `label_for(score)`.
15. WHERE a result has `computed = True` and `matched_thesis_id` is not None, THE
    Redundancy_Analyzer SHALL return a `matched_title` equal to the stored `title` of the matched
    thesis.
16. WHEN `analyze_titles` is called with a set of probes, THE Redundancy_Analyzer SHALL return, for
    each probe, the same `score`, `label`, and `matched_thesis_id` that it returns when called with
    that probe as the only element of the input.
17. THE Redundancy_Analyzer SHALL order Approved corpus rows by `('created_at', 'id')` and SHALL
    resolve tied maximum similarities to the lowest column index.
18. THE Redundancy_Analyzer SHALL hold its cached corpus matrix, ids, titles, and cache key in
    module-level state local to the operating-system process serving the call, SHALL key that cache
    on the pair (count of Approved corpus rows, maximum `updated_at` of Approved corpus rows), and
    SHALL derive that key with exactly one aggregate query per `analyze_titles` call.
19. WHILE the cache key derived from the database equals the key held by the process serving the
    call, THE Redundancy_Analyzer SHALL reuse that process's cached matrix and SHALL issue zero
    Approved corpus row queries.
20. WHEN a thesis is added to, removed from, re-approved into, or re-embedded within the Approved
    corpus and that mutation changes either the row count or the maximum `updated_at` of the
    Approved corpus, THE Redundancy_Analyzer SHALL issue exactly one Approved corpus row query on
    the next `analyze_titles` call in each process, rebuild that process's cached matrix, and return
    results that reflect that mutation.
21. WHEN `invalidate_cache()` is called, THE Redundancy_Analyzer SHALL discard the calling process's
    cached key, matrix, ids, and titles, so that the next `analyze_titles` call in that process
    re-derives the key and rebuilds the matrix from the database.
22. WHEN `analyze_titles` is called, THE Redundancy_Analyzer SHALL read each probe only through its
    `id` and `title_embedding` attributes, SHALL accept probes that have never been saved to the
    database, SHALL execute no INSERT, UPDATE, or DELETE statement, and SHALL leave every persisted
    field of every stored thesis row unchanged across the call.
23. WHEN the Thesis_Changelist renders a page of rows, THE Thesis_Changelist SHALL call
    `analyze_titles` exactly once for that page and SHALL pass the paginated `result_list` rather
    than the unpaginated filtered queryset.
24. WHEN `overlap_badge` is called for a row present in the per-request stash, THE
    Thesis_Changelist SHALL read the stashed result rather than calling `analyze_titles` again.
25. WHEN `analyze_titles` is called with an empty iterable of probes, THE Redundancy_Analyzer SHALL
    return an empty mapping and SHALL issue zero database queries.
26. WHILE two or more threads in the same process call `analyze_titles` concurrently, THE
    Redundancy_Analyzer SHALL serialise every read and write of the cached key, matrix, ids, and
    titles under a single lock, SHALL return to each caller results measured against one consistent
    corpus snapshot whose matrix rows, ids, and titles come from the same load, and SHALL raise no
    exception in any caller.
27. IF a deletion from and an insertion into the Approved corpus leave both the row count and the
    maximum `updated_at` unchanged between two `analyze_titles` calls, THEN THE Redundancy_Analyzer
    SHALL reuse the cached matrix and SHALL return results measured against the pre-mutation corpus
    until either the derived cache key changes or `invalidate_cache()` is called.

### Requirement 5: Graceful Degradation Of The Advisory Signal

**User Story:** As a faculty reviewer, I want the review page to keep working when the redundancy
signal cannot be measured, so that a data or environment problem never blocks a decision.

#### Acceptance Criteria

1. IF a probe's `title_embedding` is NULL, an empty list, or a value that is not a list, THEN THE
   Redundancy_Analyzer SHALL return a result with `computed = False` and
   `reason = 'missing_title_embedding'`, regardless of the value of
   `title_embedding_generated_at`.
2. IF a probe's `title_embedding` is a non-empty list whose length differs from 384, THEN THE
   Redundancy_Analyzer SHALL return a result with `computed = False` and
   `reason = 'dimension_mismatch'`, and SHALL apply this length check before any check on the list's
   element values.
3. IF the NumPy import fails or the matrix multiplication raises, THEN THE Redundancy_Analyzer SHALL
   return `computed = False` with `reason = 'vector_math_unavailable'` for every probe that carried
   a Usable embedding, SHALL leave unchanged the `reason` already assigned to every other probe
   under criteria 1, 2, and 12, and SHALL return normally without raising.
4. IF loading the Approved corpus raises a database error, THEN THE Redundancy_Analyzer SHALL return
   `computed = False` with `reason = 'vector_math_unavailable'` for every probe that carried a
   Usable embedding, SHALL leave the previously cached key, matrix, ids, and titles unchanged, and
   SHALL return normally without raising.
5. WHERE a result has `computed = False`, THE Redundancy_Analyzer SHALL return `score = 0.0`,
   `label = 'Not computed'`, `matched_thesis_id = None`, `matched_title = ''`, `corpus_size = 0`,
   and a non-empty `reason`.
6. WHEN the count of Approved corpus rows admitted to the matrix under criterion 8 is zero, THE
   Redundancy_Analyzer SHALL return, for every probe with a Usable embedding and regardless of that
   probe's own `status`, `computed = True`, `score = 0.0`, `label = 'Clean'`,
   `matched_thesis_id = None`, `matched_title = ''`, `corpus_size = 0`, and `reason = ''`.
7. WHEN the only Approved corpus row admitted to the matrix under criterion 8 is the probe itself,
   THE Redundancy_Analyzer SHALL return `computed = True`, `score = 0.0`, `label = 'Clean'`,
   `matched_thesis_id = None`, `matched_title = ''`, `corpus_size = 0`, and `reason = ''` for that
   probe.
8. IF a stored Approved corpus row holds a `title_embedding` that is not a Usable embedding, THEN
   THE Redundancy_Analyzer SHALL omit that row from the matrix, SHALL exclude it from every result's
   `corpus_size`, SHALL never return its id as a `matched_thesis_id`, and SHALL continue with the
   remaining rows without raising.
9. WHEN `analyze_titles` is called with any iterable of 0 to 200 probes, including probes whose
   embeddings are NULL, non-list, wrong-dimension, non-numeric, non-finite, or zero-norm, unsaved
   instances, and duplicate ids, THE Redundancy_Analyzer SHALL return a mapping holding exactly one
   result per distinct probe id and SHALL raise no exception.
10. IF `analyze_titles` raises inside the Thesis_Changelist page-batching hook, THEN THE
    Thesis_Changelist SHALL log a warning, set the per-request stash to an empty mapping, SHALL not
    re-raise that exception, and SHALL render the grey `Not computed` badge for every row for which
    no `computed = True` result is available.
11. WHILE any degradation described in criteria 1 through 10 and criterion 12 is in effect, WHEN a
    staff user issues a GET request to the changelist URL
    (`reverse('admin:theses_thesis_changelist')`), the add-form URL
    (`reverse('admin:theses_thesis_add')`), or the change-form URL
    (`reverse('admin:theses_thesis_change', args=[thesis id])`), THE Thesis_Admin SHALL return HTTP
    200 for that request.
12. IF a probe's `title_embedding` is a list of exactly 384 values that is not a Usable embedding
    because it holds an element which is not a number, holds an element that is NaN or infinite, or
    has an L2 norm below 1e-6, THEN THE Redundancy_Analyzer SHALL treat that vector as absent and
    return a result with `computed = False` and `reason = 'missing_title_embedding'`.
13. THE Redundancy_Analyzer SHALL return `reason = ''` for every result with `computed = True`, and
    SHALL return for every result with `computed = False` a `reason` equal to exactly one of
    `'missing_title_embedding'`, `'dimension_mismatch'`, or `'vector_math_unavailable'`, and no
    other value.
14. WHILE any degradation described in criteria 1 through 10 and criterion 12 is in effect, WHEN a
    staff user submits the Thesis_Change_Form POST request with a status value that differs from the
    stored status, THE Thesis_Admin SHALL persist that status change and SHALL return a response
    that is not a server-error response (HTTP status below 500).

### Requirement 6: Corpus Context In The Advisory

**User Story:** As a faculty reviewer, I want the advisory to state how large the corpus it compared
against was, so that a green badge over an empty corpus is not read as a clean bill of health.

#### Acceptance Criteria

1. THE Redundancy_Analyzer SHALL populate `RedundancyResult.corpus_size` with a non-negative integer
   equal to the count of Approved corpus rows carrying a Usable embedding whose id differs from that
   result's `thesis_id`, so a probe that is itself a member of the Approved corpus is excluded from
   its own `corpus_size` and a probe that is not a member reduces `corpus_size` by nothing.
2. WHEN the Thesis_Change_Form renders a result with `computed = True`, a non-null
   `matched_thesis_id`, and `corpus_size` greater than or equal to 2, THE Thesis_Change_Form SHALL
   render a note stating the `corpus_size` value as a decimal integer followed by the plural noun
   form `theses`.
3. WHEN the Thesis_Change_Form renders a result with `computed = True` and `corpus_size = 0`, THE
   Thesis_Change_Form SHALL render a note stating that no other approved thesis was available to
   compare against, and SHALL render no numeric corpus size in that note.
4. WHEN the Thesis_Change_Form renders a result with `computed = True` and `corpus_size = 1`, THE
   Thesis_Change_Form SHALL render a note stating the value `1` followed by the singular noun form
   `thesis`.
5. WHERE a result has `computed = False`, THE Redundancy_Analyzer SHALL return `corpus_size = 0`.
6. WHEN the Thesis_Changelist renders `overlap_badge` for any result, THE Thesis_Changelist SHALL
   omit the `corpus_size` value from the badge text, so corpus context is rendered only by the
   Thesis_Change_Form panel.

### Requirement 7: Changelist Overlap Badge And Preview Link

**User Story:** As a faculty reviewer, I want the overlap level and a preview link on the
changelist, so that I can triage the queue and open a manuscript without losing the admin tab.

#### Acceptance Criteria

1. THE Thesis_Changelist SHALL include `overlap_badge` and `preview_link` in `list_display`.
2. WHEN `overlap_badge` renders a result with `computed = True`, THE Thesis_Changelist SHALL apply
   the label colour as the badge span's `background-color` — `#DC3545` for `High Overlap`, `#FFA500`
   for `Moderate`, `#28A745` for `Clean` — with white label text, using the same inline-styled span
   shape as `status_badge`.
3. WHEN `overlap_badge` renders a result with `computed = True`, THE Thesis_Changelist SHALL render
   the label text, then one space, then the score multiplied by 100 rounded half away from zero to
   exactly one decimal place, then `%`, emitting a leading `-` for a negative score, so that score
   `0.8543` renders `85.4%` and score `-0.0321` renders `-3.2%`. This is the single definition of
   the percentage format referenced by Requirement 8.
4. IF no result for the thesis is obtained from the per-request stash or from the single-probe
   fallback in criterion 13, or the obtained result has `computed = False`, THEN THE
   Thesis_Changelist SHALL render background colour `#6C757D` with white text `Not computed` and
   SHALL append no percentage.
5. THE `overlap_badge` callable SHALL omit `admin_order_field`, so the Overlap column header renders
   without a sort link.
6. WHEN `preview_link` renders for a thesis, THE Thesis_Changelist SHALL emit one anchor whose
   visible text is `Preview` and whose `href` equals the resolved frontend base URL followed by
   `/theses/`, the thesis primary key in canonical UUID string form, and `/preview`, with no
   trailing `/` after `preview`.
7. WHEN `preview_link` renders for a thesis, THE Thesis_Changelist SHALL emit
   `target="_blank"` and `rel="noopener noreferrer"` on that anchor.
8. WHERE `settings.FRONTEND_URL` is defined, THE Thesis_Changelist SHALL use its value as the
   frontend base URL.
9. WHERE `settings.FRONTEND_URL` is absent and `settings.CORS_ALLOWED_ORIGINS` is non-empty, THE
   Thesis_Changelist SHALL use the first entry of `CORS_ALLOWED_ORIGINS` as the frontend base URL.
10. IF `settings.FRONTEND_URL` is absent and `settings.CORS_ALLOWED_ORIGINS` is empty or absent,
    THEN THE Thesis_Changelist SHALL use `http://localhost:5173` as the frontend base URL.
11. THE Thesis_Changelist SHALL strip every trailing `/` character from the resolved frontend base
    URL before appending the preview path.
12. THE Thesis_Changelist SHALL apply `select_related('uploaded_by', 'reviewed_by')` to its
    queryset.
13. IF `overlap_badge` is called for a thesis that has no entry in the per-request stash, including
    when the request carries no stash attribute at all, THEN THE Thesis_Changelist SHALL call
    `analyze_titles` exactly once with that thesis as the only probe and SHALL render the returned
    result.
14. THE Thesis_Changelist SHALL derive the rendered label from `label_for` applied to the unrounded
    score, so that a score whose displayed percentage rounds up to a threshold boundary keeps the
    label of the unrounded score: score `0.5999` renders `Clean 60.0%` and score `0.8499` renders
    `Moderate 85.0%`.
15. THE Thesis_Changelist SHALL emit the `preview_link` anchor for every rendered thesis row
    regardless of the thesis `status`, the presence of an uploaded file, and the reviewer's frontend
    session state, and SHALL perform no authorization or document-availability check against the
    target route.

### Requirement 8: Change-Form Redundancy Panel And Read-Only Provenance

**User Story:** As a faculty reviewer, I want the redundancy detail and the review provenance shown
read-only on the change form, so that I see the closest match at decision time and cannot
mis-attribute a decision.

#### Acceptance Criteria

1. THE Thesis_Admin SHALL include `redundancy_analysis` in `readonly_fields` and SHALL define the
   `fields` of the Review Status fieldset as exactly the five-element ordered tuple
   (`status`, `rejection_reason`, `redundancy_analysis`, `reviewed_by`, `reviewed_at`), containing no
   other field.
2. WHEN the Thesis_Change_Form renders for an existing thesis, and WHEN the add form renders for an
   unsaved thesis, THE Thesis_Admin SHALL render `reviewed_by` and `reviewed_at` as non-editable
   text, emitting zero `input`, `select`, or `textarea` elements named `reviewed_by` or
   `reviewed_at`.
3. THE Thesis_Admin SHALL write `reviewed_by` and `reviewed_at` only from `save_model`.
4. WHEN the Thesis_Change_Form renders `redundancy_analysis` for a result with `computed = True` and
   a non-null `matched_thesis_id`, THE Thesis_Change_Form SHALL render the label, the score as a
   percentage in the format defined by Requirement 7 criterion 3 so that both surfaces yield an
   identical percentage substring for the same score, the matched thesis title, an anchor whose href
   is produced by `reverse('admin:theses_thesis_change', args=[matched_thesis_id])` and which is
   rendered for every staff user regardless of that user's permissions on the matched thesis, and
   the text returned by `advisory_for(label)`.
5. IF the object passed to `redundancy_analysis` is None or has a NULL primary key, THEN THE
   Thesis_Change_Form SHALL render text stating that redundancy analysis is available after the
   thesis is saved, SHALL make zero calls to `analyze_titles`, and SHALL issue zero Approved corpus
   queries.
6. WHEN the Thesis_Change_Form renders `redundancy_analysis` for a result with `computed = False`,
   THE Thesis_Change_Form SHALL render the text `Not computed`, a non-empty human-readable sentence
   of at most 200 characters that is distinct for each of the reason codes
   `missing_title_embedding`, `dimension_mismatch`, and `vector_math_unavailable`, and the backfill
   command `manage.py embed_theses --titles-only`.
7. THE `advisory_for` function SHALL return, for each of the four labels `High Overlap`, `Moderate`,
   `Clean`, and `Not computed`, exactly one non-empty string of at most 300 characters, and the four
   returned strings SHALL be pairwise distinct.
8. IF a change-form POST carries a submitted value for `reviewed_by` or `reviewed_at`, THEN THE
   Thesis_Admin SHALL discard that submitted value, SHALL raise no form validation error, and SHALL
   persist for those two fields only the values assigned by `save_model`.
9. WHEN the Thesis_Change_Form renders for an existing thesis, THE Thesis_Admin SHALL render
   `rejection_reason` as an editable form input and SHALL persist the submitted `rejection_reason`
   value on save, including when the save is a No-op save.
10. IF a staff user follows the matched-thesis anchor while lacking change permission on the matched
    thesis, THEN THE Thesis_Admin SHALL deny that request through the existing Django admin
    permission check, and THE Thesis_Change_Form SHALL expose no field value of the matched thesis
    other than its `title` and its id.

### Requirement 9: Transition-Aware Review Provenance

**User Story:** As a program chair, I want review provenance stamped from the actual database
transition, so that a stale form or a concurrent reviewer cannot produce a wrong or missing stamp.

#### Acceptance Criteria

1. WHEN `save_model` runs with `change` true and the object's primary key not NULL, THE Thesis_Admin
   SHALL read the pre-save status by issuing exactly one query, filtered on that primary key, that
   fetches only the `status` column of at most one row and constructs no `Thesis` instance, and SHALL
   treat that query returning no row as a pre-save status of NULL.
2. THE Thesis_Admin SHALL classify a save as a Transition or a No-op save solely by comparing the
   submitted `obj.status` with the pre-save status read in criterion 1, and SHALL NOT consult
   `form.changed_data` or `form.initial` for that classification.
3. WHILE `form.initial` holds a status value that differs from the stored status, WHEN `save_model`
   runs, THE Thesis_Admin SHALL use the stored status as the pre-save status, so that a stale form
   neither reports a Transition the database does not show nor suppresses one that it does.
4. WHEN `save_model` runs with `change` false or with the object's primary key NULL, THE Thesis_Admin
   SHALL treat the pre-save status as NULL without issuing a pre-save status query, and SHALL treat
   the save as a Transition for every submitted status value, including `pending_review`.
5. WHEN a Transition whose new status is `approved` or `rejected` is persisted, THE Thesis_Admin
   SHALL set `reviewed_by` to `request.user` and `reviewed_at` to a UTC timestamp no earlier than the
   start of that request and no later than the return of `save_model`.
6. WHEN a Transition whose new status is `pending_review` is persisted, THE Thesis_Admin SHALL set
   `reviewed_by` and `reviewed_at` to NULL, including when both stored values are already NULL, in
   which case the persisted values SHALL remain NULL.
7. WHEN a No-op save is persisted, THE Thesis_Admin SHALL leave the stored `reviewed_by` and
   `reviewed_at` byte-identical to their pre-save values, regardless of which other editable fields
   the form changed.
8. THE Thesis_Admin SHALL assign `reviewed_by` and `reviewed_at` before calling
   `super().save_model(...)`, so that the status and the provenance are persisted by that one call,
   and SHALL invoke the embedding repair helper and then the Review_Audit_Writer only after
   `super().save_model(...)` returns.
9. WHILE the stored `reviewed_by` is non-NULL and names a user other than `request.user`, WHEN a
   Transition whose new status is `approved` or `rejected` is persisted, THE Thesis_Admin SHALL
   overwrite the stored `reviewed_by` with `request.user` and the stored `reviewed_at` with that
   save's timestamp rather than preserving the earlier values.
10. WHEN two reviewers submit the Thesis_Change_Form for the same thesis and both saves are persisted
    in sequence, THE Thesis_Admin SHALL use the first save's persisted status as the second save's
    pre-save status, and SHALL leave the persisted `reviewed_by` and `reviewed_at` equal to the values
    written by the later save without rejecting either submission.
11. WHILE the stored status equals the submitted status `rejected`, WHEN the Thesis_Change_Form
    submits a changed `rejection_reason`, THE Thesis_Admin SHALL persist the submitted
    `rejection_reason` while leaving `reviewed_by` and `reviewed_at` unchanged.

### Requirement 10: Audit Trail For Review Decisions

**User Story:** As a program chair, I want one append-only audit row per review decision, so that I
can reconstruct who decided what and when, even after a later reviewer overwrites the provenance
fields.

#### Acceptance Criteria

1. WHEN a Transition is persisted, THE Thesis_Admin SHALL call `Review_Audit_Writer` exactly once
   for that save, so that at most one `AuditLog` row per save carries a `thesis.review.` event type.
2. WHEN a Transition whose new status is `approved` is persisted, THE Thesis_Admin SHALL use the
   event type `thesis.review.approved`.
3. WHEN a Transition whose new status is `rejected` is persisted, THE Thesis_Admin SHALL use the
   event type `thesis.review.rejected`.
4. WHEN a Transition whose new status is `pending_review` is persisted, THE Thesis_Admin SHALL use
   the event type `thesis.review.reopened`.
5. WHEN a Transition is persisted, THE Thesis_Admin SHALL invoke `Review_Audit_Writer` strictly
   after `super().save_model(...)` has returned without raising and after the embedding repair helper
   has run, so that the written row's `created_at` is greater than or equal to the persisted
   thesis's `updated_at`.
6. WHEN `Review_Audit_Writer` is invoked, THE Thesis_Admin SHALL pass `actor = request.user`,
   `target = obj.uploaded_by`, `success = True`, and the current `request`, where `target` is
   non-NULL for every persisted thesis because `Thesis.uploaded_by` is a non-nullable foreign key
   with `on_delete = PROTECT`.
7. WHEN `Review_Audit_Writer` is invoked, THE Thesis_Admin SHALL pass metadata containing exactly
   the keys `thesis_id`, `title`, `previous_status`, `new_status`, `program`, `year`, and `created`,
   plus `rejection_reason` only in the case stated in criterion 8, where `thesis_id` is the string
   form of the thesis primary key, `title` is the stored title truncated to its first 200 characters
   counted as characters rather than bytes and with no ellipsis appended, `previous_status` is the
   pre-save status string read from the database or NULL when the save is a create and never a
   sentinel string such as an empty string or `none`, `new_status` is the persisted status string,
   `program` is the stored program value, `year` is the stored year as an integer, and `created` is
   True only when the save created the row.
8. WHERE the new status is `rejected`, THE Thesis_Admin SHALL additionally pass `rejection_reason`
   in the metadata as the stored value truncated to its first 500 characters, counted as characters
   rather than bytes.
9. WHEN a No-op save occurs, THE Thesis_Admin SHALL not invoke `Review_Audit_Writer`, leaving the
   count of `AuditLog` rows unchanged.
10. THE Thesis_Admin SHALL produce, over any sequence of change-form saves, a count of `AuditLog`
    rows whose `event_type` starts with `thesis.review.` equal to the number of saves in that
    sequence that were Transitions.
11. IF the `AuditLog` insert raises, or the passed `target` cannot be resolved to a stored user
    record, THEN THE Thesis_Admin SHALL complete the review request with the status change
    persisted, relying on `Review_Audit_Writer` to insert the row with `target_user` NULL when only
    resolution failed and to log any insert failure to the `audit` logger without re-raising.
12. WHEN two reviewers submit the change form for the same thesis in sequence, THE Thesis_Admin
    SHALL write one audit row per Transition, each carrying a `previous_status` equal to the status
    stored in the database immediately before that reviewer's save.
13. IF `super().save_model(...)` raises for a Transition, THEN THE Thesis_Admin SHALL not invoke
    `Review_Audit_Writer` for that save and SHALL leave the count of `AuditLog` rows whose
    `event_type` starts with `thesis.review.` unchanged.
14. THE Thesis_Admin SHALL use only the event type values `thesis.review.approved`,
    `thesis.review.rejected`, and `thesis.review.reopened`, each of which is 22 characters and
    therefore within the 64-character limit of `AuditLog.event_type`.
15. THE Thesis_Admin SHALL create `AuditLog` rows by insert only and SHALL issue no update and no
    delete against any `AuditLog` row.

### Requirement 11: Output Escaping Of User-Supplied Text

**User Story:** As a security reviewer, I want every user-supplied value in the new admin callables
escaped, so that a thesis title cannot inject markup into a reviewer's admin page.

#### Acceptance Criteria

1. THE Thesis_Admin SHALL pass every value it renders from `overlap_badge`, `preview_link`, and
   `redundancy_analysis` into markup through a `format_html` placeholder, and SHALL treat every value
   read from a `Thesis` field, including the probe's own `title` and a matched thesis's `title`, as
   user-supplied.
2. WHEN `overlap_badge` renders for a thesis whose `title` contains any of the characters `<`, `>`,
   `"`, `'`, or `&`, THE Thesis_Changelist SHALL restrict the returned badge markup to the badge
   colour, the label, and the score formatted as a percentage, and SHALL emit zero characters
   originating from that `title` in that markup.
3. WHEN `redundancy_analysis` renders a matched thesis whose `title` contains any of the characters
   `<`, `>`, `"`, `'`, or `&`, THE Thesis_Change_Form SHALL emit each of those five characters only
   in HTML-escaped form, so that the returned markup contains zero unescaped occurrences of them
   originating from that `title`, including when the matched thesis is a record other than the one
   being edited and its `title` was supplied by an uploader other than the current reviewer.
4. WHEN `redundancy_analysis` renders a matched title equal to `<script>alert(1)</script>` or equal
   to `" onmouseover="alert(1)`, THE Thesis_Change_Form SHALL emit that title as visible text inside
   the panel and SHALL emit zero occurrences of `<script`, `</script`, or an
   attribute-terminating `"` originating from that title.
5. THE Thesis_Admin SHALL build the markup of `overlap_badge`, `preview_link`, and
   `redundancy_analysis` from format strings that are literals in the module defining Thesis_Admin,
   without `mark_safe` and without interpolating any rendered value into the format string itself by
   f-string, `%`-formatting, `str.format`, or concatenation, and SHALL leave the markup construction
   of the pre-existing display callables (`title_short`, `status_badge`, `uploaded_by_name`,
   `extracted_text_preview`, `embedding_vector_info`) unchanged.
6. WHEN `redundancy_analysis` renders a matched thesis whose `title` contains a brace sequence such
   as `{`, `}`, `{}`, `{0}`, or `{advisory}`, THE Thesis_Change_Form SHALL emit those brace
   characters as literal visible text, SHALL raise no exception, and SHALL render every other value
   in the same position it occupies for a matched title containing no brace characters.
7. WHERE a rendered result has `computed = False`, WHEN `redundancy_analysis` renders the
   human-readable form of the `reason`, THE Thesis_Change_Form SHALL emit a string selected from a
   fixed Thesis_Admin-owned set keyed by the machine reason code, SHALL emit a fixed default string
   when the code matches no entry in that set, and SHALL include in that string no value read from
   any `Thesis` field.
8. WHEN `redundancy_analysis` renders the advisory text, THE Thesis_Change_Form SHALL derive that
   text solely from the result's `label` through `advisory_for` and SHALL include in it no value read
   from any `Thesis` field.

### Requirement 12: Admin Naming

**User Story:** As a faculty reviewer, I want the admin to say Thesis and Theses, so that the
interface reads correctly.

#### Acceptance Criteria

1. THE Thesis_Model `Meta` SHALL define `verbose_name` as the exact string `Thesis` and
   `verbose_name_plural` as the exact string `Theses`, with no leading or trailing whitespace and
   with the capitalisation as given.
2. WHEN an admin surface whose text derives from the model's plural verbose name is rendered for a
   staff user — specifically the app index entry for the model, the breadcrumb trail segment on the
   changelist page, the breadcrumb trail segment on the add form, change form, and delete
   confirmation pages, and the deletion summary count line on the delete confirmation page — THE
   Thesis_Admin SHALL render the plural form as the exact substring `Theses` in each of those five
   surfaces.
3. WHEN `python manage.py makemigrations --check --dry-run` is run against a codebase in which the
   `verbose_name` and `verbose_name_plural` addition is the only unapplied model edit, THE
   Thesis_Model SHALL cause the command to report that no changes are detected, exit with status 0,
   and leave the set of migration files for the `theses` app unchanged, because neither attribute
   affects the database schema.
4. WHEN `python manage.py makemigrations --check --dry-run` is run after the migration adding
   `title_embedding` and `title_embedding_generated_at` exists and has been applied, THE
   Thesis_Model SHALL cause the command to report that no changes are detected and exit with status
   0, because those two columns are already recorded in migration state and the two naming
   attributes remain non-schema-affecting.
5. THE Thesis_Model `Meta` SHALL retain, unchanged from their pre-change values, `db_table` equal to
   `theses`, `ordering` equal to `['-created_at']`, all three declared indexes
   (`theses_status_created_idx`, `theses_program_idx`, `theses_year_idx`) with their existing field
   lists, and all three declared check constraints (`theses_status_check`, `theses_filetype_check`,
   `theses_year_range_check`) with their existing conditions.
6. WHEN any admin page for the model is rendered and WHEN any `message_user` string is emitted by
   the Thesis_Admin, THE Thesis_Admin SHALL produce zero occurrences of the substring `Thesiss` in
   any case variant, and SHALL render the singular form as the exact substring `Thesis` on the add
   form title, the change form title, and the single-object delete confirmation prompt.

## Requirements Traceability

The mapping from correctness properties to these acceptance criteria lives in the `Correctness
Properties` table of `design.md` (properties P1 through P20). Criteria numbering changed in this
refinement pass — requirements 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, and 12 all gained criteria, and
several existing criteria were split or re-scoped — so every `Validates: Requirements X.Y` reference
in that table needs re-checking against this document before the properties are implemented.
