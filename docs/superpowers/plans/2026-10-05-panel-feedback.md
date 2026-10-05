# Panel Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the four panel fixes that are not on hold: wider, less cramped layout; search suggestions while typing; "title similarity" wording; and Google-Scholar-style "Cited by N" counts.

**Architecture:**
- **Backend:** Django REST views in `backend/theses/`. There is one new public `suggest/` endpoint, one new `ThesisCitation` model with a detection service, and a `citations/` endpoint. Citation candidates ride on the existing upload response, which is also the async job result.
- **Frontend:** React + Tailwind. There is one new `SearchSuggestions` component, used by the landing and Repository searches. The citation UI lives in existing pages.

**Tech Stack:** Django 5.0.9 + DRF, PostgreSQL, pytest (`backend/pytest.ini`), React + Vite + Tailwind. The frontend has no test runner, so frontend tasks are verified in the browser.

**Spec:** `docs/superpowers/specs/2026-10-05-panel-feedback-design.md`

## Global Constraints

- **On hold, do not build:** the "Student or Faculty first" step and the landing-page sign-in (spec §2, §3).
- **Privacy:** logged-out visitors never receive thesis titles or authors. `suggest/` returns only keywords to anonymous users.
- **Visibility:** every list of theses shown to a user goes through `_visible_queryset(user)` (`backend/theses/views.py:76`).
- **Count rule:** "Cited by N" counts only citations whose **citing** thesis is `approved`.
- **Test servers:** browser checks run only on the side-by-side servers, started with `preview_start` by name: `test-backend` (8001) and `test-frontend` (5174) in `.claude/launch.json`.
  - **Never** start, stop, or restart anything on 8000 or 5173. Those are the user's live demo and their own Vite.
  - The user signs in themselves. Never type their password.
- **Copy:** sentence-level wording matches existing pages. Use "Cited by N", never "N citations".
- **Commits:** end every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commit only the files a task names. The working tree has unrelated user changes, so never `git add -A`.
- **Run backend tests from `backend/`** with `./venv/Scripts/python.exe -m pytest …`.

## Review Focus

1. **Suggest with an expired token:** a logged-in user whose access token has expired types in the search. Expected: suggestions still load after the client's normal refresh, or quietly show nothing. The search box must keep working. Pinned in Task 4 by the anonymous test and in Task 5 by the "errors are ignored" rule.
2. **Suggest with special characters or very long input:** `%`, `_`, quotes, or a pasted 5,000-character string. Expected: 200 with empty or normal results, never a 500. Pinned by `test_long_and_odd_input_is_safe` in Task 4.
3. **Citing a thesis that is later rejected:** the citing thesis is pending or rejected. Expected: it does not count toward anyone's "Cited by". Pinned by `test_count_ignores_unapproved_citing` in Task 7.
4. **Duplicate save:** the uploader presses "Save citations" twice. Expected: no error and no duplicate rows. Pinned by `test_post_is_idempotent` in Task 7.
5. **Thesis without a references heading:** short text, or text with no "References" line. Expected: detection still runs on the last 20% and returns `[]` rather than crashing. Pinned by `test_no_heading_uses_tail` and `test_empty_text` in Task 6.

---

## File map

| File | Change |
|---|---|
| `frontend/src/components/legal/LegalModal.jsx` | rename wording |
| `frontend/src/pages/LandingPage.jsx` | rename wording, wider container, nav spacing, suggestions |
| `PRODUCT.md` | rename wording |
| `frontend/src/components/layout/PageShell.jsx` | wider band, gutters match navbar |
| `frontend/src/components/layout/AppNavbar.jsx` | link spacing |
| any page file the audit flags | responsive class fixes |
| `backend/theses/views.py` | `ThesisSuggestView`, `ThesisCitationsView`, `cited_candidates` in upload response |
| `backend/theses/urls.py` | two routes |
| `backend/theses/tests/test_thesis_suggest.py` | new |
| `frontend/src/components/search/SearchSuggestions.jsx` | new |
| `frontend/src/pages/RepositoryPage.jsx` | suggestions, "Cited by" on cards |
| `backend/theses/models.py` + migration `0010_thesiscitation.py` | `ThesisCitation` |
| `backend/theses/admin.py` | register `ThesisCitation` |
| `backend/theses/services/citations.py` | new detection service |
| `backend/theses/tests/test_citations.py` | new |
| `backend/theses/serializers.py` | `cited_by_count` on list items |
| `backend/theses/management/commands/detect_citations.py` | new |
| `frontend/src/components/upload/UploadThesisModal.jsx` | cited-theses checklist on success |
| `frontend/src/pages/ThesisDetailPage.jsx` | "Cited by" section |

---

### Task 1: "Originality" → "Title similarity" wording

