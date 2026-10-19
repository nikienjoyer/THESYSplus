# Request Access: Role First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/request-access` first asks Student or Faculty, then shows that role's form; faculty submit name + email with no upload, an administrator approves, and they set a password from the existing flow.

**Architecture:** The backend branches on `requested_role` instead of on whether a file was sent: students keep the document-upload branch unchanged, faculty go to a renamed `_handle_faculty_request` that stores a `pending` request for admin review, and the claim poller reports pending faculty requests as `pending_manual_review`. The frontend reads `?role=` with `useSearchParams` and renders a new `RolePicker`, the existing `RequestAccessForm` (role radio removed) or a new `FacultyRequestForm`; everything after submit reuses the existing claim/decision screens.

**Tech Stack:** Django REST Framework + pytest (backend), React 19 + react-router + Tailwind (frontend).

**Spec:** `docs/superpowers/specs/2026-10-13-request-access-role-first-design.md`
**Approved mockup:** `docs/superpowers/specs/mockups/2026-10-13-request-access-role-first.html` (serve with the `mockups` launch config, port 5180)

## Global Constraints

- No model change, no migration. `justification` column stays; the API no longer accepts it.
- Student email: `is_student_number_email` (frontend `/^[0-9]+@pampangastateu\.edu\.ph$/i`), unchanged.
- Faculty email: `is_institutional_email(e) and not is_student_number_email(e)` (frontend `/^(?![0-9]+@)[^@\s]+@pampangastateu\.edu\.ph$/i`).
- Allowed fields: student `{email, first_name, last_name, requested_role, document}`; faculty `{email, first_name, last_name, requested_role}`. Anything else → existing `UNKNOWN_FIELD`.
- Rate limits, duplicate-pending, already-registered and verification-pending checks run for both roles, unchanged.
- Placeholders only, never real accounts: `2024000000@pampangastateu.edu.ph`, `firstname.lastname@pampangastateu.edu.ph`, "Maria" / "Santos".
- Error copy (exact):
  - `FACULTY_EMAIL_LOOKS_LIKE_STUDENT` → "This looks like a student email. Request access as a Student instead." with a link to `?role=student`
  - `DOCUMENT_REQUIRED` → "Please upload your PampangaStateU Student ID or COR."
  - `INVALID_EMAIL_DOMAIN` (faculty) → "Use your PampangaStateU email (e.g. firstname.lastname@pampangastateu.edu.ph)."
- UI matches the auth pages: `AuthLayout`, `thesys-input`, `bg-primary-solid` buttons, tokens from `DESIGN.md`; light and dark; 375px and 1280px+.
- Test only on `test-backend` (8001) and `test-frontend` (5174). Never touch 8000 or 5173.

## Review Focus

1. **Faculty reloads the page while waiting.** The stored claim must win over `?role=` and show the faculty "Waiting for an administrator" panel, not the picker or the student copy. (Task 4: `role` saved with the claim.)
2. **Faculty claim expires before the admin decides.** The poller must still say `pending_manual_review`, not `expired`. (Task 2 test `test_expired_faculty_claim_still_reports_manual_review`.)
3. **Student types a faculty-style email, or faculty types an all-digit email.** Each form shows its own inline error before any request is sent; the faculty one links to the student form. (Task 4 browser check, Task 1 server test.)
4. **Unknown `?role=` value** (`?role=admin`, `?role=`) shows the picker, never a blank page. (Task 3 browser check.)
5. **Admin approves a faculty request** → the open tab advances to Set Password through the existing `approved`/`verified` path. (Task 5 end-to-end check.)

---

### Task 1: Backend submission branches on role

**Files:**
- Modify: `backend/access_requests/serializers.py` (`RequestAccessSerializer`: drop `justification`; role-driven `validate_email`; `validate` requires `document` for students)
- Modify: `backend/access_requests/views.py:168-307` (`RequestAccessView.post`, rename `_handle_legacy_justification` → `_handle_faculty_request`)
- Test: `backend/access_requests/tests/test_faculty_request.py` (new); rewrite justification cases in `backend/access_requests/tests.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/request-access/` with JSON `{first_name, last_name, email, requested_role: 'faculty'}` → `201 {status: 'pending', decision: 'pending_manual_review', submitted_at, claim, claim_expires_at}`. Error codes `FACULTY_EMAIL_LOOKS_LIKE_STUDENT`, `DOCUMENT_REQUIRED` (400).

