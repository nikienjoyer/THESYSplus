# Auto-detected Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Citations between repository theses are detected and saved by the server during upload; the success screen shows them read-only, with no checkboxes, search, or Save button.

**Architecture:** `find_cited_theses` becomes a whole-title matcher. The upload view stores its matches as `ThesisCitation` rows right after creating the thesis and returns them as `cited`. The confirm endpoint (`POST /citations/`) and the `source` field go away. The modal renders `success.cited` as a plain list.

**Tech Stack:** Django 5 + DRF, pytest-django, React 18 + Vite + Tailwind.

**Spec:** `docs/superpowers/specs/2026-11-09-auto-detected-citations-design.md` (mockup: `docs/superpowers/specs/mockups/2026-11-09-auto-cited-success-screen.html`)

## Global Constraints

- Work on branch `auto-detected-citations`, never directly on `main`.
- `/ponytail:ponytail` for every code change (shortest diff, reuse what exists); `/impeccable:impeccable` for the UI task.
- Detection or storing must never fail an upload: log and return `cited: []`.
- Only approved theses can be cited; a thesis never cites itself (existing DB constraint `thesis_citation_not_self`).
- Backend tests: from `backend/`, `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -q`.
- Browser checks: side-by-side test servers only (`.claude/launch.json` `test-backend` on 8001, `test-frontend` on 5174). Never touch :8000 or :5173. The user signs in themselves.
- Copy is fixed by the spec (see Task 4).

## Review Focus

1. Reference list writes the title with different case or punctuation ("SMART-PARKING availability detection: using ultrasonic sensors") → still matched. Test in Task 1.
2. Repository title under 4 words whose words appear in the references → never matched. Test in Task 1.
3. Detection raises during upload → upload still returns 201 with `cited == []`, no rows. Test in Task 2.
4. Student (pending) upload that cites a thesis → row stored, `cited` returned, but `cited_by_count` stays 0 until the student's thesis is approved. Test in Task 2.
5. An async job result produced before deploy has no `cited` key → success screen shows "none found", not a crash. Handled in Task 4 (`success.cited || []`).

---

### Task 1: Whole-title matcher

**Files:**
- Modify: `backend/theses/services/citations.py`
- Modify: `backend/theses/management/commands/detect_citations.py`
- Test: `backend/theses/tests/test_citations.py`

**Interfaces:**
- Produces: `find_cited_theses(text: str, exclude_id=None) -> list[dict]`, each dict exactly `{'id': str, 'title': str, 'year': int}`, sorted by title. No `match` key.

- [ ] **Step 0: Branch and commit the design docs (from the repo root)**

```bash
git switch -c auto-detected-citations
git add docs/superpowers/specs/2026-11-09-auto-detected-citations-design.md docs/superpowers/specs/mockups/2026-11-09-auto-cited-success-screen.html docs/superpowers/plans/2026-11-09-auto-detected-citations.md
git commit -m "Spec and plan: citations are auto-detected only"
```

All later backend commands and `git add` paths run from `backend/`.

- [ ] **Step 1: Update tests**

In `test_citations.py`:
- `test_title_match`: expected becomes `[{'id': str(cited.id), 'title': cited.title, 'year': 2021}]`.
- Delete `test_author_year_match`, `test_author_year_needs_same_line`, `test_short_surname_ignored`.
- `test_detect_citations_dry_run_and_apply`: drop the `'author_year' in out.getvalue()` assertion; keep the rest (the Barangay thesis is no longer matched, so the apply result is unchanged).
- Add:

```python
def test_shared_eight_word_prefix_is_not_a_match(uploader, make_thesis):
    make_thesis(uploader, 'Development of a Web-Based Student Information System for Lubao')
    refs = 'REFERENCES\nCruz, J. (2020). Development of a web-based student information system for Guagua.'
    assert find_cited_theses(refs) == []


def test_title_match_ignores_case_and_punctuation(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    refs = 'REFERENCES\nManalo (2021). SMART-PARKING availability detection: using ultrasonic\nsensors.'
    assert [c['id'] for c in find_cited_theses(refs)] == [str(cited.id)]


def test_short_title_never_matches(uploader, make_thesis):
    make_thesis(uploader, 'Inventory System', authors=['Garcia, Liza'])
    assert find_cited_theses('REFERENCES\nGarcia (2022). Inventory system for a store.') == []
```