**Files:**
- Modify: `frontend/src/components/legal/LegalModal.jsx:102`
- Modify: `frontend/src/pages/LandingPage.jsx:84` (and keep the user's uncommitted hero edit at `:397`)
- Modify: `PRODUCT.md:104`

- [ ] **Step 1: Edit the three lines**

`LegalModal.jsx:102`:
```jsx
            <li>Title similarity validation against the full corpus using cosine similarity and TF-IDF</li>
```
`LandingPage.jsx:84`:
```js
    desc:  'See how close your proposed title is to existing theses before you commit to a topic.',
```
`PRODUCT.md:104`:
```markdown
- A title similarity checker that compares proposed topics against the full institutional corpus
```
Leave `LandingPage.jsx:397` ("check title similarity") as the user already changed it.

- [ ] **Step 2: Verify nothing user-facing still says it**

Run (from repo root): `grep -rn -i "originality" frontend/src PRODUCT.md`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/legal/LegalModal.jsx frontend/src/pages/LandingPage.jsx PRODUCT.md
git commit -m "Say 'title similarity' instead of 'originality'

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Note: this commit includes the user's own uncommitted one-line hero change in `LandingPage.jsx`. Check `git diff --cached frontend/src/pages/LandingPage.jsx` first: it must show only lines 84 and 397.

---

### Task 2: Wider pages and roomier navbar

**Files:**
- Modify: `frontend/src/components/layout/PageShell.jsx:19`
- Modify: `frontend/src/pages/LandingPage.jsx:71` and the desktop nav `<ul>` (around `:233`)
- Modify: `frontend/src/components/layout/AppNavbar.jsx` (`NAV_LINK_BASE`, desktop `<ul>`)

- [ ] **Step 1: Widen the content band and line its gutter up with the navbar**

`PageShell.jsx:19`:
```jsx
    <main className={`max-w-7xl 2xl:max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-14 py-8 ${className}`.trim()}>
```
Update its doc comment so it says `max-w-7xl` (1280px), up to 1440px at 2xl, and that the gutters match `NAV_BAR_CLASS`.

`LandingPage.jsx:71`:
```js
const CONTAINER = 'max-w-7xl 2xl:max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-14';
```

- [ ] **Step 2: Give the nav links room**

`AppNavbar.jsx`:
```js
export const NAV_LINK_BASE = 'relative px-3 xl:px-4 py-1.5 rounded-md text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';
```
In both `AppNavbar.jsx` (desktop `<ul className="flex items-center gap-1">`) and `LandingPage.jsx` (desktop `<ul className="flex items-center gap-1">`), change the class to:
```jsx
<ul className="flex items-center gap-1 xl:gap-3">
```

- [ ] **Step 3: Check in the browser**

1. Start the `test-backend` and `test-frontend` servers with `preview_start` by name.
2. Open `http://localhost:5174/`, then ask the user to sign in on `http://localhost:5174/sign-in`.
3. At 1440×900 and 1920×1080, visit `/`, `/repository`, `/title-similarity`, `/trend-analysis` and `/analytics`. Confirm:
   - The page content's left edge lines up with the logo.
   - The content is visibly wider than before.
   - The five nav links have clear gaps.
4. Take one screenshot of `/repository` at 1920 as proof.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/PageShell.jsx frontend/src/components/layout/AppNavbar.jsx frontend/src/pages/LandingPage.jsx
git commit -m "Wider pages and roomier navbar so content isn't bunched in the middle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Responsive audit pass

**Files:** only the page or component files where a defect is found.

This task is discovery followed by fixes. The procedure and the pass bar are fixed. The edits depend on what the audit finds.

- [ ] **Step 1: Sweep every page at four widths, in both themes**

On the test servers, signed in, visit each route below at 375×812, 768×1024, 1280×800 and 1920×1080, in light and dark mode. Routes: `/`, `/repository`, one `/repository/<id>`, `/title-similarity` (run one check), `/trend-analysis`, `/analytics`, `/profile`, `/settings`, and the upload modal opened from the navbar.

At each stop, run this in the page:
```js
[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.tagName + '.' + e.className.toString().slice(0, 60)).slice(0, 10)
```
Record any element it returns. Also look for these:
- text that overflows or gets cut off
- grids that leave one squeezed column
- tap targets smaller than 40px at 375
- a navbar that wraps

- [ ] **Step 2: Fix each finding in the page that owns it**

- **Allowed fixes** are Tailwind class changes:
  - `min-w-0` on grid or flex children that overflow
  - `flex-wrap`
  - `grid-cols-1 sm:grid-cols-2` style breakpoints
  - `overflow-x-auto` on wide tables only
  - `h-10`/`min-h-10` for small tap targets
- **Not allowed:** new layout components, and changes to behavior or copy.

- [ ] **Step 3: Re-run Step 1's overflow check on the fixed pages**

Expected: an empty array at every width.

- [ ] **Step 4: Commit**

```bash
git add <each fixed file>
git commit -m "Responsive fixes from a four-width audit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
If the audit finds nothing, skip the commit and record "no defects" in the task report.

---

### Task 4: `GET /theses/suggest/` endpoint

**Files:**
- Modify: `backend/theses/views.py` (new view near `ThesisPublicStatsView`, ~line 2109)
- Modify: `backend/theses/urls.py` (route **before** `path('<str:id>/', …)`)
- Test: `backend/theses/tests/test_thesis_suggest.py`

**Interfaces:**
- Produces: `GET /api/v1/theses/suggest/?q=<text>` → `{"titles": [{"id": str, "title": str, "year": int}], "keywords": [str], "authors": [str]}`. URL name: `thesis-suggest`.

- [ ] **Step 1: Write the failing tests**

`backend/theses/tests/test_thesis_suggest.py`:
```python
"""GET /api/v1/theses/suggest/ — typing suggestions for the search boxes.

Anonymous callers get keywords only (no titles or authors). Signed-in callers
get titles and authors from what they are allowed to see.
"""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisStatus


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email='student.sg@pampangastateu.edu.ph', first_name='Stu', last_name='Dent',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def other_student(db):
    return User.objects.create_user(
        email='other.sg@pampangastateu.edu.ph', first_name='Oth', last_name='Er',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    counter = {'n': 0}

    def _make(uploaded_by, title, keywords=(), authors=('Dela Cruz, Juan',),
              status=ThesisStatus.APPROVED, year=2024):
        counter['n'] += 1
        n = counter['n']
        t = Thesis(
            title=title, abstract=f'Abstract for {title}.', authors=list(authors),
            keywords=list(keywords), program=Program.BSIT.value, year=year,
            file_type=FileType.PDF, sha256=(f'{n:x}' + 'd' * 64)[:64],
            status=status, uploaded_by=uploaded_by,
        )
        t.uploaded_file.save(f'sg_{n}.pdf', ContentFile(b'%PDF-1.4\n%x'), save=False)
        t.save()
        return t

    return _make


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _get(client, q, user=None):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {_bearer(user)}'} if user else {}
    return client.get(reverse('thesis-suggest'), {'q': q}, **headers)


def test_short_query_returns_empty_lists(client, student):
    body = _get(client, 'a', student).json()
    assert body == {'titles': [], 'keywords': [], 'authors': []}


def test_anonymous_gets_keywords_only(client, student, make_thesis):
    make_thesis(student, 'RFID Attendance Monitoring System', keywords=['RFID', 'IoT'])
    r = _get(client, 'rfid')
    assert r.status_code == 200
    body = r.json()
    assert body['keywords'] == ['RFID']
    assert body['titles'] == [] and body['authors'] == []


def test_signed_in_gets_titles_and_authors(client, student, make_thesis):
    t = make_thesis(student, 'RFID Attendance Monitoring System', keywords=['RFID'],
                    authors=['Rivera, Ana'])
    body = _get(client, 'rfid', student).json()
    assert body['titles'] == [{'id': str(t.id), 'title': t.title, 'year': 2024}]
    assert _get(client, 'rive', student).json()['authors'] == ['Rivera, Ana']


def test_student_never_sees_others_pending_title(client, student, other_student, make_thesis):
    make_thesis(other_student, 'Pending Drone Mapping Study', status=ThesisStatus.PENDING_REVIEW)
    assert _get(client, 'drone', student).json()['titles'] == []


def test_keywords_dedupe_case_and_space_blind(client, student, make_thesis):
    make_thesis(student, 'Alpha thesis title here', keywords=['Machine  Learning'])
    make_thesis(student, 'Beta thesis title here', keywords=['machine learning'])
    assert _get(client, 'machine', student).json()['keywords'] == ['Machine Learning']


def test_long_and_odd_input_is_safe(client, student, make_thesis):
    make_thesis(student, 'Some thesis title words', keywords=['RFID'])
    for q in ['%_%', "o'reilly \"x\"", 'x' * 5000]:
        assert _get(client, q, student).status_code == 200
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_thesis_suggest.py -v`
Expected: FAIL with `NoReverseMatch: Reverse for 'thesis-suggest' not found`.

- [ ] **Step 3: Implement the view**

In `backend/theses/views.py`, add the import next to `IsAuthenticated` (line 33):
```python
from rest_framework.permissions import AllowAny, IsAuthenticated
```
Add the view right above `class ThesisPublicStatsView`:
```python
class ThesisSuggestView(APIView):
    """Typing suggestions for the landing and Repository search boxes.

    Anonymous callers get keywords only: thesis titles and authors stay behind
    sign-in, same as the rest of the landing page. Signed-in callers get titles
    and authors from ``_visible_queryset`` so a student never sees another
    student's pending upload here.
    """

    permission_classes = [AllowAny]
    MIN_LENGTH = 2
    MAX_LENGTH = 100

    def get(self, request, *args, **kwargs):
        q = (request.query_params.get('q') or '').strip()[:self.MAX_LENGTH]
        body = {'titles': [], 'keywords': [], 'authors': []}
        if len(q) < self.MIN_LENGTH:
            return Response(body)
        needle = q.lower()

        # ponytail: Python scan over approved keywords/authors, fine at a few
        # hundred theses; move to a Postgres trigram index past ~10k.
        body['keywords'] = self._matches(
            Thesis.objects.filter(status=ThesisStatus.APPROVED).order_by('created_at').values_list('keywords', flat=True),
            needle, limit=5,
        )
        if not request.user.is_authenticated:
            return Response(body)

        visible = _visible_queryset(request.user)
        body['titles'] = [
            {'id': str(t.id), 'title': t.title, 'year': t.year}
            for t in visible.filter(title__icontains=q).order_by('-year', 'title')[:5]
        ]
        body['authors'] = self._matches(
            visible.order_by('created_at').values_list('authors', flat=True), needle, limit=3,
        )
        return Response(body)

    @staticmethod
    def _matches(lists, needle, *, limit):
        """Distinct values containing ``needle``; case- and space-blind, first spelling kept.

        Values that start with the needle sort before ones that merely contain it.
        """
        seen = {}
        for values in lists:
            for raw in values or []:
                label = ' '.join(str(raw).split())
                key = label.lower()
                if needle in key and key not in seen:
                    seen[key] = label
        return sorted(seen.values(), key=lambda v: (not v.lower().startswith(needle), v.lower()))[:limit]
```

In `backend/theses/urls.py`, import `ThesisSuggestView` alongside the other views, and add this right after the `search/` line:
```python
    path('suggest/', ThesisSuggestView.as_view(), name='thesis-suggest'),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_thesis_suggest.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/theses/views.py backend/theses/urls.py backend/theses/tests/test_thesis_suggest.py
git commit -m "Add /theses/suggest/ for search-as-you-type (keywords only when signed out)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `SearchSuggestions` component on the landing and Repository searches

**Files:**
- Create: `frontend/src/components/search/SearchSuggestions.jsx`
- Modify: `frontend/src/pages/LandingPage.jsx` (hero `<input>` at ~`:410`)
- Modify: `frontend/src/pages/RepositoryPage.jsx` (search `<input>` at ~`:586`)

**Interfaces:**
- Consumes: `GET /theses/suggest/` from Task 4, through `client` (`frontend/src/api/client.js`).
- Produces: `<SearchSuggestions value onChange onPick inputClassName wrapperClassName placeholder ariaLabel />`.
  - `onPick(text)` is called for a keyword or author pick.
  - A title pick navigates to `/repository/:id` itself.

- [ ] **Step 1: Create the component**

`frontend/src/components/search/SearchSuggestions.jsx`:
```jsx
/**
 * SearchSuggestions: a search input with suggestions while typing.
 *
 * Calls GET /theses/suggest/?q= 200ms after typing stops, cancelling any
 * request still in flight. Signed-out users only get keywords back (the
 * server decides). ARIA combobox: ↑/↓ move, Enter picks, Esc closes.
 * Picking a thesis opens it; picking a keyword or author calls onPick(text).
 * Errors are ignored: suggestions are a convenience and must never block search.
 */

import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../../api/client';

const GROUPS = [
  { key: 'titles',   label: 'Theses'   },
  { key: 'keywords', label: 'Keywords' },
  { key: 'authors',  label: 'Authors'  },
];

export default function SearchSuggestions({
  value, onChange, onPick, inputClassName = '', wrapperClassName = '', placeholder, ariaLabel,
}) {
  const navigate = useNavigate();
  const listId = useId();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const skipNext = useRef(false);

  useEffect(() => {
    if (skipNext.current) { skipNext.current = false; return undefined; }
    const q = value.trim();
    if (q.length < 2) { setItems([]); setOpen(false); return undefined; }
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const { data } = await client.get('/theses/suggest/', { params: { q }, signal: ctrl.signal });
        const flat = GROUPS.flatMap(({ key }) => (data[key] || []).map((v) => (
          key === 'titles'
            ? { group: key, text: v.title, id: v.id, meta: v.year }
            : { group: key, text: v }
        )));
        setItems(flat);
        setActive(-1);
        setOpen(flat.length > 0);
      } catch {
        /* aborted or failed: keep the input usable, show nothing */
      }
    }, 200);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [value]);

  const pick = (item) => {
    setOpen(false);
    if (item.group === 'titles') { navigate(`/repository/${item.id}`); return; }
    skipNext.current = true; // the value change below should not reopen the list
    onPick(item.text);
  };

  const onKeyDown = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % items.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i <= 0 ? items.length - 1 : i - 1)); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(items[active]); }
    else if (e.key === 'Escape') { setOpen(false); }
  };

  return (
    <div className={`relative ${wrapperClassName}`}>
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-label={ariaLabel}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onFocus={() => items.length && setOpen(true)}
        className={inputClassName}
        autoComplete="off"
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full mt-1 z-40 max-h-80 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-surface-elevated shadow-lg py-1 text-left"
        >
          {items.map((item, i) => (
            <li key={`${item.group}-${item.text}-${i}`} role="presentation">
              {(i === 0 || items[i - 1].group !== item.group) && (
                <p className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  {GROUPS.find((g) => g.key === item.group).label}
                </p>
              )}
              <div
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); pick(item); }}
                onMouseEnter={() => setActive(i)}
                className={`px-3 py-2 text-sm cursor-pointer flex justify-between gap-3 ${
                  i === active ? 'bg-nav-hover-bg text-ink' : 'text-body'
                }`}
              >
                <span className="truncate">{item.text}</span>
                {item.meta && <span className="text-xs text-muted tabular-nums">{item.meta}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Use it in the landing hero**

In `LandingPage.jsx`, add the import:
```js
import SearchSuggestions from '../components/search/SearchSuggestions';
```
Replace the hero `<input …/>` (the one with `aria-label="Search titles, topics, or authors"`) with:
```jsx
                <SearchSuggestions
                  value={searchQuery}
                  onChange={setSearchQuery}
                  onPick={(text) => navigate(`/repository?q=${encodeURIComponent(text)}`)}
                  wrapperClassName="flex-1 min-w-0"
                  inputClassName={`w-full bg-transparent text-sm outline-none min-w-0 text-gray-100 placeholder-gray-500 ${heroInputTextCls}`}
                  placeholder="Search titles, topics, or authors…"
                  ariaLabel="Search titles, topics, or authors"
                />
```
The surrounding `<div className={… flex items-center …}>` stays. Its `overflow` must not clip the list: if the list is clipped, remove `overflow-hidden` from that div only.

- [ ] **Step 3: Use it in the Repository search**

In `RepositoryPage.jsx`, add the same import with the path `'../components/search/SearchSuggestions'`. Replace the search `<input …/>` inside the filter bar with:
```jsx
              <SearchSuggestions
                value={searchInput}
                onChange={setSearchInput}
                onPick={(text) => {
                  setSearchInput(text);
                  updateSearchParams({ q: text, keyword: '', page: '' });
                }}
                inputClassName="w-full px-4 py-2.5 rounded-lg border text-sm outline-none transition-colors thesys-input"
                placeholder="Search by topic, title, keyword, or author..."
                ariaLabel="Search by topic, title, keyword, or author"
              />
```

- [ ] **Step 4: Check in the browser**

On the test servers:
1. **Signed out, on `/`:** type `rf`. Only a "Keywords" group appears, with no titles.
2. **Signed in, on `/repository`:**
   - Type `rfid`. Theses, Keywords and Authors groups appear.
   - Press ↓ ↓ Enter on a keyword. The search runs.
   - Click a thesis. Its page opens.
   - Press Esc. The list closes.
   - Type one letter. No list appears.
3. **Both themes:** the list is readable in light and dark mode.
4. **Console:** `read_console_messages` with `onlyErrors` shows no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/search/SearchSuggestions.jsx frontend/src/pages/LandingPage.jsx frontend/src/pages/RepositoryPage.jsx
git commit -m "Search suggestions while typing on the landing and Repository searches

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `ThesisCitation` model and detection service

**Files:**
- Modify: `backend/theses/models.py` (append after `Thesis`)
- Create: migration via `makemigrations` (expected `backend/theses/migrations/0010_thesiscitation.py`)
- Modify: `backend/theses/admin.py`
- Create: `backend/theses/services/citations.py`
- Test: `backend/theses/tests/test_citations.py`

**Interfaces:**
- Produces:
  - Model `ThesisCitation(citing: FK Thesis, cited: FK Thesis, source: 'detected'|'manual', created_by: FK User | None, created_at)`, with related names `citations_made` and `citations_received`.
  - Service `find_cited_theses(text: str, exclude_id=None) -> list[dict]`. Each dict is `{'id': str, 'title': str, 'year': int, 'match': 'title' | 'author_year'}`.

- [ ] **Step 1: Write the failing tests**

`backend/theses/tests/test_citations.py`:
```python
"""Citation links between repository theses, and finding them in reference lists."""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.db import IntegrityError

from accounts.models import Role, User
from theses.models import FileType, Program, Thesis, ThesisCitation, ThesisStatus
from theses.services.citations import find_cited_theses, references_section


@pytest.fixture
def uploader(db):
    return User.objects.create_user(
        email='cite.up@pampangastateu.edu.ph', first_name='Up', last_name='Loader',
        role=Role.STUDENT, password='Test12345!Test',
    )


@pytest.fixture
def make_thesis(db):
    counter = {'n': 0}

    def _make(uploaded_by, title, authors=('Dela Cruz, Juan',), year=2022,
              status=ThesisStatus.APPROVED, text=''):
        counter['n'] += 1
        n = counter['n']
        t = Thesis(
            title=title, abstract=f'Abstract for {title}.', authors=list(authors),
            keywords=['x'], program=Program.BSIT.value, year=year,
            file_type=FileType.PDF, sha256=(f'{n:x}' + 'e' * 64)[:64],
            status=status, uploaded_by=uploaded_by, extracted_text=text,
        )
        t.uploaded_file.save(f'ct_{n}.pdf', ContentFile(b'%PDF-1.4\n%x'), save=False)
        t.save()
        return t

    return _make


REFS = """Chapter 1 ... body text ...
REFERENCES
Manalo, P. (2021). Smart Parking Availability Detection Using Ultrasonic Sensors. PSU.
Garcia, L. et al. 2022, A mobile app for something else entirely.
"""


def test_title_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors',
                        authors=['Manalo, Paolo'], year=2021)
    out = find_cited_theses(REFS)
    assert out == [{'id': str(cited.id), 'title': cited.title, 'year': 2021, 'match': 'title'}]


def test_author_year_match(uploader, make_thesis):
    cited = make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2022)
    assert find_cited_theses(REFS) == [
        {'id': str(cited.id), 'title': cited.title, 'year': 2022, 'match': 'author_year'},
    ]


