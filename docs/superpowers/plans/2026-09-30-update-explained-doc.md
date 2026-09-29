# Update THESYSPLUS_EXPLAINED.md and regenerate the PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `THESYSPLUS_EXPLAINED.md` in line with the code as it is today (16 commits and a whole app it never mentioned), then rebuild `THESYSPLUS_EXPLAINED.pdf` from it.

**Architecture:** The document is one long "explain it like a restaurant" walkthrough, one `###` section per file, grouped in `## Part N`. We keep that structure and voice. A small checker script (kept outside the repo) turns "is the doc current?" into two lists — code files the doc never names, and doc claims (paths, identifiers) the code no longer has — and each task shrinks those lists. `build_pdf.py` (reportlab) then turns the Markdown into the PDF.

**Tech Stack:** Markdown, Python 3.11 + reportlab 4.2.5 (already installed), git. No new dependencies.

**Spec:** The request itself ("Update THESYSPLUS_EXPLAINED.md and regenerate THESYSPLUS_EXPLAINED.pdf"), plus `THESYSPLUS_EXPLAINED.md` lines 1-23 (voice and reading rules) and `build_pdf.py` docstring (the Markdown subset the PDF builder supports).

## Global Constraints

- Working directory `C:\Users\Desktop\Downloads\THESYSplus-main`, branch `main`, in sync with `origin/main` at the start.
- **Never** push, reset, amend, rebase or otherwise rewrite history. Local new commits are allowed; no `git push`.
- Do not touch code. Only `THESYSPLUS_EXPLAINED.md`, `THESYSPLUS_EXPLAINED.pdf`, and (only if the PDF cannot render something) `build_pdf.py`. `.claude/settings.local.json` stays uncommitted.
- Markdown subset only (from `build_pdf.py`): `#`/`##`/`###` headings, `- ` bullets one level, `>` quotes, fenced code, `---`, `**bold**`, `` `code` ``. **No tables, no nested lists, no images.**
- Keep the existing voice: restaurant metaphor, plain language, a short emoji in each `###` title, real file paths in backticks. Every claim must be checkable in the code; do not invent behaviour.
- No secrets in the doc: never write values from `backend/.env` or `backend/.env.demo`. Describe variable *names* only.
- Section title format stays `### path/to/file — "Metaphor title" 🔧` and files stay grouped in numbered Parts; new Parts get the next numbers (18, 19).

## Review Focus