- [ ] **Step 2: Run, expect failures**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -q`
Expected: FAIL on `test_title_match` (extra `match` key) and `test_shared_eight_word_prefix_is_not_a_match`.

- [ ] **Step 3: Change `find_cited_theses` in `citations.py`**

Match `f" {' '.join(words)} "` (whole normalised title, `len(words) >= 4`) against the normalised references; delete the author-year branch, the `lines` list, and `_surname`; drop `authors` from `.only(...)`; return `{'id', 'title', 'year'}`. Rewrite the module docstring: one signal (whole title), only approved theses, saved without confirmation.

- [ ] **Step 4: Simplify `detect_citations`**

Every candidate is stored on `--apply`; print `f'{thesis.title[:50]!r} -> {cand["title"][:50]!r}'`; rename the counter to `matches`; docstring no longer mentions author-year or title-only filtering.

- [ ] **Step 5: Run, expect pass**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -q`
Expected: all pass. (`test_upload_response_carries_cited_candidates` still asserts `cands[0]['match']` and fails here; change that line to `cands[0]['id'] == str(cited.id)`. Task 2 rewrites the test fully.)

- [ ] **Step 6: Commit**

```bash
git add theses/services/citations.py theses/management/commands/detect_citations.py theses/tests/test_citations.py
git commit -m "Match cited theses by whole title only"
```

---

### Task 2: Save detected citations during upload

**Files:**
- Modify: `backend/theses/views.py` (upload Step 8, around line 1246)
- Test: `backend/theses/tests/test_citations.py`

**Interfaces:**
- Consumes: `find_cited_theses` from Task 1.
- Produces: upload 201 body key `cited: list[{'id', 'title', 'year'}]` (replaces `cited_candidates`). Task 4 reads it.

- [ ] **Step 1: Rewrite the upload test and add two**

Factor the body of `test_upload_response_carries_cited_candidates` into a helper `_upload(client, user, extra_lines) -> Response` (sync mode, same payload). Then:

```python
def test_upload_saves_cited_theses(client, make_thesis, settings, tmp_path):
    # faculty upload; cited = approved thesis whose title is in the PDF text
    r = _upload(client, faculty, [cited.title])
    assert r.status_code == 201, r.content
    new_id = r.json()['id']
    assert r.json()['cited'] == [{'id': str(cited.id), 'title': cited.title, 'year': 2021}]
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id', 'created_by_id')) == [
        (UUID(new_id), cited.id, faculty.id)]


def test_student_upload_saves_but_does_not_count_yet(client, make_thesis, settings, tmp_path):
    # same, uploader role STUDENT
    assert r.json()['cited'][0]['id'] == str(cited.id)
    assert ThesisCitation.objects.count() == 1
    rows = client.get(reverse('thesis-list'), **_auth(student)).json()['results']
    assert {x['id']: x['cited_by_count'] for x in rows}[str(cited.id)] == 0


def test_upload_survives_detection_error(client, make_thesis, settings, tmp_path, monkeypatch):
    def boom(*a, **k): raise RuntimeError('x')
    monkeypatch.setattr('theses.services.citations.find_cited_theses', boom)
    r = _upload(client, faculty, [cited.title])
    assert r.status_code == 201 and r.json()['cited'] == []
    assert ThesisCitation.objects.count() == 0
```

`UUID` comes from `uuid`. `settings.MEDIA_ROOT = str(tmp_path / 'media')` and `settings.DOCUMENT_PROCESSING_ASYNC = False` go in the helper's callers as today. Fixtures for `faculty`/`student` follow the existing `create_user` pattern with distinct emails.

- [ ] **Step 2: Run, expect failure**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -q -k upload`
Expected: FAIL (`KeyError: 'cited'`).

- [ ] **Step 3: Change Step 8 in `ThesisUploadView`**

Inside the existing `try`: `cited = find_cited_theses(...)`, then `ThesisCitation.objects.bulk_create([ThesisCitation(citing=thesis, cited_id=c['id'], created_by=request.user) for c in cited], ignore_conflicts=True)`, then `data['cited'] = cited`. The `except` sets `data['cited'] = []`. Update the Step 8 comment: citations are saved, not confirmed. The import stays inside the method (the monkeypatch targets the module attribute).

- [ ] **Step 4: Run, expect pass**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add theses/views.py theses/tests/test_citations.py
git commit -m "Save detected citations during upload"
```

---

### Task 3: Remove the confirm endpoint and the source field

**Files:**
- Modify: `backend/theses/views.py` (`ThesisCitationsView`, around line 471)
- Modify: `backend/theses/models.py` (`ThesisCitation`)
- Modify: `backend/theses/admin.py:589-590`
- Create: `backend/theses/migrations/0011_remove_thesiscitation_source.py` (generated)
- Test: `backend/theses/tests/test_citations.py`

**Interfaces:**
- Produces: `ThesisCitation(citing, cited, created_by, created_at)`, no `source`. `GET /theses/<id>/citations/` unchanged; `POST` returns 405.