def test_author_year_needs_same_line(uploader, make_thesis):
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2019)
    assert find_cited_theses(REFS) == []


def test_short_surname_ignored(uploader, make_thesis):
    make_thesis(uploader, 'Some Other Thesis Title', authors=['Li, Wei'], year=2022)
    assert find_cited_theses('REFERENCES\nLi, W. (2022). Unrelated.') == []


def test_excludes_self_and_unapproved(uploader, make_thesis):
    me = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'],
                year=2022, status=ThesisStatus.PENDING_REVIEW)
    assert find_cited_theses(REFS, exclude_id=me.id) == []


def test_no_heading_uses_tail(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    text = ('body ' * 400) + 'Smart Parking Availability Detection Using Ultrasonic Sensors'
    assert [c['id'] for c in find_cited_theses(text)] == [str(cited.id)]


def test_empty_text(db):
    assert find_cited_theses('') == []
    assert references_section('') == ''


def test_last_heading_wins():
    text = 'Contents\nReferences ... 88\nbody\nReferences\nthe real list'
    assert references_section(text).strip() == 'the real list'


def test_pair_is_unique_and_not_self(uploader, make_thesis):
    a = make_thesis(uploader, 'Thesis A title words')
    b = make_thesis(uploader, 'Thesis B title words')
    ThesisCitation.objects.create(citing=a, cited=b)
    with pytest.raises(IntegrityError):
        ThesisCitation.objects.create(citing=a, cited=b)


def test_self_citation_rejected(uploader, make_thesis):
    a = make_thesis(uploader, 'Thesis A title words')
    with pytest.raises(IntegrityError):
        ThesisCitation.objects.create(citing=a, cited=a)
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -v`
Expected: collection error, `ImportError: cannot import name 'ThesisCitation'`.

- [ ] **Step 3: Add the model**

Append to `backend/theses/models.py`, after the `Thesis` class:
```python
class ThesisCitation(models.Model):
    """One repository thesis citing another, like Google Scholar's "Cited by".

    Only citations whose ``citing`` thesis is approved count toward a total.
    """

    class Source(models.TextChoices):
        DETECTED = 'detected', 'Detected from references'
        MANUAL = 'manual', 'Added manually'

    citing = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name='citations_made')
    cited = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name='citations_received')
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.DETECTED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['citing', 'cited'], name='thesis_citation_unique_pair'),
            models.CheckConstraint(check=~models.Q(citing=models.F('cited')), name='thesis_citation_not_self'),
        ]

    def __str__(self) -> str:
        return f'{self.citing_id} cites {self.cited_id}'
