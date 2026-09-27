# Abstract recovery audit

Completed 27 September 2026. Baseline captured before edits through `ThesisExtractMetadataView._extract_and_respond`, the same extraction/gate/response body used by the upload metadata POST. The source corpus is `C:/Users/Desktop/Downloads/{2021,2023,2024,2025}`: 50 PDFs plus two DOCX controls. No source documents were edited. Database connections were prohibited by the audit runner.

## Results

- PDF coverage: **40/50 → 45/50** nonempty abstracts. Both DOCX controls remain unchanged.
- All 40 existing PDF abstracts and their confidence values are byte-for-byte unchanged. All other fields and confidence values match the baseline across all 52 documents.
- All source SHA-256 hashes, response field names, response methods, and HTTP statuses match. `filled_fields` and `message` reflect the five newly filled abstracts through the existing response logic.
- Every extended scan uses a 15-page limit; no response runs that 15-page extraction twice.
- The normal detector, document rejection gate, submission path, database records, and embeddings were not changed. The later timeout follow-up changed only the frontend preview time limit; pre-existing working-tree changes were preserved.

## Completed phases

1. Captured baseline values/confidence for every document. Added an absent-abstract-only retry through page 15, sharing the keyword retry. Four isolation tests passed. Printed-page checks showed HUBISKO was complete, EXTHEALTH was fragmented, and APPOKO was truncated; these intermediate results are in `phase1.json`.
2. Added a local recovery parser with page boundaries, one continuation page, explicit section endings, marginal-text cleanup, prose checks, and rejection of incomplete candidates. HUBISKO, EXTHEALTH, and APPOKO were verified against the rendered printed pages. Thirty-three focused tests passed. `phase2.json` records the results.
3. Added optional Poppler coordinate-based column recovery, confined to at most two heading-bearing pages inside the 15-page window. CODEQUEST’s printed left column was checked in full; the introduction is excluded. Thirty-seven focused tests passed. `phase3.json` records the result.
4. Reused existing cover OCR for CYBERESCAPE. Added page-level image/sparse-text checks and a maximum of two targeted OCR pages, with failure returning blank and OCR confidence capped at medium. Forty-seven focused tests passed at phase completion. `phase4.json` records the result.

## Printed-source checks

| Document | PDF page(s) | Final result | Confidence | Recovery |
|---|---|---|---|---|
| HUBISKO | 11 | Complete and readable; ends “student applicants and scholarship providers.” | High | Shared 15-page text pass |
| EXTHEALTH | 12 | Complete, readable prose after joining fragmented words; ends “stay informed about health topics.” | Medium | Shared 15-page pass plus local whitespace repair |
| APPOKO | 13–14 | Complete continuation; joins “stakeholder registration”; ends “Bahay Pag-ibig.” | High | Shared 15-page pass plus two-page recovery |
| CODEQUEST | 1 | Complete left-column abstract; ends “evolving educational methodologies.” No introduction text. | High | Poppler column recovery |
| CYBERESCAPE | 1 | Full abstract through “varlous requirements.” Structurally complete and readable, but OCR spelling needs review. | Medium | Reused existing cover OCR |

CYBERESCAPE OCR retains visible recognition errors, including “im modem” for printed “in modern”, “tuming” for “turning”, and “varlous” for “various”. No speculative spelling substitutions were made. The existing medium-confidence UI displays **Please verify**. A separate direct targeted-page OCR check also recovered the complete abstract at medium confidence, without depending on missing keywords.

## Remaining blanks and negative checks

The following five audit PDFs remain blank/low. A full selectable-text inspection found no occurrence of “Abstract” in them; no prose was inferred from their introductions:

- 2021/ARAL.pdf
- 2021/DTracker.pdf
- 2021/MAMALAKAYA.pdf
- 2021/ModeYul.pdf
- 2021/Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus.pdf

Synthetic negative tests cover table-of-contents Abstract entries (with leaders and with a separate page number), introduction-only text, no heading, no end boundary, a truncated final sentence, mixed sections, excessive length, and continuation beyond the permitted page range. All stay blank. Existing detector and document-gate tests also pass.

## Validation and bounds