- Emoji in headings may render as boxes/black squares in the PDF (reportlab's built-in fonts lack them) — check how the current PDF handles them before adding more.
- A `|` table or `1.` list pasted from a source file would render as raw text in the PDF — grep the finished Markdown for `^\|` and `^\d+\.`.
- Very long lines inside fenced code blocks overflow the page in `Preformatted` — keep code snippets under ~90 characters per line.
- Stale numbers: counts ("5 apps", "115 theses", "8 clusters"), phase names and file lists in the existing intro/closing text.
- Claims about removed behaviour (e.g. "second email", `isDark` everywhere, placeholder tokens) surviving in sections nobody re-read.

---

### Task 1: Baseline, checker, and PDF pipeline smoke test

**Files:**
- Create (outside repo): `C:\Users\Desktop\AppData\Local\Temp\claude\C--Users-Desktop-Downloads-THESYSplus-main\93877d96-ba75-4733-958d-c4829758ae72\scratchpad\doc_check.py`
- Read: `THESYSPLUS_EXPLAINED.md`, `build_pdf.py`

**Interfaces:**
- Produces: `doc_check.py` with three outputs — `MISSING FILES` (tracked source files not named in the doc), `DEAD PATHS` (backticked repo paths in the doc that no longer exist), `STALE NAMES` (per `###` section, backticked identifiers like `foo()` / `ClassName` that do not appear in that section's file). Exit code 0 always; the executor reads the lists.

- [ ] **Step 1: Write the checker**

```python
# doc_check.py — run from the repo root
import re, subprocess, os
doc = open("THESYSPLUS_EXPLAINED.md", encoding="utf-8").read()
tracked = subprocess.run(["git", "ls-files", "backend", "frontend/src"],
                         capture_output=True, text=True).stdout.split("\n")
skip = re.compile(r"(/migrations/|/tests?/|test_|__init__|\.gitkeep|\.(png|jpe?g|webp|svg|json|lock|md|txt|css|html|ico|woff2?|pdf|docx|xlsx)$|/static/|/media/|fixtures|conftest|/templates/|/assets/)")
print("== MISSING FILES")
for f in tracked:
    if f and not skip.search(f) and os.path.basename(f) not in doc and f not in doc:
        print(" ", f)

print("== DEAD PATHS")
for p in sorted(set(re.findall(r"`((?:frontend|backend)/[\w./-]+\.\w+)`", doc))):
    if not os.path.exists(p):
        print(" ", p)

print("== STALE NAMES")
sections = re.split(r"^### ", doc, flags=re.M)[1:]
for sec in sections:
    head = sec.split("\n", 1)[0]
    m = re.search(r"((?:frontend|backend)/[\w./-]+\.\w+)", head)
    if not m or not os.path.exists(m.group(1)):
        continue
    src = open(m.group(1), encoding="utf-8", errors="ignore").read()
    names = set(re.findall(r"`([A-Za-z_][\w]*)\(\)`", sec)) | set(re.findall(r"`([A-Z][A-Za-z0-9]{3,})`", sec))
    gone = sorted(n for n in names if n not in src)
    if gone:
        print(f"  {m.group(1)}: {', '.join(gone)}")
```

- [ ] **Step 2: Run it and record the baseline**

Run: `python "<scratchpad>/doc_check.py" > "<scratchpad>/check_before.txt"; wc -l "<scratchpad>/check_before.txt"`
Expected: a non-empty `MISSING FILES` list (about 47 entries, including `backend/processing_jobs/worker.py`), and possibly some `DEAD PATHS` / `STALE NAMES`.

- [ ] **Step 3: Prove the PDF pipeline works before editing**

Run: `python build_pdf.py && python -c "import reportlab,sys; from reportlab.pdfgen import canvas; print('ok')"` then `ls -la THESYSPLUS_EXPLAINED.pdf`
Expected: builds without a traceback and rewrites the PDF. If it fails, fix `build_pdf.py` minimally now (Review Focus 1) and re-run.

- [ ] **Step 4: Check how emoji render in the existing PDF**

Run: `python -c "import re;t=open('build_pdf.py',encoding='utf-8').read();print([l for l in t.splitlines() if 'emoji' in l.lower() or 'font' in l.lower()][:10])"`
Expected: see whether emoji are stripped or mapped. Record the answer; new headings follow whatever the builder does.

- [ ] **Step 5: Restore the PDF so Task 1 leaves the tree clean**

Run: `git checkout -- THESYSPLUS_EXPLAINED.pdf` (safe: restores a file, does not touch history)
Expected: `git status --short` shows only `.claude/settings.local.json`.

---

### Task 2: Fix what the doc gets wrong today

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.md` (any section the checker's `DEAD PATHS` / `STALE NAMES` flags, plus lines 1-23 and 2197-2212)

**Interfaces:**
- Consumes: `check_before.txt` from Task 1.
- Produces: an updated intro that mentions the new Parts 18-19 and a closing note whose scope statement is true.

- [ ] **Step 1: For each `DEAD PATHS` entry**, find the section, open the file's current location (`git log --diff-filter=R --name-status` if renamed), and update or delete the section.
- [ ] **Step 2: For each `STALE NAMES` entry**, open the real file, and rewrite the sentence that names the missing function/class so it names what exists now.
- [ ] **Step 3: Re-verify the sections the code changed most since mid-September** by reading the current code and correcting the prose: `backend/theses/views.py` (21 commits), `topic_analysis.py`, `semantic_search.py`, `title_similarity.py`, `text_extractor.py`, `theses/urls.py`, `thesys/settings/prod.py`. Only change sentences that are wrong; keep the rest.
- [ ] **Step 4: Update the closing note** so it no longer claims "every actively-used file" unless `MISSING FILES` is empty at the end (Task 7 re-checks this), and mention the new Parts.
- [ ] **Step 5: Re-run the checker** — `DEAD PATHS` and `STALE NAMES` must both be empty.
- [ ] **Step 6: Commit**

```bash
git add THESYSPLUS_EXPLAINED.md
git commit -m "docs: correct stale claims in THESYSPLUS_EXPLAINED.md"
```

---

### Task 3: Frontend — the redesign and the files nobody explained

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.md` (Parts 1, 5, 6, 7, 8, 9)
- Read: `frontend/src/App.jsx`, `frontend/src/api/client.js`, `frontend/src/api/jobs.js`, `frontend/src/lib/{motion,upload}.js`, `frontend/src/utils/formatters.js`, `frontend/src/hooks/useBodyScrollLock.js`, `frontend/src/components/navigation/RouteScrollManager.jsx`, `frontend/src/components/ui/AnimatedCounter.jsx`, `frontend/src/components/auth/SetPasswordForm.jsx`, `frontend/src/pages/SignInPage.jsx`, `frontend/src/styles/tokens.{js,css}`, `frontend/src/index.css`, `frontend/src/components/layout/{AppNavbar,PageHeader,PageShell,AuthLayout}.jsx`, `DESIGN.md`

**Interfaces:**
- Consumes: the section format from Global Constraints.
- Produces: new `###` sections for each undocumented frontend file, placed in the Part that fits (e.g. `api/jobs.js` in Part 1, `lib/motion.js` and `lib/upload.js` and `utils/formatters.js` in Part 9, `RouteScrollManager` in Part 9, `AnimatedCounter` in Part 8, `SetPasswordForm` and `SignInPage` in Parts 7/5).

- [ ] **Step 1: Read each unlisted file above** (docstring, exports, what calls it via `grep -rn "<name>" frontend/src`).
- [ ] **Step 2: Write one `###` section per file** in the existing voice, each with: what it is, why it exists, the 3-5 things it does, who uses it.
- [ ] **Step 3: Update the changed sections** to today's behaviour, using `DESIGN.md` as the checked source for design facts: `App.jsx` (pages load on demand), `client.js` (ngrok skip header on the thesys.plus hosts), `tokens.js`/`tokens.css` (semantic tokens are real, not placeholders; solid-primary tokens), `index.css` (`.thesys-input`), `AppNavbar.jsx` (shared `NAV_BAR_CLASS`), `PageHeader`/`PageShell` (every page uses them), `ThesysLogo.jsx` (`onDark`, SVG symbol), `LandingPage.jsx` (shared bar, token sections, hero), `TrendAnalysisPage.jsx` (proposed-title topic check, reviewed-subjects view), `RepositoryPage.jsx`, `TitleSimilarityPage.jsx`, `ThesisDetailPage.jsx`, `AnalyticsDashboardPage.jsx`, `UploadThesisModal.jsx` (real upload progress, job polling via `waitForJob`), `ProfilePage.jsx`, `SettingsPage.jsx`.
- [ ] **Step 4: Run the checker.** `MISSING FILES` lists no `frontend/` entries; `STALE NAMES` empty.
- [ ] **Step 5: Commit**

```bash
git add THESYSPLUS_EXPLAINED.md
git commit -m "docs: explain the frontend redesign and undocumented frontend files"
```

---

### Task 4: Backend `theses` — services, commands, search rules

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.md` (Part 14)
- Read: `backend/theses/services/{abstract_recovery,acronyms,cached_topic_trends,metadata_extraction,preview_pages,redundancy,reviewed_subjects,subject_suggestions,technology_tags,thesis_document_check,title_match,watermark_pdf}.py` and `backend/theses/management/commands/*.py`

**Interfaces:**
- Consumes: none from Tasks 2-3.
- Produces: one `###` section per service and one grouped `###` section for the management commands (`attach_sample_manuscripts`, `embed_theses`, `import_reviewed_subjects`, `list_acronym_candidates`, `seed_demo_data`, `seed_theses`, `warm_topic_trends`), placed inside Part 14 next to their neighbours (search-related services after `semantic_search`, document-related services after `text_extractor`).

- [ ] **Step 1: For each service, read the module docstring, the public functions (`grep -n "^def \|^class "`), and the callers** (`grep -rn "<module>" backend --include=*.py`). Write down what goes in and what comes out.
- [ ] **Step 2: Write the sections.** For `metadata_extraction.py` (2960 lines) explain the pipeline stages and the fields it fills, not every helper. For `acronyms.py` and `title_match.py` explain how Repository search and Title Similarity share them and give one concrete example from the code's own comments or tests.
- [ ] **Step 3: Write the management-commands section** from each command's `help` text and `add_arguments`.
- [ ] **Step 4: Run the checker.** No `backend/theses/` entries in `MISSING FILES`.
- [ ] **Step 5: Commit**

```bash
git add THESYSPLUS_EXPLAINED.md
git commit -m "docs: explain the theses services and management commands"
```

---

### Task 5: Backend `processing_jobs` and the other missing backend modules

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.md` (new Part 18; small additions to Parts 3, 12 and 16)
- Read: `backend/processing_jobs/{models,services,views,urls,worker,apps}.py`, `backend/processing_jobs/management/commands/process_jobs.py`, `backend/auth_service/sso.py`, `backend/common/performance.py`, `backend/identity_verification/services/audit.py`, `backend/identity_verification/management/commands/migrate_verification_documents.py`, `backend/access_requests/tests.py` (only to confirm it is a test file — leave it out of the doc)

**Interfaces:**
- Produces: `## Part 18 — Backend: the processing_jobs app (the back-of-house order queue) 🧾` containing `models.py` (`ProcessingJob`, its four kinds and four states), `services.py` (`enqueue_file`, `enqueue_identity`, `claim_next`, cleanup helpers), `views.py` + `urls.py` (`JobStatusView`, `/jobs/<uuid>/`), `worker.py` + `process_jobs` command (lease, heartbeat, `execute`, `run_one`). Plus one `###` each for `sso.py` (Part 3), `performance.py` (Part 16), `identity_verification/services/audit.py` and the `migrate_verification_documents` command (Part 12).

- [ ] **Step 1: Read the processing_jobs app end to end** (about 500 lines in total) and trace one upload: view enqueues → worker claims → `execute` runs the right service → frontend polls the status view.
- [ ] **Step 2: Write Part 18** with a short "life of a job" walk-through before the per-file sections.
- [ ] **Step 3: Write the four small sections** in Parts 3, 12, 16.
- [ ] **Step 4: Check the claim about job kinds and states** against `models.py` (`title`, `metadata`, `thesis`, `identity`; `queued`, `running`, `succeeded`, `failed`).
- [ ] **Step 5: Run the checker.** No `processing_jobs`, `sso.py`, `performance.py` or identity-audit entries left in `MISSING FILES`.
- [ ] **Step 6: Commit**

```bash
git add THESYSPLUS_EXPLAINED.md
git commit -m "docs: explain the processing_jobs app and remaining backend modules"
```

---

### Task 6: New Part 19 — running it for real

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.md` (new Part 19; intro tweak)
- Read: `backend/scripts/{start,stop}_demo_{backend,ngrok}.ps1`, `backend/thesys/demo_wsgi.py`, `backend/.env.example`, `frontend/vercel.json`, `docs/NGROK_DEMO.md`, `backend/common/email_backend.py`

**Interfaces:**
- Produces: `## Part 19 — Running THESYS+ for real (the demo setup) 🚀` with sections for the four demo scripts, `demo_wsgi.py`, and one prose section "How a request travels from thesys.plus to the kitchen" (browser → Vercel rewrite `/api/v1` → ngrok tunnel → Waitress → Django) and one on email (`EMAIL_BACKEND`, `EMAIL_FROM`, `SMTP_*` names and where the verification/reset links get their base URL, `FRONTEND_BASE_URL`). Variable **names only**.

- [ ] **Step 1: Read the sources above.** Confirm names against the files, not memory.
- [ ] **Step 2: Write Part 19** in the restaurant voice (the tunnel is "the delivery door", Vercel "the front window").
- [ ] **Step 3: Grep the new text for secrets** — `grep -nE "re_[A-Za-z0-9]{10,}|password=|SECRET" THESYSPLUS_EXPLAINED.md` must find no value, only variable names.
- [ ] **Step 4: Commit**

```bash
git add THESYSPLUS_EXPLAINED.md
git commit -m "docs: explain how the demo deployment and email delivery work"
```

---

### Task 7: Final checks, regenerate the PDF, commit

**Files:**
- Modify: `THESYSPLUS_EXPLAINED.pdf` (regenerated), possibly `build_pdf.py`

**Interfaces:**
- Consumes: the finished Markdown from Tasks 2-6.

- [ ] **Step 1: Run the checker.** All three lists empty (or every remaining `MISSING FILES` entry is a deliberate exclusion that the closing note names).
- [ ] **Step 2: Lint the Markdown for the unsupported subset**

Run: `grep -nE "^\|" THESYSPLUS_EXPLAINED.md | head; grep -nE "^  +- " THESYSPLUS_EXPLAINED.md | head; awk 'length>140' THESYSPLUS_EXPLAINED.md | head -3`
Expected: no tables, no nested bullets; long lines only in prose (which wraps).
- [ ] **Step 3: Rebuild the PDF**

Run: `python build_pdf.py && ls -la THESYSPLUS_EXPLAINED.pdf`
Expected: no traceback; file newer than the Markdown.
- [ ] **Step 4: Verify the PDF content**

Run: `python -c "from pypdf import PdfReader" 2>&1 | tail -1` — if `pypdf` is missing, use `pdftotext` if present, otherwise `python -c "import re;d=open('THESYSPLUS_EXPLAINED.pdf','rb').read();print(len(re.findall(rb'/Type /Page[^s]',d)),'pages')"`.
Expected: more pages than the old 136 KB file, and a text search finds "processing_jobs" and "Part 19" in the extracted text (or, without an extractor, the page count grew and the file opens; say so honestly).
- [ ] **Step 5: Commit the PDF**

```bash
git add THESYSPLUS_EXPLAINED.md THESYSPLUS_EXPLAINED.pdf
git commit -m "docs: regenerate THESYSPLUS_EXPLAINED.pdf from the updated explainer"
```
- [ ] **Step 6: Confirm nothing was pushed or rewritten**

Run: `git status -sb; git log --oneline origin/main..HEAD`
Expected: `main` is ahead of `origin/main` by the new docs commits only; the tree shows just `.claude/settings.local.json` modified.
