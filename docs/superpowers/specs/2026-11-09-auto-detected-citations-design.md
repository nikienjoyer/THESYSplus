# Auto-detected citations only

**Date:** 2026-11-09
**Source:** panel recommendation after the defense
**Mockup:** [mockups/2026-11-09-auto-cited-success-screen.html](mockups/2026-11-09-auto-cited-success-screen.html) (approved 2026-11-09)

## Goal

Citations between repository theses are found by the system only. The uploader
no longer ticks, unticks, searches for, or saves them. After upload, the
success screen shows the theses that were found and already saved.

## What the user said

- Remove manual adding of citations after upload.
- No checkboxes. The system fills in the result.
- Plan for a thesis that cites 2 or more repository theses.
- Show it on the success screen, not the upload form, so reading the whole
  document does not slow down auto-fill.
- It is fine that most uploads find nothing. The demo citation rows (one
  detected, one manual) were already deleted from the database.

## Evidence that shaped the design

Measured on the 203 approved theses in the local database (2026-11-06):

| Finding | Effect on design |
|---|---|
| 17 of 18 detected matches were author-plus-year, and every one inspected was wrong (for example "David, A. (2022)" linked three unrelated theses). | With no one confirming, author-year matching is deleted. |
| Full-title match found the same 1 real citation as the current 8-word-prefix match. | Switch to full-title match: same recall here, and it cannot confuse formulaic titles that share their first 8 words ("Development of a web based student information system for …"). |
| No two approved theses share a title. | Identical titles are not handled specially. |
| Reading the first 10 pages of a scanned PDF took 27–92 s. | Detection stays in the upload request, which already reads the whole document. Nothing is added to auto-fill. |

## Behaviour

1. Uploader submits the thesis (sync or async job path, both go through
   `ThesisUploadView._process_synchronous`).
2. After the thesis row is created, the server runs detection on the
   `extracted_text` it already has and stores one `ThesisCitation` per match,
   `created_by` = uploader.
3. The 201 response carries `cited: [{id, title, year}, …]`, the saved list,
   sorted by title.
4. The success screen shows that list read-only.

**2 or more matches:** all are stored and all are listed, one row each with
title and year. The list grows inside the modal, which already scrolls; no
inner scroll box. No cap: in the data the most found for one thesis was 7,
and those were the wrong author-year matches now removed.

**Student uploads:** citations are stored while the thesis is pending. They
count toward "Cited by" only once the citing thesis is approved. This is how
`cited_by_count` and `GET /citations/` already work; nothing changes there.

**Failures:** detection or storing must never fail an upload. Any exception is
logged and the response carries `cited: []`, which shows as "none found".

**Retries:** the async worker can re-run an upload. Storage uses
`bulk_create(ignore_conflicts=True)` against the existing unique
`(citing, cited)` constraint, so a re-run stores nothing twice.

## Matching rule

A repository thesis is cited when:

- it is approved and is not the uploaded thesis itself, and
- its whole title, normalised (lowercase, punctuation to spaces, whitespace
  collapsed) and at least 4 words long, appears in the normalised reference
  section.

The reference section is unchanged: text after the last
"References / Bibliography / Literature cited" heading, or the last 20% of
the text when there is no heading.

Known limit: a reference that drops the cited thesis's subtitle is missed.
Accepted, because a miss is invisible while a wrong match inflates another
thesis's "Cited by" with no one able to remove it except an admin.

## Changes

### Backend

| File | Change |
|---|---|
| `theses/services/citations.py` | Delete the author-year branch and `_surname`. Match the full title, not the first 8 words. Return `{id, title, year}` (no `match` key). Update the docstring. |
| `theses/views.py`, upload Step 8 | Store the matches as `ThesisCitation` rows, then return them under `cited` (replaces `cited_candidates`). |
| `theses/views.py`, `ThesisCitationsView` | Delete `post` and `_uuids`. `GET` stays. |
| `theses/models.py`, `ThesisCitation` | Delete the `source` field and its `Source` choices: every row is now detected, so the field carries no information. |
| `theses/migrations/0011_…` | Generated `RemoveField` for `source`. |
| `theses/admin.py` | Drop `source` from `list_display` and `list_filter`. |
| `theses/management/commands/detect_citations.py` | Every match is a title match now: drop the `match` column and the title-only filter. Dry run by default and `--apply` stay. |

### Frontend

| File | Change |
|---|---|
| `components/upload/UploadThesisModal.jsx` | Replace `CitedChecklist` with a read-only list fed by `success.cited`. Drop the `SearchSuggestions` import. Copy per the mockup. |
| `components/search/SearchSuggestions.jsx` | Delete the `onPickTitle` prop; the checklist was its only caller. |

Success-screen copy (from the approved mockup):

- Heading: "Repository theses cited in this paper", with a count badge when 1 or more.
- Approved upload help: "Found in your reference list. Each one now counts this thesis under "Cited by"." ("It now counts" when exactly 1.)
- Pending upload help: "Found in your reference list. It counts under "Cited by" once your thesis is approved." ("They count" when 2 or more.)
- None found: "None of the repository's theses appear in your reference list."

## Testing

Backend (`theses/tests/test_citations.py`):

- Keep: title match, excludes self and unapproved, no-heading tail, empty
  text, last heading wins, unique pair, no self-citation, GET lists approved
  citing only, counts ignore unapproved citing.
- Delete: author-year tests, short-surname test, every POST test, manual-ids test.
- New: a title sharing its first 8 words with the reference but differing
  after them is not matched.
- New: `POST /citations/` returns 405.
- Change: the upload test asserts the `ThesisCitation` row exists and the
  response's `cited` list holds it.
- Change: the `detect_citations` test drops its author-year expectations.

Frontend: no unit tests exist for the modal. Verify in the browser on the
side-by-side test servers (backend 8001, Vite 5174): upload a document whose
references contain a repository title, check the list in light and dark at
desktop and phone width, then an upload with no matches.

## Out of scope

- A "Cites" list on the thesis detail page.
- Re-running detection when a pending thesis is approved later (run
  `detect_citations --apply` instead).
- Letting uploaders or faculty remove a wrong match (admin can, in Django admin).