- [ ] **Step 1: Update tests**

Delete `_post`, `test_post_saves_valid_and_skips_bad_ids`, `test_post_is_idempotent`, `test_post_forbidden_for_other_student`, `test_post_with_list_body_saves_nothing`, `test_post_manual_ids_saved_as_manual`, and the `other` fixture if unused. Add:

```python
def test_post_citations_not_allowed(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    r = client.post(reverse('thesis-citations', args=[mine.id]), {}, content_type='application/json', **_auth(uploader))
    assert r.status_code == 405
```

- [ ] **Step 2: Run, expect failure**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py::test_post_citations_not_allowed -q`
Expected: FAIL (200, not 405).

- [ ] **Step 3: Delete `post` and `_uuids` from `ThesisCitationsView`**

Docstring becomes: "``GET``: approved theses citing this one. Citations are saved by the upload view." Remove now-unused imports only if nothing else in `views.py` uses them (`Role` and `make_error_response` are used elsewhere; check before removing).

- [ ] **Step 4: Delete `source` and `Source` from `ThesisCitation`; drop `source` from admin `list_display` and remove `list_filter`**

- [ ] **Step 5: Generate the migration**

Run: `DJANGO_ENV=development ./venv/Scripts/python.exe manage.py makemigrations theses -n remove_thesiscitation_source`
Expected: creates `0011_remove_thesiscitation_source.py` with one `RemoveField`. Then `./venv/Scripts/python.exe manage.py makemigrations --check --dry-run` prints "No changes detected".

- [ ] **Step 6: Run the theses suite**

Run: `./venv/Scripts/python.exe -m pytest theses -q`
Expected: all pass. `grep -rn "Source\.\|source=" theses --include=*.py` shows no `ThesisCitation` uses.

- [ ] **Step 7: Commit**

```bash
git add theses/views.py theses/models.py theses/admin.py theses/migrations/0011_remove_thesiscitation_source.py theses/tests/test_citations.py
git commit -m "Remove citation confirm endpoint and source field"
```

---

### Task 4: Read-only cited list on the success screen

**Files:**
- Modify: `frontend/src/components/upload/UploadThesisModal.jsx:180-265` (`CitedChecklist`), `:30` (import), `:856-858` (usage)
- Modify: `frontend/src/components/search/SearchSuggestions.jsx:7,22,58`

**Interfaces:**
- Consumes: `success.cited` (Task 2) and `success.status` (`'approved'` or pending).
- Produces: `function CitedList({ cited, approved })`, replaces `CitedChecklist`.

- [ ] **Step 1: Replace `CitedChecklist` with `CitedList`**

No state, no `client` call. Keep the existing `<section>` wrapper classes and `aria-labelledby="cited-heading"`. Structure per the approved mockup: heading "Repository theses cited in this paper" with a count badge (`tabular-nums`, pill, `bg-surface-secondary border border-border-default`) when `cited.length > 0`; a bordered `<ol>` with hairline-divided rows, title left in `text-ink`, year right in `text-muted tabular-nums`, `py-2.5 px-3`; no inner scroll (`max-h` removed). Exact copy:

| Case | Help text |
|---|---|
| approved, 1 | `Found in your reference list. It now counts this thesis under "Cited by".` |
| approved, 2+ | `Found in your reference list. Each one now counts this thesis under "Cited by".` |
| pending, 1 | `Found in your reference list. It counts under "Cited by" once your thesis is approved.` |
| pending, 2+ | `Found in your reference list. They count under "Cited by" once your thesis is approved.` |
| 0 | `None of the repository's theses appear in your reference list.` (no list, no badge) |

Usage: `<CitedList cited={success.cited || []} approved={success.status === 'approved'} />`, still inside `{success.id && …}`. Remove the `SearchSuggestions` import.

- [ ] **Step 2: Delete `onPickTitle` from `SearchSuggestions`**

Remove the prop, the line-58 branch, and the doc-comment mention.

- [ ] **Step 3: Lint and build**

Run (from `frontend/`): `npm run lint` then `npm run build`
Expected: no new lint errors in the two files; build succeeds.

- [ ] **Step 4: Browser check**

Start `test-backend` and `test-frontend` via preview_start; the user signs in as faculty on `http://localhost:5174/sign-in`. Upload a PDF whose reference list contains an approved thesis's full title: the list shows it with the approved help text. Upload one with no matches: the "None of…" line. Screenshot light and dark at desktop and 375 px. Confirm `GET /theses/<cited id>/citations/` lists the new thesis. Stop only 8001/5174 afterwards.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/upload/UploadThesisModal.jsx frontend/src/components/search/SearchSuggestions.jsx
git commit -m "Show auto-detected citations read-only after upload"
```