- Broad existing/focused suite: **503 passed, 52 deselected** using `-m "not django_db"`; database-backed tests were deliberately excluded. After final cache/exception refinements, **52 focused tests passed**, including additional failure and section-boundary safeguards. No production or test database was accessed.
- Added request-level POST/schema validation without database access, gate-order validation, failure isolation, unchanged normal results, keyword-pass reuse, DOCX exclusion, page limits, column isolation, unavailable-tool behavior, OCR confidence/timeout checks, and exact single-page rasterization checks.
- All five real target endpoint responses were rechecked after the final cache refinement and matched `final.json` exactly.
- Frontend source inspection confirms `fillText` skips touched/nonempty values, including an edit made while extraction is pending via the existing touched-field guard. Browser interaction was not tested.
- The normal ten-page metadata pass is unchanged. An empty PDF abstract permits a 15-page retry, reused if keywords already required it. Text recovery follows at most two pages beginning at an explicit Abstract heading. Layout examines at most two explicit-heading pages (10-second timeout each).
- New targeted OCR considers an image-backed first page, or an image-backed page with a selectable Abstract heading, only when fewer than 200 alphabetic characters are selectable. It OCRs at most two such pages within page 15, including any existing cover attempt in that budget. Each new page has a 15-second rendering timeout and a 20-second OCR timeout. It does not scan unlabeled sparse interior pages; those remain a conservative limitation.

## Dependency and latency impact

No Python package or requirements changes. Layout recovery uses optional **Poppler `pdftotext` on PATH** (part of the Poppler tooling already used for PDF rendering). Deployments exposing only `pdftoppm`/`pdfinfo` must also expose `pdftotext` to recover column cases. Absence/timeouts are caught and leave uncertain fields blank. OCR reuses existing `pdf2image`, Tesseract, and the project’s Tesseract path discovery.

Local recovery-only measurements after the shared PDF pass: text recovery rounded to 0.000 s for the three late abstracts; CODEQUEST column recovery took 0.062 s; direct targeted CYBERESCAPE OCR took 2.922 s. These are single local measurements, not service guarantees. The actual CYBERESCAPE endpoint reuses its existing OCR, so it adds no new rasterization/OCR pass. Successful normal abstracts do no recovery work. Missing abstracts with existing keywords can add a bounded 15-page extraction. Full audit endpoint timings are retained in both JSON snapshots; concurrent test activity makes their small differences unsuitable as a benchmark.

## Files changed by this task

- `backend/theses/services/abstract_recovery.py` — new local conservative recovery service.
- `backend/theses/services/text_extractor.py` — cache raw page boundaries without changing normal text; expose bounded single-page OCR.
- `backend/theses/views.py` — run abstract-only fallbacks after existing metadata handling and reuse keyword/cover results.
- `backend/theses/tests/test_abstract_recovery.py` — new isolation, quality, layout, OCR and request tests.
- `backend/theses/tests/test_metadata_fields.py` — update two existing source-fixture expectations to allow the newly recovered abstract while preserving other fields.
- `backend/theses/tests/audit_abstracts.py` — resumable read-only audit runner with a database guard.
- `docs/abstract-audit/` — this report, complete baseline/final responses, per-phase evidence and timing results.

Other files already marked modified before this task were not edited here, except the upload form's timeout constant and comment in the later follow-up. The shared normal abstract detector in `metadata_extraction.py` remains byte-identical to the starting snapshot.

## Follow-up: CYBERESCAPE preview timeout

A later local run of the CYBERESCAPE endpoint took 28.923 seconds against the upload form's 30-second request timeout. Instrumentation showed an unused second author OCR pass during the cover-page keyword retry. The retry now reads the same cover text while omitting only that unused author pass; a new unit test checks both the identical cover text and the single author OCR call. The upload form's preview timeout is now 45 seconds to allow slower machines to finish bounded OCR. A follow-up local run took 15.537 seconds, called author OCR once, and returned a response exactly equal to the earlier `final.json` CYBERESCAPE result. These measurements are local observations, not deployment guarantees. The final focused suite passed 53 tests, and the frontend production build passed. Lint still reports an existing `react-hooks/set-state-in-effect` error at `UploadThesisModal.jsx:220`, unrelated to this timeout change. The form's field-filling rules were not changed by this follow-up.

This follow-up also changes `frontend/src/components/upload/UploadThesisModal.jsx` only for the preview timeout and its comment. The baseline and final JSON snapshots remain the pre-follow-up audit evidence; the CYBERESCAPE response was compared to them after optimization.

## Per-document comparison

Full text and all confidence values are in [baseline.json](baseline.json) and [final.json](final.json). “Unchanged” means exact abstract text and confidence equality.