- [ ] **Step 1: Write the failing tests** in `test_faculty_request.py`, posting JSON to the request-access URL:

```python
def test_faculty_valid_email_creates_pending_request(client):
    # email 'maria.santos@pampangastateu.edu.ph', role 'faculty'
    assert res.status_code == 201
    assert res.json()['decision'] == 'pending_manual_review'
    req = AccessRequest.objects.get(email='maria.santos@pampangastateu.edu.ph')
    assert (req.status, req.requested_role, req.justification) == ('pending', 'faculty', None)

def test_faculty_all_digit_email_rejected(client):          # '2024000000@…'
    assert res.status_code == 400 and code(res) == 'FACULTY_EMAIL_LOOKS_LIKE_STUDENT'

def test_faculty_non_institutional_email_rejected(client):  # 'maria@gmail.com'
    assert res.status_code == 400 and code(res) == 'INVALID_EMAIL_DOMAIN'

def test_faculty_with_document_is_unknown_field(client):    # multipart with a small PNG
    assert res.status_code == 400 and code(res) == 'UNKNOWN_FIELD'

def test_justification_is_unknown_field(client):            # faculty + justification
    assert res.status_code == 400 and code(res) == 'UNKNOWN_FIELD'

def test_student_without_document_rejected(client):         # role 'student', '2024000000@…'
    assert res.status_code == 400 and code(res) == 'DOCUMENT_REQUIRED'

def test_faculty_duplicate_pending_rejected(client):        # submit twice
    assert second.status_code == 409 and code(second) == 'DUPLICATE_REQUEST_PENDING'
```

`code(res)` reads `res.json()['error']['code']`. Clear the rate-limit cache between tests the way `tests/test_claim_status.py` does.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && ./venv/Scripts/python.exe -m pytest access_requests/tests/test_faculty_request.py -v`
Expected: FAIL. Faculty without justification currently returns `MISSING_REQUIRED_FIELD`.

- [ ] **Step 3: Implement**
  - `RequestAccessSerializer`: remove the `justification` field and the either/or `validate`. `validate_email` reads `self.initial_data.get('requested_role')`. For `'faculty'`: not institutional → `INVALID_EMAIL_DOMAIN`; student-number → `FACULTY_EMAIL_LOOKS_LIKE_STUDENT`. Otherwise keep today's student rule. `validate(attrs)`: if `attrs['requested_role'] == 'student'` and no `document` → `ValidationError(..., code='DOCUMENT_REQUIRED')`.
  - `RequestAccessView.post`: `allowed_fields` comes from `request.data.get('requested_role') == 'faculty'` (faculty set), else the student set. Branch with `if v['requested_role'] == 'faculty': return self._handle_faculty_request(...)`, else `_handle_document_upload` (unchanged).
  - `_handle_faculty_request`: today's legacy body with `justification=None`, audit `flow: 'faculty_request'`, and `'decision': 'pending_manual_review'` added to the 201 body.
  - Confirm `_hoist_first_field_error` surfaces the `DOCUMENT_REQUIRED` non-field code. If it drops it, raise it as `{'document': ValidationError(..., code='DOCUMENT_REQUIRED')}` instead.

- [ ] **Step 4: Rewrite existing justification tests**

In `access_requests/tests.py`: delete the justification length and either/or serializer tests, which test a field that no longer exists. Turn `test_legacy_justification_flow_still_works` into a faculty submission. Keep every document-flow test as is.

- [ ] **Step 5: Run the app's tests**

Run: `./venv/Scripts/python.exe -m pytest access_requests -q`
Expected: all pass, except the claim-status and decision-flow helpers that still post `justification`. Task 2 fixes those.

- [ ] **Step 6: Commit** `git add backend/access_requests && git commit -m "Accept faculty access requests without a document"`

---

### Task 2: Claim poller reports pending faculty requests as manual review

**Files:**
- Modify: `backend/access_requests/views.py` (`RequestAccessStatusView.get`, the `req.status == 'pending'` branch; `_manual_review_outcome`)
- Test: `backend/access_requests/tests/test_claim_status.py`, `backend/access_requests/tests/test_decision_flow.py`

**Interfaces:**
- Consumes: Task 1's faculty submission.
- Produces: `GET …/request-access/status/?claim=` → `{status: 'pending_manual_review'}` for a pending faculty request, whether or not its claim has expired.

- [ ] **Step 1: Switch the helpers.** The `_submit` helpers in both test files post the faculty JSON body (`requested_role: 'faculty'`, `maria.santos@pampangastateu.edu.ph`, no `justification`). Then add:

```python
def test_pending_faculty_claim_reports_manual_review(client):
    assert poll(claim)['status'] == 'pending_manual_review'