```
If `settings` is not already imported in `models.py`, add `from django.conf import settings`. Check how `uploaded_by` references the user model and use the same form.

- [ ] **Step 4: Make the migration**

Run: `./venv/Scripts/python.exe manage.py makemigrations theses -n thesiscitation`
Expected: `theses/migrations/0010_thesiscitation.py` created with `CreateModel ThesisCitation` and two constraints.

- [ ] **Step 5: Write the service**

`backend/theses/services/citations.py`:
```python
"""Find repository theses cited in a thesis's reference list.

Two signals, strongest first:
  title        — the cited thesis's title (first 8 words, at least 4) appears in
                 the references text after normalising case and punctuation.
  author_year  — the cited thesis's first-author surname (4+ characters) and
                 its year appear on the same reference line.
Only approved theses are candidates. The uploader confirms which are real.
"""

from __future__ import annotations

import re

from theses.models import Thesis, ThesisStatus

_HEADING = re.compile(r'(?im)^\s*(references|bibliography|literature cited)\s*$')
_NON_WORD = re.compile(r'[^a-z0-9 ]+')


def _norm(text: str) -> str:
    return ' '.join(_NON_WORD.sub(' ', (text or '').lower()).split())


def references_section(text: str) -> str:
    """Text after the LAST references heading (a table of contents can list one
    earlier); the final 20% of the text when there is no heading."""
    text = text or ''
    headings = list(_HEADING.finditer(text))
    if headings:
        return text[headings[-1].end():]
    return text[int(len(text) * 0.8):]


