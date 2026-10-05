# Panel Feedback — Design

Date: 2026-10-05
Source: panelist sticky notes from the THESYS+ defense (Madam P, Ms. Angel, Sir JQ, and others).

## Goal

Address six panel comments without changing how the system's core search,
similarity, and trend features work:

1. Pages and navbar feel cramped in the middle → spread them out, and make them responsive.
2. ~~Ask "Student or Faculty?" first~~ — on hold; the team is consulting the panel first.
3. Put Sign In on the landing page instead of behind a separate button.
4. Show suggestions while typing in search.
5. Use "title similarity" instead of "originality".
6. Show a thesis citation count, like Google Scholar's "Cited by N".

Success means each item is visible in the running app, works at phone (375px),
tablet (768px), laptop (1280px) and wide (1920px) widths in light and dark mode,
and leaves existing tests passing.

## Decisions made with the user

| Item | Decision |
|---|---|
| Citations | Auto-detect from the uploaded thesis's reference list, then the uploader confirms which ones they really cited. |
| Sign In | Sign-in form sits on the right side of the landing hero for logged-out visitors. The navbar Sign In button is removed. |
| Suggestions | Signed-in users get titles, keywords, and authors. Logged-out users get keywords only (no titles), keeping the existing privacy rule. |
| Faculty flow | On hold. Not part of this work. |

## 1. Layout and navbar spacing

**Problem.** `PageShell` and the landing `CONTAINER` cap content at `max-w-6xl`
(1152px). The navbar's five links sit in a tight `gap-1` cluster. On laptop and
wide screens everything bunches in the center.

**Change.**
- `PageShell` and the landing `CONTAINER` go from `max-w-6xl` to `max-w-7xl`
  (1280px), and to `2xl:max-w-[1440px]` above 1536px. Narrow task pages
  (Settings, Title Similarity, Thesis Detail) keep their own inner `max-w-*`.
- Navbar links (`AppNavbar` and the landing page's copy): `gap-1` → `gap-1 xl:gap-3`,
  and the link padding grows from `px-3` to `xl:px-4`. The bar's side padding is
  unchanged, so the logo still lines up with page content.
- Responsiveness audit: open every page at 375/768/1280/1920 in both themes. Fix
  horizontal overflow, cramped grids, and tap targets under 40px. Each fix is a
  class change in that page; no new layout components.

## 2. Student or Faculty first — on hold

The team is checking with the panel before any changes. No request-access changes in this work.

## 3. Sign In on the landing page

- Logged-out visitors at `lg+`: the CCS building photo stays as the hero
  background. The headline, paragraph, search, and Title Similarity button stay
  on the left. A frosted sign-in card sits bottom-right **on top of** the photo:
  translucent background with `backdrop-filter: blur(8px)`, a light border, and
  bottom alignment so the "College of Computing Studies" sign stays visible
  above it. The card is dark glass in dark mode and white glass in light mode.
  It holds the existing `SignInCard` fields plus "Forgot password?" and
  "Request access" links. The scrim fades out by about 66% across, so the
  building reads clearly behind the card.
  Mockup: `shot-low.png` (dark) and `shot-low-light.png` (light).
- Below `lg`: the panel stacks under the hero text, still inside the hero.
- The navbar Sign In buttons (desktop, mobile, and drawer) are removed for
  logged-out visitors. On mobile the drawer gets a "Sign in" link that scrolls
  to the panel (`#sign-in`).
- On success the visitor stays on `/`, which switches to its signed-in state:
  the panel disappears and Upload Thesis plus the avatar appear.
- The `/sign-in` page stays. It's where session-expired, password-set, and
  account-setup redirects land.
- The sign-in error mapping moves out of `SignInPage.jsx` into
  `components/auth/` so the page and the hero panel share it.

## 4. Search suggestions

**Endpoint.** `GET /api/v1/theses/suggest/?q=<text>`, `AllowAny`, throttled
like the other public endpoints. When `q` is shorter than 2 characters, all
three lists come back empty.

```json
{ "titles":   [{ "id": "…", "title": "…", "year": 2023 }],
  "keywords": ["machine learning", "…"],
  "authors":  ["Dela Cruz, Juan"] }
```

- `titles` and `authors` come from `_visible_queryset(request.user)` and are
  only filled for authenticated users. Logged-out users get `titles: []` and
  `authors: []`.
- `keywords` come from approved theses only, for every user.
- Matching is case-insensitive substring (`icontains` on title; Python filter
  over keywords and authors). Up to 5 titles, 5 keywords, and 3 authors.
  ponytail: an in-memory keyword/author scan, fine at hundreds of theses; move
  to a Postgres trigram index if the corpus reaches tens of thousands.

**UI.** One `SearchSuggestions` component, used in the landing hero search and
the Repository search input.
- Debounced 200ms, with the request cancelled when the user types again.
- ARIA combobox: the input has `role="combobox"` and `aria-expanded`; the list
  has `role="listbox"`. ↑/↓ move, Enter picks, Esc closes.
- Grouped under small labels: Theses, Keywords, Authors.
- Picking a thesis opens `/repository/:id`. Picking a keyword or author fills
  the input and submits the search.
- Empty results close the list. Errors are ignored silently, since suggestions
  are only a convenience.

## 5. "Originality" → "Title similarity"

The app already calls the tool "Title Similarity". Remaining text to change:
- `LegalModal.jsx`: "Title originality validation…" → "Title similarity validation…".
- Landing feature card: "…so your topic starts out original." → "…before you commit to a topic."
- The uncommitted landing-hero line ("check title similarity") is included.
- `seed_demo_data.py` strings and `PRODUCT.md`.
- The printed thesis manuscript has to be updated by you. It isn't in this repo.

## 6. Citation counts

**Data.** New model `ThesisCitation`:

| field | type |
|---|---|
| `citing` | FK Thesis, cascade |
| `cited` | FK Thesis, cascade |
| `source` | `detected` / `manual` |
| `created_by` | FK User, null |
| `created_at` | datetime |

Constraints: unique (`citing`, `cited`), and `citing != cited`. It is registered
in Django admin so an administrator can fix wrong links.

**Count rule.** "Cited by N" counts citations whose **citing thesis is
approved**. A rejected or pending thesis doesn't inflate anyone's count.

**Detection.** New service `theses/services/citations.py`:
- `find_cited_theses(text, exclude_id=None) -> list[dict]` locates the
  references section, using the last heading among References, Bibliography,
  or Literature Cited. If none is found, it uses the final 20% of the text.
- Title match: the cited thesis's normalized title (first 8 words, at least 4
  words) appears in the normalized references text → `match: "title"`, high
  confidence.
