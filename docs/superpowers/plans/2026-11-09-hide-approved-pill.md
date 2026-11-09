# Hide the "Approved" pill on repository cards

**Why:** Panel recommendation. Approved is the default state of the repository, so the green pill says nothing new and takes width a long title needs. "Pending review" (and "Rejected") still show, because those are the exceptions.

**Scope:** One file, `frontend/src/pages/RepositoryPage.jsx`. About 10 minutes plus a browser check.

## Steps

1. In `ThesisCard` (around line 253), render the status `<Badge>` only when `thesis.status !== 'approved'`.
2. Remove the `approved` entry from `statusVariantClass` (line 161) since nothing uses it anymore.
3. Leave the `%  match` badge as is. When neither badge shows, the right-side wrapper is empty and takes no width, so the title fills the row.
4. Check in the browser (8001/5174 test setup, logged in):
   - Approved card: no pill, title runs full width, still clamps at 2 lines.
   - Pending review card (admin/faculty view): yellow pill still shows.
   - Search with a score: `% match` badge still shows on approved cards.
   - Phone width (375px): no overflow.

## Out of scope

- Thesis detail page status display: unchanged.
- "Under review" tag on cited theses: unchanged.