def _surname(thesis: Thesis) -> str:
    first = (thesis.authors or [''])[0]
    return _norm(first.split(',')[0])


def find_cited_theses(text: str, exclude_id=None) -> list[dict]:
    refs = references_section(text)
    if not refs.strip():
        return []
    refs_norm = f' {_norm(refs)} '
    lines = [f' {_norm(line)} ' for line in refs.splitlines()]

    # ponytail: scans every approved thesis per upload; fine at hundreds of theses.
    candidates = Thesis.objects.filter(status=ThesisStatus.APPROVED).only('id', 'title', 'year', 'authors')
    if exclude_id:
        candidates = candidates.exclude(id=exclude_id)

    found = []
    for thesis in candidates.order_by('title'):
        words = _norm(thesis.title).split()
        if len(words) >= 4 and f" {' '.join(words[:8])} " in refs_norm:
            match = 'title'
        else:
            surname, year = _surname(thesis), str(thesis.year)
            if len(surname) < 4 or not any(f' {surname} ' in line and f' {year} ' in line for line in lines):
                continue
            match = 'author_year'
        found.append({'id': str(thesis.id), 'title': thesis.title, 'year': thesis.year, 'match': match})
    return found
```

- [ ] **Step 6: Register in admin so wrong links can be fixed**

In `backend/theses/admin.py`, import `ThesisCitation` next to the other model imports, and append:
```python
@admin.register(ThesisCitation)
class ThesisCitationAdmin(admin.ModelAdmin):
    list_display = ('citing', 'cited', 'source', 'created_by', 'created_at')
    list_filter = ('source',)
    search_fields = ('citing__title', 'cited__title')
    raw_id_fields = ('citing', 'cited', 'created_by')
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -v`
Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/theses/models.py backend/theses/migrations/0010_thesiscitation.py backend/theses/admin.py backend/theses/services/citations.py backend/theses/tests/test_citations.py
git commit -m "Thesis citation links and reference-list detection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Citation API (upload candidates, `citations/` endpoint, `cited_by_count`)

**Files:**
- Modify: `backend/theses/views.py` (`_process_synchronous` Step 8 response ~`:1189`; new `ThesisCitationsView`)
- Modify: `backend/theses/urls.py`
- Modify: `backend/theses/serializers.py` (`ThesisListItemSerializer`)
- Test: `backend/theses/tests/test_citations.py` (append)

**Interfaces:**
- Consumes: `ThesisCitation` and `find_cited_theses` from Task 6.
- Produces:
  - The upload response gains `cited_candidates: list[dict]` (same shape as `find_cited_theses`).
  - `GET /api/v1/theses/<id>/citations/` → `{"count": int, "cited_by": [{"id", "title", "year"}]}`.
  - `POST` to the same URL, body `{"cited_ids": [str]}` → `{"count_saved": int}`. URL name: `thesis-citations`.
  - List items gain `cited_by_count: int`.

- [ ] **Step 1: Append the failing tests**

Add to `backend/theses/tests/test_citations.py`:
```python
from django.urls import reverse