def test_expired_faculty_claim_still_reports_manual_review(client):
    # set claim_expires_at in the past
    assert poll(claim)['status'] == 'pending_manual_review'
```

- [ ] **Step 2: Run to verify they fail**

Run: `./venv/Scripts/python.exe -m pytest access_requests/tests/test_claim_status.py -v`
Expected: the two new tests FAIL with `pending_verification` and `expired`.

- [ ] **Step 3: Implement `_awaits_admin(req) -> bool` in `views.py`**

It returns `req.requested_role == 'faculty' or VerificationDocument.objects.filter(access_request=req).exists()`. Use it in both the `pending` branch of `get` and `_manual_review_outcome`, in place of the document-only checks.

- [ ] **Step 4: Run all backend tests**

Run: `./venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Existing assertions that a pending request with no document is `pending_verification` now describe faculty, so update them to `pending_manual_review`.

- [ ] **Step 5: Commit** `git commit -am "Report pending faculty requests as awaiting an administrator"`

---

### Task 3: Role picker and student form behind `?role=`

**Files:**
- Create: `frontend/src/components/auth/RolePicker.jsx`
- Modify: `frontend/src/components/auth/RequestAccessForm.jsx` (remove the role radio and `role` state; always send `requested_role=student`; email error copy uses `2024000000@pampangastateu.edu.ph`)
- Modify: `frontend/src/pages/RequestAccessPage.jsx` (read `role`; render picker / student form; "Change role" back link; stepper only on forms)

**Interfaces:**
- Produces: `RolePicker({ onPick: (role: 'student'|'faculty') => void })`. In `RequestAccessPage`, `const role = ['student','faculty'].includes(p.get('role')) ? p.get('role') : null`, and `setRole(r)` writes `?role=r`; `setRole(null)` clears it.

- [ ] **Step 1: Build `RolePicker`**

Copy the mockup's distilled picker exactly: heading "Who is requesting access?", lede "Students and faculty sign up differently.", one bordered list with two `<button>` rows.
- Student row: graduation-cap icon, title "Student", line "Student-number email and your Student ID or COR".
- Faculty row: monitor icon, title "Faculty", line "PampangaStateU email. An administrator approves it."
- Each row ends with a trailing chevron. Use `lucide-react` icons (`GraduationCap`, `Monitor`, `ChevronRight`).
- Hover is `bg-primary-light`. Focus ring is inset.

- [ ] **Step 2: Wire the page**
  - No stored claim and no `role` → `RolePicker`, with no stepper and no "Request Account Access" heading.
  - `role === 'student'` → back link "Change role" (`ChevronLeft`), heading "Request student access", then `RequestAccessForm`.
  - A stored claim still wins over `role`, as today.

- [ ] **Step 3: Verify in the browser** on 5174 at 375px and 1280px, light and dark.
  - `/request-access` shows the picker.
  - Student opens the form with `?role=student` in the URL.
  - Change role goes back to the picker.
  - `?role=admin` shows the picker.
  - Submitting a student request still reaches today's decision screens.