| Document | Baseline confidence | Final confidence | Result |
|---|---|---|---|
| 2021/#31B A 117 EMERGENCY COMMUNICATION PLATFORM FOR ABUSE REPORT IN A MOBILE APPLICATION.pdf | high | high | Unchanged |
| 2021/ALUMNI PORTAL TRACKER WITH DATA ANALYTICS USING FOLD-GROWTH ALGORITHM.pdf | high | high | Unchanged |
| 2021/ARADA.pdf | high | high | Unchanged |
| 2021/ARAL.pdf | low | low | Blank |
| 2021/CAREER TRACK MOBILE APPLICATION USING FUZZY LOGIC FOR HIGH SCHOOL STUDENT.pdf | high | high | Unchanged |
| 2021/DTracker.pdf | low | low | Blank |
| 2021/E-PANGASIWA.pdf | high | high | Unchanged |
| 2021/KLASIKOPINAS.pdf | high | high | Unchanged |
| 2021/MAMALAKAYA.pdf | low | low | Blank |
| 2021/MedicScale.pdf | high | high | Unchanged |
| 2021/ModeYul.pdf | low | low | Blank |
| 2021/SABIYAHE.pdf | high | high | Unchanged |
| 2021/SIMPLIFY.pdf | high | high | Unchanged |
| 2021/SIMULATION OF LOGIC GATES CIRCUITS TEST AND GUIDE USING ANDROID APPLICATION.pdf | high | high | Unchanged |
| 2021/Vehicle Management System using Cloud Mapping Technology.pdf | high | high | Unchanged |
| 2021/Web-Based Qualifying Examination for Accountancy Students of Don Honorio Ventura State University – Main Campus.pdf | low | low | Blank |
| 2023/ANIDELIVERY.pdf.pdf | high | high | Unchanged |
| 2023/ANTABE.pdf.pdf | high | high | Unchanged |
| 2023/AQUAFLOW.pdf | high | high | Unchanged |
| 2023/CODEQUEST.pdf | low | high | Recovered |
| 2023/COMPAWNION.pdf.pdf | high | high | Unchanged |
| 2023/CYBERESCAPE.pdf | low | medium | Recovered |
| 2023/DHVCHAT.pdf.pdf | high | high | Unchanged |
| 2023/DORMIFY.pdf | high | high | Unchanged |
| 2023/FUZZY.pdf.pdf | high | high | Unchanged |
| 2023/HTEFinder.pdf | high | high | Unchanged |
| 2023/MEMOLOOP.pdf | high | high | Unchanged |
| 2023/MSWD Online Financial Assistance Program Management System with SMS.pdf | high | high | Unchanged |
| 2023/PALENGKIHAN.pdf.pdf | high | high | Unchanged |
| 2023/SISTEMA de OBRA.pdf | high | high | Unchanged |
| 2023/TASKGROVE.pdf | high | high | Unchanged |
| 2023/VAXTRACK.pdf.pdf | high | high | Unchanged |
| 2023/Web-Based Equipment Maintenance Monitoring System for DHVSU Facilities.pdf | high | high | Unchanged |
| 2024/APPOKO.pdf | low | high | Recovered |
| 2024/EXTHEALTH.pdf | low | medium | Recovered |
| 2024/HUBISKO.pdf | low | high | Recovered |
| 2024/THESIX.pdf | high | high | Unchanged |
| 2025/AnImo.pdf | high | high | Unchanged |
| 2025/ATTACHMATES.pdf | high | high | Unchanged |
| 2025/BARANGAYMED+.pdf | high | high | Unchanged |
| 2025/ChemLab AR.pdf | high | high | Unchanged |
| 2025/CyberDefender.pdf | high | high | Unchanged |
| 2025/DormHonorio.pdf | high | high | Unchanged |
| 2025/HEADLINK.docx | high | high | Unchanged |
| 2025/iSecure.docx | high | high | Unchanged |
| 2025/MY HONORIAN BUDDY.pdf | high | high | Unchanged |
| 2025/REHIRELY.pdf | high | high | Unchanged |
| 2025/Revolucion.pdf | high | high | Unchanged |
| 2025/ShopEase.pdf | high | high | Unchanged |
| 2025/SINDALAN CONNECT.pdf | high | high | Unchanged |
| 2025/Web-Based Grading System with Data Analytics for the Modernized Processing of President's and Dean's Lists Canditates_organized..pdf | high | high | Unchanged |
| 2025/Web-Based Grading System with Data Analytics for the Modernized Processing of President's and Dean's Lists Canditates_organized.pdf | high | high | Unchanged |
