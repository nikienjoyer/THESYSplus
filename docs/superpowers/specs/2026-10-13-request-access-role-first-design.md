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
member submits name, institutional email and program, an admin approves them,
and they set a password from the emailed link. Works at 375px and 1280px+,
light and dark.

## Decisions made with the user

| Item | Decision |
|---|---|
| Faculty verification | Admin review only. No upload. |
| Faculty email | `@pampangastateu.edu.ph`, local part **not** all digits (e.g. `kurtross@…`). Student emails stay all digits (e.g. `2023313528@…`). |
| Faculty extra field | Program dropdown: BSIS / BSIT / BSCS. |
| Where the choice lives | First screen of `/request-access`, kept in the URL as `?role=`. |
| UI design | Done with `/impeccable:impeccable`. |
| Plan execution | `/superpowers:executing-plans`. |

## 1. Screens (frontend)

`RequestAccessPage` reads `role` from the query string (`useSearchParams`).

- **No `role`** → role picker: two cards, "I'm a Student" (hint: upload your
  Student ID or COR) and "I'm a Faculty member" (hint: an administrator reviews
  your request). Each card is a button that sets `?role=student|faculty`.
- **`role=student`** → today's `RequestAccessForm`, minus the role radio. It
  sends `requested_role=student` as before.
- **`role=faculty`** → new `FacultyRequestForm`: First name, Last name,
  Institutional email (placeholder `kurtross@pampangastateu.edu.ph`), Program
  `<select>` (BSIS / BSIT / BSCS), Terms checkbox, submit. Sent as JSON.
- Any other `role` value → treated as no role (picker).
- Both forms show "← Change" which clears `role` (back to the picker).
- The stepper is shown on the forms, not on the picker. For faculty, after
  submit, the stepper is the existing manual-review variant (Submit Request →
  Manual Review → Set Password → Account Ready).
- After submit, both roles use the existing decision/claim screens. Faculty land
  on "Your request needs manual review", which already polls for the admin's
  decision. A stored claim (reload while waiting) wins over `role`.
- Visual design of the picker and faculty form is decided with
  `/impeccable:impeccable`, matching the current auth pages (`AuthLayout`,
  `thesys-input`, `bg-primary-solid` buttons, tokens from `DESIGN.md`).

Frontend email rules mirror the backend:
- Student: `/^[0-9]+@pampangastateu\.edu\.ph$/i` (unchanged).
- Faculty: `/^(?![0-9]+@)[^@\s]+@pampangastateu\.edu\.ph$/i`.

## 2. Backend (`access_requests`)

**Model.** `AccessRequest.program = CharField(max_length=40, choices=Program.choices, null=True, blank=True)`,
reusing `theses.models.Program`. One migration.

**Serializer / view.** The role picks the branch, not the presence of a file:

| `requested_role` | Must send | Email rule | Branch |
|---|---|---|---|
| `student` | `document` | `is_student_number_email` | `_handle_document_upload` (unchanged) |
| `faculty` | `program` | `is_institutional_email` and not `is_student_number_email` | `_handle_legacy_justification`, renamed `_handle_faculty_request`, stores `program`, `status='pending'` |

- Allowed fields: student `{email, first_name, last_name, requested_role, document}`;
  faculty `{email, first_name, last_name, requested_role, program}`. Others → existing unknown-field error.
- `justification` is no longer accepted. The column stays (old rows keep it).
- Student without document → `400 DOCUMENT_REQUIRED`.
- Faculty with all-digit email → `400 FACULTY_EMAIL_LOOKS_LIKE_STUDENT`.
- Faculty without/with invalid program → `400 INVALID_PROGRAM`.
- Rate limits, duplicate-pending and already-registered checks run as today for both roles.
- Response for faculty adds `decision: 'pending_manual_review'` so the frontend
  doesn't rely on its fallback.

**Admin.** `program` added to `AccessRequestListItemSerializer` fields and to
the Django admin `list_display`, `list_filter` and detail `fields`. Approval is
unchanged: approve → set-password email → owner of the address finishes signup.

## 3. Errors shown to the user

| Code | Message |
|---|---|
| `FACULTY_EMAIL_LOOKS_LIKE_STUDENT` | "This looks like a student email. Request access as a Student instead." with a link to `?role=student` |
| `INVALID_PROGRAM` | "Choose your program." |
| `DOCUMENT_REQUIRED` | "Please upload your PampangaStateU Student ID or COR." |
| `INVALID_EMAIL_DOMAIN` (faculty) | "Use your PampangaStateU email (e.g. kurtross@pampangastateu.edu.ph)." |

## 4. Testing

Backend pytest (`access_requests/tests/`):
- Faculty: valid email + program → 201, `status='pending'`, `program` saved.
- Faculty: all-digit email → 400 `FACULTY_EMAIL_LOOKS_LIKE_STUDENT`.
- Faculty: missing / unknown program → 400 `INVALID_PROGRAM`.
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
