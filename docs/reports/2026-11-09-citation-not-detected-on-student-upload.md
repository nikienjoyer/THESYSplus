# Citation not detected on a student upload

**Date:** 2026-11-09
**Reported by:** project owner, with two screenshots of the upload success screen
**Status:** cause confirmed; fix proposed, not yet built

## What was seen

| Upload | Account | Result on the success screen |
|---|---|---|
| Sample thesis citing the AI-Powered thesis | Administrator | "Thesis Approved & Published", **1** cited thesis listed |
| Laboratory Equipment sample thesis (cites both earlier samples) | Student | "Submitted for Review", **"None of the repository's theses appear in your reference list."** |

The student's thesis does cite two theses that were in the system, so "none" looked wrong.

## What happened

**1. The theses it cites were not approved when it was uploaded.**
Only **approved** theses can be cited. That rule is deliberate: a pending or rejected thesis is not part of the repository yet, so nothing may count as citing it.

The database right after the student upload:

| Thesis | Status | Uploaded by | Time (UTC) |
|---|---|---|---|
| Development of an AI-Powered Student Academic Performance Monitoring System | pending review | student | 06:54 |
| Design and Implementation of a Web-Based Inventory Management System for Small Businesses | pending review | student | 06:54 |
| Development of a Web-Based Laboratory Equipment Inventory and Borrowing Monitoring System | pending review | student | 06:55 |

No approved copy of either cited thesis existed, and no citation rows existed at all. The earlier approved copies, uploaded by the administrator, had been deleted before 06:54. The student re-uploads prove it: the same files would have been refused as duplicates ("This file has already been uploaded") if the approved copies still existed. Deleting a thesis also deletes its citations, which is why the administrator's earlier citation is gone too.

So detection had **zero candidates** to compare against, and "none found" was the correct answer for that moment.

**2. The matching itself works.** Checked directly against the stored text of the student's thesis, both titles match its reference list. They are only skipped because they are pending:

| Cited thesis | Would match if approved |
|---|---|
| Design and Implementation of a Web-Based Inventory… | yes |
| Development of an AI-Powered Student Academic… | yes |

**3. A real gap: detection runs only once, at upload.**
Approving a thesis later does not re-run detection, in either direction:

- When the two cited theses are approved, the Laboratory Equipment thesis is **not** linked to them.
- When the Laboratory Equipment thesis is approved, its own references are **not** checked again.

So even after faculty approve all three, no citation appears unless someone re-uploads or runs the `detect_citations` command. This gap is what will confuse users. The "none found" message was accurate, but it stays wrong forever after the approvals.

## What should be done

### Now (no code change)

1. A faculty account approves the three pending theses (order does not matter for step 2).
2. Run once on the server:

   ```bash
   python manage.py detect_citations --apply
   ```

   It checks every approved thesis against every other approved thesis and stores the missing citations. It is safe to re-run.

### Fix (recommended)

Re-run detection when a thesis is **approved**, in `record_transition` (`backend/theses/services/review.py`). Every status change goes through that one function: the faculty review API, Django admin, and admin-created records.

On approval of thesis **X**:

1. Save X's own citations (the same `_save_citations` the upload uses).
2. Check every other approved or pending thesis's reference list for X's title, and save those citations too.

Step 2 is what links the Laboratory Equipment thesis back to the two theses once they are approved. Pending citing theses are fine to link: "Cited by" already counts a citation only after the **citing** thesis is approved.

Cost: about 20 lines plus 3 tests (approve the cited thesis first; approve the citing thesis first; a rejected thesis is never cited). Detection stays best-effort: a failure is logged and never blocks an approval.

### Optional: clearer message for students

The student screen could say why nothing was found when that is possible, for example: "Only approved theses can be cited. Citations to theses still under review are added when they are approved." With the fix above, that promise becomes true. This is a small copy change and needs a mockup first.

## Not the cause

- The citation matching rules (whole title, or first 8 words ending at the reference title's end): both titles match.
- Student versus administrator accounts: the account type changes only the status of the **new** upload, not which theses can be cited.
- The "A Sample Undergraduate Thesis Manuscript" line in titles: handled since commit `21bc8cf`.
