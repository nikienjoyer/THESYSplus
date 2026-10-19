# Request Access: Student or Faculty First — Design

Date: 2026-10-13
Source: panel feedback item 2 ("Ask Student or Faculty first"), see
[`2026-10-05-panel-feedback-design.md`](2026-10-05-panel-feedback-design.md).
The panel has not answered yet; this design is the team's own proposal.

## Goal

Clicking Request Access first asks "Student or Faculty?", then shows a form for
that role. Today faculty cannot get through at all: the form demands a
student-number email and a Student ID/COR upload, and the backend enforces both.

Success means: a student completes today's ID-upload flow unchanged; a faculty
member submits name and institutional email, an admin approves them,
and they set a password from the emailed link. Works at 375px and 1280px+,
light and dark.

## Decisions made with the user

| Item | Decision |
|---|---|
| Faculty verification | Admin review only. No upload. |
| Faculty email | `@pampangastateu.edu.ph`, local part **not** all digits (e.g. `firstname.lastname@…`). Student emails stay all digits (e.g. `2024000000@…`). |
| Faculty extra field | None. Faculty teach across programs, so no program is asked. |
| Where the choice lives | First screen of `/request-access`, kept in the URL as `?role=`. |
| UI design | Done with `/impeccable:impeccable`. |
| Plan execution | `/superpowers:executing-plans`. |

## 1. Screens (frontend)

`RequestAccessPage` reads `role` from the query string (`useSearchParams`).

- **No `role`** → role picker (distilled 2026-10-19): heading "Who is requesting
  access?", one line "Students and faculty sign up differently.", then one
  bordered list with two rows divided by a hairline. Each row is a button with
  an icon, a title and one muted line, and sets `?role=student|faculty`:
  - **Student**: "Student-number email and your Student ID or COR"
  - **Faculty**: "PampangaStateU email. An administrator approves it."
  No bullet lists and no sample email addresses on the picker. Examples
  elsewhere use placeholders only (`2024000000@…`, `firstname.lastname@…`,
  "Maria Santos"), never real accounts.
- **`role=student`** → today's `RequestAccessForm`, minus the role radio. It
  sends `requested_role=student` as before.
- **`role=faculty`** → new `FacultyRequestForm`: First name, Last name,
  PampangaStateU email (placeholder `firstname.lastname@pampangastateu.edu.ph`), Terms
  checkbox, "Submit for Review". Sent as JSON.
- Any other `role` value → treated as no role (picker).
- Both forms show "← Change" which clears `role` (back to the picker).
- The stepper is shown on the forms, not on the picker. For faculty, after
  submit, the stepper reads Submit Request → Admin Review → Set Password →
  Account Ready (from the start of the faculty form, not only after submit).
- After submit, both roles use the existing decision/claim screens. Faculty land
  on the manual-review panel, retitled for faculty "Waiting for an administrator",
  which already polls for the admin's decision. A stored claim (reload while waiting) wins over `role`.
- Visual design of the picker and faculty form is decided with
  `/impeccable:impeccable`. Approved mockup:
  [`mockups/2026-10-13-request-access-role-first.html`](mockups/2026-10-13-request-access-role-first.html)
  (serve with the `mockups` launch config, port 5180). Match the current auth pages (`AuthLayout`,
  `thesys-input`, `bg-primary-solid` buttons, tokens from `DESIGN.md`).

Frontend email rules mirror the backend:
- Student: `/^[0-9]+@pampangastateu\.edu\.ph$/i` (unchanged).
- Faculty: `/^(?![0-9]+@)[^@\s]+@pampangastateu\.edu\.ph$/i`.

## 2. Backend (`access_requests`)

**Model.** No change. No migration.

**Serializer / view.** The role picks the branch, not the presence of a file:

| `requested_role` | Must send | Email rule | Branch |
|---|---|---|---|
| `student` | `document` | `is_student_number_email` | `_handle_document_upload` (unchanged) |
| `faculty` | nothing extra | `is_institutional_email` and not `is_student_number_email` | `_handle_legacy_justification`, renamed `_handle_faculty_request`, `status='pending'` |

- Allowed fields: student `{email, first_name, last_name, requested_role, document}`;
  faculty `{email, first_name, last_name, requested_role}`. Others → existing unknown-field error.
- `justification` is no longer accepted. The column stays (old rows keep it).
- Student without document → `400 DOCUMENT_REQUIRED`.
- Faculty with all-digit email → `400 FACULTY_EMAIL_LOOKS_LIKE_STUDENT`.
- Rate limits, duplicate-pending and already-registered checks run as today for both roles.
- Response for faculty adds `decision: 'pending_manual_review'` so the frontend
  doesn't rely on its fallback.

**Admin.** No change; Django admin already filters by `requested_role`. Approval is
unchanged: approve → set-password email → owner of the address finishes signup.

## 3. Errors shown to the user

| Code | Message |
|---|---|
| `FACULTY_EMAIL_LOOKS_LIKE_STUDENT` | "This looks like a student email. Request access as a Student instead." with a link to `?role=student` |
| `DOCUMENT_REQUIRED` | "Please upload your PampangaStateU Student ID or COR." |
| `INVALID_EMAIL_DOMAIN` (faculty) | "Use your PampangaStateU email (e.g. firstname.lastname@pampangastateu.edu.ph)." |

## 4. Testing

Backend pytest (`access_requests/tests/`):
- Faculty: valid email → 201, `status='pending'`, `requested_role='faculty'`.
- Faculty: all-digit email → 400 `FACULTY_EMAIL_LOOKS_LIKE_STUDENT`.
- Faculty: sends `document` → 400 unknown field.
- Student: no document → 400 `DOCUMENT_REQUIRED`.
- Existing student/document tests still pass; legacy-justification tests are
  rewritten for the faculty branch.

Frontend: existing test suite passes.

Browser check on 8001/5174 (never 8000/5173): picker → each form → back link;
faculty submit → approve in Django admin → set-password link → sign in. Phone
and desktop widths, light and dark.

## Out of scope

- Automatic faculty ID checks.
- Departments outside CCS.
- A custom admin review page in the React app (Django admin is the review tool).