- [ ] **Step 4: Lint** `cd frontend && npx eslint src/pages/RequestAccessPage.jsx src/components/auth` — no new errors.

- [ ] **Step 5: Commit** `git commit -am "Ask Student or Faculty first on Request Access"`

---

### Task 4: Faculty form, faculty copy and stepper

**Files:**
- Create: `frontend/src/components/auth/FacultyRequestForm.jsx`
- Modify: `frontend/src/pages/RequestAccessPage.jsx` (`handleSubmit(data, role)`, `mapError(err, role)`, stored claim carries `role`, faculty review copy, stepper labels)

**Interfaces:**
- Consumes: Task 1's JSON endpoint and Task 2's `pending_manual_review` poll status.
- Produces: `FacultyRequestForm({ onSubmit: (body: {first_name, last_name, email, requested_role:'faculty'}) => void, error, isLoading, onOpenLegal, onSwitchToStudent })`.

- [ ] **Step 1: Build `FacultyRequestForm`**

Copy the mockup's faculty form:
- First Name ("Maria") and Last Name ("Santos").
- "PampangaStateU Email" with placeholder `firstname.lastname@pampangastateu.edu.ph` and help "The faculty address you use at PampangaStateU."
- The Terms checkbox, using the same copy and `onOpenLegal` as the student form.
- Submit button "Submit for Review".
- Lede above the form: "An administrator reviews faculty requests. Once approved, we email you a link to set your password."

Inline email checks run on blur and on submit, before sending:
- All-digit email: show the `FACULTY_EMAIL_LOOKS_LIKE_STUDENT` copy, with "Request access as a Student instead" calling `onSwitchToStudent`.
- Any other mismatch: show the faculty `INVALID_EMAIL_DOMAIN` copy.

- [ ] **Step 2: Wire the page**
  - `role === 'faculty'` → "Change role" link, heading "Request faculty access", then `FacultyRequestForm`.
  - `handleSubmit` sends JSON for faculty (no multipart header) and keeps `FormData` for students.
  - `writeStoredClaim` gains a `role` field, and `readStoredClaim` restores it.
  - `mapError(err, role)` returns the faculty `INVALID_EMAIL_DOMAIN` copy for faculty. Add `FACULTY_EMAIL_LOOKS_LIKE_STUDENT` and `DOCUMENT_REQUIRED` with the exact copy from Global Constraints.
  - `ProgressStepper` takes `role`. For faculty, the labels are `['Submit Request', 'Admin Review', 'Set Password', 'Account Ready']` from the moment the faculty form opens.
  - When `decision === 'pending_manual_review'` and the role is faculty, the panel reads:
    - title: "Waiting for an administrator"
    - body: "Your faculty request for {email} was received. An administrator will review it."
    - note: "When it is approved, we email you a link to set your password. This page also updates on its own."
  - Students keep today's manual-review copy.

- [ ] **Step 3: Verify in the browser** on 5174, 375px and 1280px, light and dark.
  - Faculty submit lands on the waiting panel, with Admin Review highlighted in the stepper.
  - Reloading the page keeps the waiting panel.
  - An all-digit email shows the student hint and link, and no request is sent.

- [ ] **Step 4: Lint and build** `npx eslint src/pages/RequestAccessPage.jsx src/components/auth && npx vite build --outDir <scratchpad>/build`. Expected: no new lint errors, and the build succeeds.

- [ ] **Step 5: Commit** `git commit -am "Let faculty request access for administrator review"`

---

### Task 5: End-to-end check

- [ ] **Step 1:** Start `test-backend` and `test-frontend` from `.claude/launch.json`.
- [ ] **Step 2:** Submit a faculty request in the browser with `maria.santos@pampangastateu.edu.ph`.
- [ ] **Step 3:** Approve it in Django admin at `http://localhost:8001/admin/`, filtering by `requested_role = faculty`. The user signs in to admin themselves.
- [ ] **Step 4:** The open tab advances to Set Password, and setting a password reaches Account Ready.
- [ ] **Step 5:** Delete the test `AccessRequest` and its `User` in admin. Stop only 8001 and 5174.