- Author-year match: the first author's surname (4+ characters) and the
  thesis's year appear on the same reference line → `match: "author_year"`,
  lower confidence.
- Candidates come from approved theses only.

**Upload flow.**
- `/theses/extract-metadata/` adds `cited_candidates: [{id, title, year, authors, match}]`
  to its response.
- The upload modal shows a "Repository theses cited in this paper" checklist
  when there are candidates. Title matches start ticked; author-year matches
  start unticked. The section is hidden when there are no candidates.
- `/theses/upload/` accepts `cited_thesis_ids` (a repeated form field). After
  the thesis is created it stores `ThesisCitation(source="detected", created_by=uploader)`
  for each id that exists, isn't the new thesis, and is approved. Unknown ids
  are ignored, not errors.

**Existing theses.** Management command `detect_citations [--apply]`. It is a
dry run by default and prints the candidates. With `--apply` it stores
**title matches only**, since there is no uploader to confirm the others. Your
current data has 0 title matches, so existing counts will start at 0 and grow
as new theses that cite older ones are uploaded.

**Display.**
- Thesis list/search serializer: `cited_by_count`, annotated with one
  `Count(..., filter=Q(citations_received__citing__status=APPROVED))`.
- Repository cards: "Cited by N" in the meta row, shown only when N > 0, like
  Scholar.
- Thesis Detail: a "Cited by N" section listing the citing theses (title, year,
  linking to the thesis), visible-queryset filtered. When N is 0 it shows "Not
  cited by other theses in the repository yet."

## Testing

- Backend pytest:
  - `find_cited_theses`: title match, author-year match, self-exclusion, no references heading, and a short-surname guard.
  - Suggest endpoint: anonymous users get no titles or authors; a student doesn't see others' pending theses; `q` under 2 characters returns empty.
  - Upload with `cited_thesis_ids`: valid, self, unknown, and unapproved ids.
  - `cited_by_count`: only approved citing theses count.
- Existing backend and frontend test suites still pass.
- Browser check on the side-by-side test servers (8001/5174, never 8000/5173):
  - Every page at the four widths in both themes.
  - The landing sign-in, suggestions with the keyboard, and the upload citation checklist.

## Out of scope

- Citations from outside the repository (Google Scholar, journals).
- A manual "search and add a citation" picker in the upload modal. Admin can
  add links in Django admin if needed.
- Editing the thesis manuscript document.