def _bearer(user):
    from auth_service.services import issue_token_pair
    return issue_token_pair(user, request=None, remember_me=False).access_token


def _auth(user):
    return {'HTTP_AUTHORIZATION': f'Bearer {_bearer(user)}'}


@pytest.fixture
def other(db):
    return User.objects.create_user(
        email='cite.other@pampangastateu.edu.ph', first_name='Ot', last_name='Her',
        role=Role.STUDENT, password='Test12345!Test',
    )


def _post(client, user, thesis, ids):
    return client.post(
        reverse('thesis-citations', args=[thesis.id]), {'cited_ids': ids},
        content_type='application/json', **_auth(user),
    )


def test_post_saves_valid_and_skips_bad_ids(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words', status=ThesisStatus.PENDING_REVIEW)
    good = make_thesis(uploader, 'Older approved thesis words')
    pending = make_thesis(uploader, 'Pending thesis title words', status=ThesisStatus.PENDING_REVIEW)
    r = _post(client, uploader, mine, [str(good.id), str(mine.id), str(pending.id),
                                       '00000000-0000-0000-0000-000000000000', 'not-a-uuid'])
    assert r.status_code == 200
    assert r.json() == {'count_saved': 1}
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id')) == [(mine.id, good.id)]


def test_post_is_idempotent(client, uploader, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    good = make_thesis(uploader, 'Older approved thesis words')
    _post(client, uploader, mine, [str(good.id)])
    r = _post(client, uploader, mine, [str(good.id)])
    assert r.status_code == 200
    assert ThesisCitation.objects.count() == 1


def test_post_forbidden_for_other_student(client, uploader, other, make_thesis):
    mine = make_thesis(uploader, 'My new thesis title words')
    good = make_thesis(uploader, 'Older approved thesis words')
    assert _post(client, other, mine, [str(good.id)]).status_code == 403


def test_get_lists_approved_citing_only(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    a = make_thesis(uploader, 'Approved citing thesis words', year=2024)
    p = make_thesis(uploader, 'Pending citing thesis words', status=ThesisStatus.PENDING_REVIEW)
    ThesisCitation.objects.create(citing=a, cited=cited)
    ThesisCitation.objects.create(citing=p, cited=cited)
    body = client.get(reverse('thesis-citations', args=[cited.id]), **_auth(uploader)).json()
    assert body == {'count': 1, 'cited_by': [{'id': str(a.id), 'title': a.title, 'year': 2024}]}


def test_count_ignores_unapproved_citing(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    p = make_thesis(uploader, 'Pending citing thesis words', status=ThesisStatus.PENDING_REVIEW)
    ThesisCitation.objects.create(citing=p, cited=cited)
    rows = client.get(reverse('thesis-list'), **_auth(uploader)).json()['results']
    assert {r['id']: r['cited_by_count'] for r in rows}[str(cited.id)] == 0


def test_list_shows_cited_by_count(client, uploader, make_thesis):
    cited = make_thesis(uploader, 'Older approved thesis words')
    a = make_thesis(uploader, 'Approved citing thesis words')
    ThesisCitation.objects.create(citing=a, cited=cited)
    rows = client.get(reverse('thesis-list'), **_auth(uploader)).json()['results']
    assert {r['id']: r['cited_by_count'] for r in rows}[str(cited.id)] == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -v`
Expected: the new tests fail with `NoReverseMatch` for `thesis-citations` and `KeyError: 'cited_by_count'`. The Task 6 tests still pass.

- [ ] **Step 3: Add `cited_by_count` to list items**

In `backend/theses/serializers.py`, inside `ThesisListItemSerializer`, add the field:
```python
    cited_by_count = serializers.SerializerMethodField()
```
Add `'cited_by_count',` to the end of its `Meta.fields` tuple. Then add this method:
```python
    def get_cited_by_count(self, obj) -> int:
        # ponytail: one small COUNT per card (pages are 20); annotate the list
        # querysets instead if pages grow.
        return obj.citations_received.filter(citing__status=ThesisStatus.APPROVED).count()
```
Make sure `ThesisStatus` is imported from `.models` in `serializers.py`.

- [ ] **Step 4: Add the endpoint**

In `backend/theses/views.py`, add this after `ThesisDetailView`:
```python
class ThesisCitationsView(APIView):
    """``GET``: approved theses citing this one. ``POST {cited_ids}``: the uploader
    (or an administrator) confirms which repository theses this one cites."""

    permission_classes = [IsAuthenticated]
    MAX_IDS = 50

    def get(self, request, id, *args, **kwargs):
        thesis = self._get_visible(request, id)
        citing = (
            _visible_queryset(request.user)
            .filter(status=ThesisStatus.APPROVED, citations_made__cited=thesis)
            .order_by('-year', 'title')
        )
        rows = [{'id': str(t.id), 'title': t.title, 'year': t.year} for t in citing]
        return Response({'count': len(rows), 'cited_by': rows})

    def post(self, request, id, *args, **kwargs):
        from .models import ThesisCitation

        thesis = self._get_visible(request, id)
        if thesis.uploaded_by_id != request.user.id and getattr(request.user, 'role', None) != Role.ADMINISTRATOR:
            return make_error_response(
                code='FORBIDDEN', message='Only the uploader can confirm citations.',
                status=status.HTTP_403_FORBIDDEN,
            )
        ids = []
        for raw in (request.data.get('cited_ids') or [])[:self.MAX_IDS]:
            try:
                ids.append(uuid.UUID(str(raw)))
            except ValueError:
                continue
        targets = Thesis.objects.filter(id__in=ids, status=ThesisStatus.APPROVED).exclude(id=thesis.id)
        before = ThesisCitation.objects.filter(citing=thesis).count()
        ThesisCitation.objects.bulk_create(
            [ThesisCitation(citing=thesis, cited=t, created_by=request.user) for t in targets],
            ignore_conflicts=True,
        )
        return Response({'count_saved': ThesisCitation.objects.filter(citing=thesis).count() - before})

    @staticmethod
    def _get_visible(request, id):
        try:
            return _visible_queryset(request.user).get(id=id)
        except (Thesis.DoesNotExist, ValueError, DjangoValidationError):
            raise Http404
```
Check the imports at the top of `views.py` for `uuid`, `Http404` and `DjangoValidationError` (`from django.core.exceptions import ValidationError as DjangoValidationError`). Add only the ones that are missing. Also look at how `ThesisDetailView.get` resolves a thesis: if it has a helper for that, reuse it instead of `_get_visible`.

In `backend/theses/urls.py`, import `ThesisCitationsView` and add this next to the other `<str:id>/…` routes:
```python
    path('<str:id>/citations/', ThesisCitationsView.as_view(), name='thesis-citations'),
```

- [ ] **Step 5: Return candidates from the upload**

In `ThesisUploadView._process_synchronous`, replace the Step 8 return (~`:1189`):
```python
        # Step 8: respond with the detail shape, plus repository theses this
        # one appears to cite. The uploader confirms them on the success screen.
        from .services.citations import find_cited_theses

        data = ThesisDetailSerializer(thesis).data
        try:
            data['cited_candidates'] = find_cited_theses(thesis.extracted_text, exclude_id=thesis.id)
        except Exception as exc:  # pragma: no cover - detection must never fail an upload
            logger.warning('Thesis %s citation detection failed: %s', thesis.id, exc)
            data['cited_candidates'] = []
        return Response(data, status=status.HTTP_201_CREATED)
```

- [ ] **Step 6: Run tests to verify they pass, plus the existing upload and list suites**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py theses/tests/test_thesis_list_keyword.py theses/tests/test_thesis_list_ids.py theses/tests/test_thesis_list_mine.py theses/tests/test_thesis_gate_integration.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/theses/views.py backend/theses/urls.py backend/theses/serializers.py backend/theses/tests/test_citations.py
git commit -m "Citation API: upload candidates, /citations/ endpoint, cited_by_count on cards

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `detect_citations` command for existing theses

**Files:**
- Create: `backend/theses/management/commands/detect_citations.py`
- Test: `backend/theses/tests/test_citations.py` (append)

**Interfaces:**
- Consumes: `find_cited_theses` and `ThesisCitation` (Task 6).
- Produces: `manage.py detect_citations [--apply]`. It is a dry run by default. `--apply` stores **title** matches only, with `source='detected'` and `created_by=None`.

- [ ] **Step 1: Append the failing tests**

```python
from io import StringIO

from django.core.management import call_command


def test_detect_citations_dry_run_and_apply(uploader, make_thesis):
    cited = make_thesis(uploader, 'Smart Parking Availability Detection Using Ultrasonic Sensors', year=2021)
    make_thesis(uploader, 'Barangay Health Records Portal', authors=['Garcia, Liza'], year=2022)
    citing = make_thesis(uploader, 'Newer thesis that cites things', text=REFS)

    out = StringIO()
    call_command('detect_citations', stdout=out)
    assert ThesisCitation.objects.count() == 0
    assert 'title' in out.getvalue() and 'author_year' in out.getvalue()

    call_command('detect_citations', '--apply', stdout=StringIO())
    assert list(ThesisCitation.objects.values_list('citing_id', 'cited_id')) == [(citing.id, cited.id)]

    call_command('detect_citations', '--apply', stdout=StringIO())   # re-run is safe
    assert ThesisCitation.objects.count() == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py::test_detect_citations_dry_run_and_apply -v`
Expected: FAIL with `CommandError: Unknown command: 'detect_citations'`.

- [ ] **Step 3: Write the command**

`backend/theses/management/commands/detect_citations.py`:
```python
"""Find citations between theses already in the repository.

Dry run by default: prints every candidate. ``--apply`` stores title matches
only: there is no uploader to confirm the weaker author-year matches.
"""

from django.core.management.base import BaseCommand

from theses.models import Thesis, ThesisCitation, ThesisStatus
from theses.services.citations import find_cited_theses


class Command(BaseCommand):
    help = 'Detect citations between existing approved theses (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Store title matches.')

    def handle(self, *args, apply=False, **options):
        title_matches = 0
        for thesis in Thesis.objects.filter(status=ThesisStatus.APPROVED).exclude(extracted_text=''):
            for cand in find_cited_theses(thesis.extracted_text, exclude_id=thesis.id):
                self.stdout.write(f'{cand["match"]:11} {thesis.title[:50]!r} -> {cand["title"][:50]!r}')
                if cand['match'] == 'title':
                    title_matches += 1
                    if apply:
                        ThesisCitation.objects.get_or_create(citing=thesis, cited_id=cand['id'])
        verb = 'Stored' if apply else 'Would store (run with --apply)'
        self.stdout.write(self.style.SUCCESS(f'{verb}: {title_matches} title match(es).'))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/Scripts/python.exe -m pytest theses/tests/test_citations.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/theses/management/commands/detect_citations.py backend/theses/tests/test_citations.py
git commit -m "detect_citations command for theses already in the repository

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Citation UI (upload checklist, "Cited by" on cards and detail)

**Files:**
- Modify: `frontend/src/components/upload/UploadThesisModal.jsx` (success screen, ~`:713–770`)
- Modify: `frontend/src/pages/RepositoryPage.jsx:255-257` (card meta line)
- Modify: `frontend/src/pages/ThesisDetailPage.jsx` (after the Keywords block, ~`:545`)

**Interfaces:**
- Consumes:
  - `success.cited_candidates` from the upload response
  - `GET`/`POST /theses/:id/citations/`
  - `thesis.cited_by_count` on list items (all from Task 7)

- [ ] **Step 1: Show the checklist on the upload success screen**

In `UploadThesisModal.jsx`:

1. Add `CitedChecklist` above the default export:
```jsx
// Repository theses this upload appears to cite. Title matches start ticked;
// author-year matches are weaker and start unticked. Nothing is stored until
// the uploader presses Save.
function CitedChecklist({ thesisId, candidates }) {
  const [picked, setPicked] = useState(
    () => new Set(candidates.filter((c) => c.match === 'title').map((c) => c.id)),
  );
  const [state, setState] = useState('idle'); // idle | saving | saved | error

  const toggle = (id) => setPicked((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const save = async () => {
    setState('saving');
    try {
      await client.post(`/theses/${thesisId}/citations/`, { cited_ids: [...picked] });
      setState('saved');
    } catch {
      setState('error');
    }
  };

  return (
    <section className="mt-6 text-left border-t border-border-default pt-5" aria-labelledby="cited-heading">
      <h3 id="cited-heading" className="text-sm font-semibold text-ink">Repository theses cited in this paper</h3>
      <p className="text-xs text-muted mt-1 mb-3">Found in your reference list. Untick any you did not cite.</p>
      <ul className="space-y-2 max-h-48 overflow-y-auto">
        {candidates.map((c) => (
          <li key={c.id}>
            <label className="flex items-start gap-2.5 text-sm text-body cursor-pointer">
              <input type="checkbox" className="mt-0.5 accent-blue-600" checked={picked.has(c.id)}
                onChange={() => toggle(c.id)} disabled={state === 'saving' || state === 'saved'} />
              <span>{c.title} <span className="text-muted tabular-nums">({c.year})</span></span>
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-center gap-3">
        <button type="button" onClick={save} disabled={state === 'saving' || state === 'saved' || picked.size === 0}
          className="px-3 py-1.5 rounded-lg bg-primary-solid text-white text-sm font-semibold hover:bg-primary-solid-hover disabled:opacity-60 transition-colors">
          {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved' : 'Save citations'}
        </button>
        {state === 'error' && <span className="text-xs text-danger">Couldn't save. Try again.</span>}
      </div>
    </section>
  );
}
```
2. In the success screen, right after the buttons `</m.div>` (the `flex flex-col sm:flex-row gap-3 justify-center` block), add:
```jsx
            {success.cited_candidates?.length > 0 && (
              <CitedChecklist thesisId={success.id} candidates={success.cited_candidates} />
            )}
```
`client` and `useState` are already imported in this file. Confirm both before adding them.

- [ ] **Step 2: "Cited by N" on Repository cards**

`RepositoryPage.jsx:255-257`:
```jsx
      <div className={`text-xs mb-3 text-muted`}>
        {thesis.program} · {thesis.year}
        {thesis.cited_by_count > 0 && <> · Cited by {thesis.cited_by_count}</>}
      </div>
```

- [ ] **Step 3: "Cited by" section on the thesis page**

In `ThesisDetailPage.jsx`:

1. Add state next to the other `useState` calls:
```jsx
  const [citedBy, setCitedBy] = useState(null);
```
2. Add an effect next to the subject-suggestions effect (~`:151`):
```jsx
  useEffect(() => {
    let alive = true;
    setCitedBy(null);
    client.get(`/theses/${id}/citations/`)
      .then((res) => { if (alive) setCitedBy(res.data); })
      .catch(() => { if (alive) setCitedBy({ count: 0, cited_by: [] }); });
    return () => { alive = false; };
  }, [id]);
```
3. Right after the Keywords `<div className="flex flex-wrap gap-1.5 mb-6">…</div>` block ends, add:
```jsx
            {citedBy && (
              <section className="mb-6" aria-labelledby="cited-by-heading">
                <h2 id="cited-by-heading" className={`text-sm font-semibold uppercase tracking-wider mb-2 text-body`}>
                  Cited by {citedBy.count}
                </h2>
                {citedBy.count === 0 ? (
                  <p className="text-sm text-muted">Not cited by other theses in the repository yet.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {citedBy.cited_by.map((t) => (
                      <li key={t.id} className="text-sm">
                        <Link to={`/repository/${t.id}`} className="text-primary hover:underline">{t.title}</Link>
                        <span className="text-muted tabular-nums"> · {t.year}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
```
If `Link` is not imported in `ThesisDetailPage.jsx`, add it to the existing `react-router-dom` import.

- [ ] **Step 4: Migrate the test database and check in the browser**

1. Apply the migration on the shared local Postgres. It only adds a table and is safe for the user's running demo, but **ask the user before running it**:
   `./venv/Scripts/python.exe manage.py migrate theses` (from `backend/`).
2. Use the test servers (8001/5174), with the user signed in:
   - **Thesis page:** open any thesis. It shows "Cited by 0" and the empty-state sentence.
   - **Admin:** in Django admin on 8001, add one `ThesisCitation` between two approved theses. The cited thesis's page then shows "Cited by 1" with a working link, and its Repository card shows "· Cited by 1".
   - **Upload checklist:** upload a test PDF whose last page lists an existing title under "REFERENCES". The success screen shows the checklist with that title ticked. Save turns the button into "Saved", and the cited thesis's count goes up.
   - **Cleanup:** delete the test upload and the admin-made link afterwards.
3. Run `read_console_messages` with `onlyErrors`. Expected: none.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/upload/UploadThesisModal.jsx frontend/src/pages/RepositoryPage.jsx frontend/src/pages/ThesisDetailPage.jsx
git commit -m "Show 'Cited by' on cards and thesis pages; confirm citations after upload

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Full verification

- [ ] **Step 1: Run the whole backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Compare against a run on `main` before Task 1 if anything unrelated fails, and report pre-existing failures as such.

- [ ] **Step 2: Build the frontend**

Run (from `frontend/`): `npx vite build`
Expected: the build finishes with no errors.

- [ ] **Step 3: Clean up the test servers**

Stop only the `test-backend` and `test-frontend` preview servers, then confirm 8000 and 5173 are still listening:
`powershell -c "Get-NetTCPConnection -State Listen | ? LocalPort -in 8000,5173 | select LocalPort"`
