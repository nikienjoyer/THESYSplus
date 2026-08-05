# Implementation Plan: AI-Assisted Identity Verification MVP

## Overview

This implementation plan delivers a **capstone-safe MVP** of the AI-Assisted Identity Verification feature for THESYS+. The MVP replaces the free-text justification field with document upload (Student ID or COR), uses Tesseract OCR for text extraction, and applies rule-based validation to automatically verify applicants from the College of Computing Studies at Pampanga State University.

**MVP Scope:** Synchronous processing, OCR + rule-based validation only. NO SBERT, NO TF-IDF, NO Celery, NO Redis, NO async processing, NO retention jobs.

**Implementation Language:** Python (Django backend, React frontend)

**Total Estimate:** ~58 tasks across 8 waves, approximately 80-120 hours of implementation time.

## Tasks

### Wave MVP-1: Foundation (8 tasks)

- [x] 1.1 Create identity_verification Django app
  - Run `python manage.py startapp identity_verification` in backend directory
  - Create `__init__.py`, `apps.py`, `models.py`, `views.py`, `admin.py`, `tests.py`
  - Create subdirectories: `services/`, `validators/`, `types.py`, `protocols.py`
  - _Requirements: 13.1, 13.2_

- [x] 1.2 Add identity_verification to INSTALLED_APPS
  - Update `backend/thesys/settings/base.py`
  - Add `'identity_verification.apps.IdentityVerificationConfig'` to INSTALLED_APPS
  - Place after `'access_requests'` in the list
  - _Requirements: 13.1_

- [x] 1.3 Create VerificationDocument model
  - Define model in `identity_verification/models.py`
  - Fields: id (UUID PK), access_request_id (UUID FK), file_path (TEXT nullable), mime_type (VARCHAR 100), sha256 (CHAR 64), size_bytes (INTEGER), uploaded_at (TIMESTAMPTZ), retention_purge_at (TIMESTAMPTZ NULL), purged_at (TIMESTAMPTZ NULL)
  - Add indexes on sha256 and retention_purge_at
  - Add UNIQUE constraint on access_request_id
  - _Requirements: 13.1, 13.3, 16.2_

- [x] 1.4 Create VerificationResult model (simplified for MVP)
  - Define model in `identity_verification/models.py`
  - Fields: id (UUID PK), access_request_id (UUID FK), status (ENUM), extracted_fields (JSONB), ocr_raw_text (TEXT), ocr_confidence (FLOAT), decision_reason (TEXT), flagged_reasons (JSONB), processed_at (TIMESTAMPTZ), processor_version (VARCHAR 100)
  - Status enum values: 'processing', 'auto_approved', 'pending_manual_review', 'rejected', 'error'
  - Add UNIQUE constraint on access_request_id
  - NOTE: NO sbert_scores or tfidf_scores fields (deferred to post-MVP)
  - _Requirements: 13.2, 13.6, 7.5, 7.6_

- [x] 1.5 Extend AccessRequest model with new fields 🟡
  - Create migration in `access_requests/migrations/`
  - Add status enum values: 'processing', 'auto_approved', 'pending_manual_review'
  - Add verification_document_id (UUID FK nullable)
  - Add verification_result_id (UUID FK nullable)
  - Keep justification field nullable (backward compatibility)
  - _Requirements: 10.1, 10.2, 13.4, 13.5, 13.6_

- [x] 1.6 Write migration 0001_identity_verification_schema
  - Create migration file in `identity_verification/migrations/`
  - CreateModel VerificationDocument with all fields and indexes
  - CreateModel VerificationResult with all fields
  - AlterField AccessRequest.status to add new enum values
  - AddField AccessRequest.verification_document_id (nullable FK)
  - AddField AccessRequest.verification_result_id (nullable FK)
  - Test migration: `python manage.py migrate --plan`
  - _Requirements: 13.1, 13.2, 13.4, 13.5, 13.6_

- [x] 1.7 Configure private file storage settings
  - Update `backend/thesys/settings/base.py`
  - Add PRIVATE_MEDIA_ROOT = os.path.join(BASE_DIR, 'media', 'private')
  - Add VERIFICATION_DOCS_PATH = 'verification_docs'
  - Ensure MEDIA_ROOT/private/ is NOT served by static file serving
  - _Requirements: 15.1, 15.3_

- [x] 1.8 Add IDENTITY_VERIFICATION settings dict
  - Update `backend/thesys/settings/base.py`
  - Add IDENTITY_VERIFICATION dict with keys: SYNC_MODE (True for dev), OCR_CONFIDENCE_HIGH (75), OCR_CONFIDENCE_MEDIUM (60), MAX_FILE_SIZE_MB (10)
  - Add canonical reference data: INSTITUTIONS, COLLEGES, PROGRAMS_CANONICAL
  - _Requirements: 7.2, 7.3, 7.4, 14.1_

- [~] 1.9 Checkpoint - Foundation complete
  - Run `python manage.py migrate` to apply schema changes
  - Verify new tables exist: `verification_document`, `verification_result`
  - Verify AccessRequest has new status values and FK fields
  - Run existing test suite to ensure no regressions
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-2: File Validation (6 tasks)

- [x] 2.1 Implement FileValidator with magic byte validation
  - Create `identity_verification/validators/file_validator.py`
  - Implement FileValidator class with validate(uploaded_file) method
  - Use python-magic to check magic bytes match declared MIME type
  - Check file size against MAX_FILE_SIZE_MB setting
  - Return FileValidationResult dataclass with is_valid, detected_mime, magic_bytes_ok, size_bytes, errors
  - _Requirements: 2.1, 2.4, 2.5, 16.1_

- [x] 2.2 Add Pillow image re-encoding to strip EXIF
  - Update FileValidator to handle image files (PNG, JPEG)
  - Re-encode images through Pillow to strip EXIF metadata
  - Save sanitized image to temporary file
  - Return sanitized file path in FileValidationResult
  - _Requirements: 2.2_

- [x] 2.3 Add pikepdf PDF sanitization
  - Update FileValidator to handle PDF files
  - Use pikepdf to strip JavaScript and embedded files
  - Save sanitized PDF to temporary file
  - Return sanitized file path in FileValidationResult
  - _Requirements: 2.3_

- [x] 2.4 Add file validation error codes
  - Define error codes in `identity_verification/constants.py`
  - Error codes: MISSING_DOCUMENT, FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE, FILE_CORRUPT, FILE_TYPE_MISMATCH
  - Update FileValidator to return structured error codes
  - _Requirements: 1.3, 1.4, 2.4, 2.5_

- [ ]* 2.5 Write unit tests for FileValidator
  - Create `identity_verification/tests/test_file_validator.py`
  - Test magic byte validation for PNG, JPEG, PDF
  - Test file size validation
  - Test EXIF stripping for images
  - Test JavaScript stripping for PDFs
  - Test error code generation
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [-] 2.6 Update RequestAccessSerializer to accept document field 🟡
  - Update `access_requests/serializers.py`
  - Add document field (FileField, required=False for backward compatibility)
  - Keep justification field (CharField, required=False)
  - Add validation: if document is provided, justification is not required
  - Add validation: if justification is provided, document is not required
  - Add early file validation (size, MIME by extension)
  - _Requirements: 1.1, 1.2, 10.1, 10.2_

- [~] 2.7 Checkpoint - File validation complete
  - Test file upload with valid PNG, JPEG, PDF files
  - Test file upload with invalid files (wrong MIME, too large, corrupt)
  - Verify error codes are returned correctly
  - Verify EXIF and JavaScript are stripped
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-3: OCR Extraction (8 tasks)

- [x] 3.1 Add OCR dependencies to requirements.txt
  - Add pytesseract, pdf2image, Pillow, pikepdf, python-magic to `backend/requirements.txt`
  - Pin versions: pytesseract==0.3.10, pdf2image==1.16.3, Pillow==10.1.0, pikepdf==8.7.1, python-magic==0.4.27
  - _Requirements: 3.1_

- [x] 3.2 Implement OCRExtractor (Tesseract wrapper)
  - Create `identity_verification/services/ocr_extractor.py`
  - Implement OCRExtractor class with extract(file_path) method
  - Use pytesseract.image_to_string() for text extraction
  - Use pytesseract.image_to_data() for confidence scores
  - Return OCRResult dataclass with raw_text, overall_confidence, per_field_confidence
  - Handle OCR failures gracefully (return confidence=0)
  - _Requirements: 3.1, 3.3, 3.4, 3.5_

- [-] 3.3 Implement PDF to image conversion
  - Update OCRExtractor to handle PDF files
  - Use pdf2image.convert_from_path() to convert PDF to images
  - Extract text from first page only (Student ID/COR are single-page)
  - Handle multi-page PDFs by processing only page 1
  - _Requirements: 3.2_

- [-] 3.4 Implement FieldExtractor with regex patterns
  - Create `identity_verification/services/field_extractor.py`
  - Implement FieldExtractor class with extract(ocr_result) method
  - Use regex patterns to extract: Full Name, School Name, College, Program, Student Number
  - Return ExtractedFields dataclass with all fields (nullable)
  - Store both raw OCR text and extracted fields
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 3.5 Integrate ProgramNormalizer into FieldExtractor
  - Create `identity_verification/normalizers.py`
  - Implement ProgramNormalizer class with normalize(raw_program) method
  - Add full alias map for BSIS, BSIT, BSCS, ACT
  - Update FieldExtractor to normalize program field
  - Store both program_raw and program (normalized) in ExtractedFields
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 3.6 Add OCR confidence thresholds to settings
  - Update IDENTITY_VERIFICATION settings dict
  - Add OCR_CONFIDENCE_HIGH = 75 (auto-approve threshold)
  - Add OCR_CONFIDENCE_MEDIUM = 60 (manual review threshold)
  - Add OCR_TIMEOUT_SECONDS = 10
  - _Requirements: 7.2, 7.3, 7.4, 14.1, 14.2_

- [ ]* 3.7 Write unit tests for OCR extraction
  - Create `identity_verification/tests/test_ocr_extractor.py`
  - Create hand-crafted OCR fixtures (mock Tesseract output)
  - Test text extraction from images
  - Test confidence score calculation
  - Test PDF to image conversion
  - Test OCR failure handling
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ]* 3.8 Write integration test with real Tesseract
  - Create `identity_verification/tests/test_ocr_integration.py`
  - Use real sample Student ID image (anonymized test data)
  - Run full OCR pipeline with Tesseract
  - Verify extracted fields match expected values
  - Skip test if Tesseract not installed (CI environment)
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.4_

- [~] 3.9 Document Tesseract installation requirements
  - Update `backend/README.md` with Tesseract installation instructions
  - Add instructions for Ubuntu: `apt-get install tesseract-ocr`
  - Add instructions for macOS: `brew install tesseract`
  - Add instructions for Windows: download installer from GitHub
  - Document Dockerfile changes for production deployment
  - _Requirements: 3.1_

- [~] 3.10 Checkpoint - OCR extraction complete
  - Test OCR extraction with sample Student ID images
  - Test OCR extraction with sample COR PDFs
  - Verify field extraction works correctly
  - Verify program normalization works correctly
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-4: Rule-Based Validation (7 tasks)

- [x] 4.1 Implement ProgramNormalizer with full alias map
  - Update `identity_verification/normalizers.py`
  - Add CANONICAL tuple with all 4 canonical program names
  - Add ALIASES dict with all variations (BSIS, BS-IS, BS Information Systems, etc.)
  - Implement case-insensitive, punctuation-ignoring lookup
  - Return canonical name if match found, else original value
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [-] 4.2 Implement RuleValidator with institution/college/program checks
  - Create `identity_verification/validators/rule_validator.py`
  - Implement RuleValidator class with validate(fields) method
  - Check School Name == "Pampanga State University"
  - Check College in ["College of Computing Studies", "CCS"]
  - Check Program in PROGRAMS_CANONICAL
  - Check required fields are not null (Full Name, School Name, College, Program)
  - Return RuleResult dataclass with passed (bool) and failures (list[RuleFailure])
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 4.3 Add canonical reference data to settings
  - Update IDENTITY_VERIFICATION settings dict
  - Add INSTITUTIONS = ('Pampanga State University',)
  - Add COLLEGES = ('College of Computing Studies', 'CCS')
  - Add PROGRAMS_CANONICAL = ('BS Information System', 'BS Information Technology', 'BS Computer Science', 'Associate in Computer Technology')
  - _Requirements: 6.1, 6.2, 6.3_

- [ ]* 4.4 Write unit tests for ProgramNormalizer
  - Create `identity_verification/tests/test_program_normalizer.py`
  - Test all BSIS aliases normalize to "BS Information System"
  - Test all BSIT aliases normalize to "BS Information Technology"
  - Test all BSCS aliases normalize to "BS Computer Science"
  - Test all ACT aliases normalize to "Associate in Computer Technology"
  - Test unknown programs are preserved unchanged
  - Test case-insensitive matching
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

- [ ]* 4.5 Write unit tests for RuleValidator
  - Create `identity_verification/tests/test_rule_validator.py`
  - Test wrong institution rejection
  - Test wrong college rejection
  - Test wrong program rejection
  - Test missing required fields rejection
  - Test valid fields pass validation
  - Test structured RuleFailure objects
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 4.6 Add rule validation audit events
  - Update `identity_verification/services/audit.py` (create if not exists)
  - Define audit event types: access_request.verification.started, access_request.verification.completed, access_request.verification.rejected
  - Implement audit logging with structured metadata (rule_failures, decision_reason)
  - _Requirements: 17.1, 17.2, 17.5_

- [-] 4.7 Update VerificationResult model to store rule_failures
  - Add rule_failures JSONB field to VerificationResult model
  - Create migration to add field
  - Update RuleValidator to serialize RuleFailure objects to JSON
  - _Requirements: 6.8, 13.2_

- [~] 4.8 Checkpoint - Rule validation complete
  - Test rule validation with valid fields (PSU, CCS, valid program)
  - Test rule validation with invalid institution
  - Test rule validation with invalid college
  - Test rule validation with invalid program
  - Test rule validation with missing required fields
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-5: Decision Engine (9 tasks)

- [~] 5.1 Implement DecisionEngine.decide_mvp() (OCR + rule only)
  - Create `identity_verification/services/decision_engine.py`
  - Implement DecisionEngine class with decide_mvp(rule, ocr) method
  - If rule validation fails → return Decision(status='rejected', reason='rule_validation_failed')
  - If rule passes AND OCR confidence >= 75 → return Decision(status='auto_approved', reason='high_confidence')
  - If rule passes AND OCR confidence 60-75 → return Decision(status='pending_manual_review', reason='ocr_medium_confidence')
  - If rule passes AND OCR confidence < 60 → return Decision(status='pending_manual_review', reason='ocr_low_confidence')
  - Return Decision dataclass with status, reason, confidence_summary, flagged_reasons
  - NOTE: NO SBERT, NO TF-IDF, NO anti-replay in MVP
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [~] 5.2 Implement VerificationOrchestrator (synchronous pipeline)
  - Create `identity_verification/services/orchestrator.py`
  - Implement VerificationOrchestrator class with verify_request(access_request_id) method
  - Load AccessRequest and VerificationDocument from database
  - Run FileValidator → if invalid, write VerificationResult(status='rejected') and stop
  - Run OCRExtractor → OCRResult
  - Run FieldExtractor → ExtractedFields
  - Run RuleValidator → RuleResult
  - Run DecisionEngine.decide_mvp() → Decision
  - Write VerificationResult with all artifacts
  - Update AccessRequest.status to match decision
  - Write audit events at each step
  - _Requirements: 7.1, 13.2, 13.6, 17.1, 17.2_

- [~] 5.3 Update RequestAccessView.post() to handle multipart 🔴
  - Update `access_requests/views.py`
  - Check if request.data contains 'document' field
  - If document present → new verification flow
  - If justification present → legacy flow (unchanged)
  - For new flow: validate file with FileValidator early checks
  - Create AccessRequest with status='processing'
  - _Requirements: 1.1, 1.2, 10.1, 10.2_

- [~] 5.4 Persist file to private storage
  - Update RequestAccessView to save uploaded file
  - Generate UUID for request
  - Compute SHA256 hash of file contents
  - Save file to MEDIA_ROOT/private/verification_docs/{uuid}/{sha256}.{ext}
  - Ensure directory permissions are secure (not publicly accessible)
  - _Requirements: 13.3, 15.1, 15.3, 16.2_

- [~] 5.5 Create VerificationDocument row
  - Update RequestAccessView to create VerificationDocument
  - Set access_request_id, file_path, mime_type, sha256, size_bytes, uploaded_at
  - Leave retention_purge_at and purged_at as null (deferred to post-MVP)
  - Link to AccessRequest via FK
  - _Requirements: 13.1, 13.3_

- [~] 5.6 Run verification pipeline inline (synchronous)
  - Update RequestAccessView to call VerificationOrchestrator.verify_request()
  - Run synchronously (IDENTITY_VERIFICATION_SYNC=True in settings)
  - Handle exceptions: catch all, write VerificationResult(status='error'), set AccessRequest to 'pending_manual_review'
  - _Requirements: 7.1, 14.1, 18.5_

- [~] 5.7 Write VerificationResult row
  - VerificationOrchestrator writes VerificationResult after decision
  - Set status, extracted_fields, ocr_raw_text, ocr_confidence, decision_reason, flagged_reasons, processed_at, processor_version
  - Link to AccessRequest via FK
  - _Requirements: 13.2, 13.6, 7.5, 7.6_

- [~] 5.8 Update AccessRequest.status based on decision
  - VerificationOrchestrator updates AccessRequest.status
  - Map decision status to AccessRequest status: 'auto_approved' → 'auto_approved', 'pending_manual_review' → 'pending_manual_review', 'rejected' → 'rejected'
  - _Requirements: 13.6, 7.1_

- [~] 5.9 If AUTO_APPROVED → call existing approve_request() 🟡
  - Update VerificationOrchestrator to check if decision is AUTO_APPROVED
  - Call existing approve_request() service (from access_requests app)
  - Trigger activation email (existing flow)
  - Handle email collision: if approve_request fails, change status to 'pending_manual_review' with reason 'email_collision'
  - Write audit event: access_request.verification.auto_approved
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 17.3_

- [~] 5.10 Checkpoint - Decision engine complete
  - Test end-to-end verification with high OCR confidence (≥75%) → AUTO_APPROVED
  - Test end-to-end verification with medium OCR confidence (60-75%) → PENDING_MANUAL_REVIEW
  - Test end-to-end verification with low OCR confidence (<60%) → PENDING_MANUAL_REVIEW
  - Test end-to-end verification with rule failure → REJECTED
  - Test AUTO_APPROVED triggers activation email
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-6: Admin Integration (4 tasks)

- [~] 6.1 Update admin list endpoint to include new status values 🟡
  - Update `access_requests/views.py` (admin list view)
  - Ensure new status values ('processing', 'auto_approved', 'pending_manual_review') are included in queryset
  - No filtering changes needed (existing filter works with new enum values)
  - _Requirements: 9.1, 10.3_

- [~] 6.2 Add GET /admin/access-requests/{id}/verification/ endpoint
  - Create new view in `identity_verification/views.py`
  - Require IsAdministrator permission
  - Load VerificationResult by access_request_id
  - Return JSON with: extracted_fields, ocr_raw_text, ocr_confidence, decision_reason, flagged_reasons, processor_version
  - For MVP: document_url is NOT included (deferred to post-MVP)
  - Return 404 if VerificationResult not found
  - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

- [~] 6.3 Update AccessRequestListItemSerializer 🟡
  - Update `access_requests/serializers.py`
  - Add verification_status field (read-only, from VerificationResult.status)
  - Add has_verification_data field (boolean, true if VerificationResult exists)
  - Ensure backward compatibility (fields are null for legacy requests)
  - _Requirements: 9.1, 10.3_

- [ ]* 6.4 Write integration test for admin verification endpoint
  - Create `identity_verification/tests/test_admin_views.py`
  - Test admin can view verification data for PENDING_MANUAL_REVIEW request
  - Test admin cannot view verification data without authentication
  - Test 404 for non-existent verification
  - Test extracted fields are returned correctly
  - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

- [~] 6.5 Checkpoint - Admin integration complete
  - Test admin can see PENDING_MANUAL_REVIEW requests in list
  - Test admin can view verification details for PENDING_MANUAL_REVIEW request
  - Test admin can approve PENDING_MANUAL_REVIEW request (existing endpoint)
  - Test admin can deny PENDING_MANUAL_REVIEW request (existing endpoint)
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-7: Frontend Redesign (10 tasks)

- [~] 7.1 Create FileUploadField component
  - Create `frontend/src/components/verification/FileUploadField.jsx`
  - Implement drag-drop file upload area
  - Implement file picker button
  - Display file name and size after selection
  - Show thumbnail preview for images
  - Show PDF icon placeholder for PDFs
  - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [~] 7.2 Update RequestAccessForm to remove justification field
  - Update `frontend/src/components/auth/RequestAccessForm.jsx`
  - Remove justification textarea field
  - Add FileUploadField component
  - Update form state to include document file
  - _Requirements: 1.1, 11.1_

- [~] 7.3 Add client-side file validation
  - Update FileUploadField component
  - Validate file type (PNG, JPEG, PDF only)
  - Validate file size (max 10 MB)
  - Display error messages immediately for invalid files
  - Error codes: FILE_TYPE_NOT_ALLOWED, FILE_TOO_LARGE
  - _Requirements: 1.3, 1.4, 11.5_

- [~] 7.4 Add image/PDF preview
  - Update FileUploadField component
  - For images: display thumbnail using FileReader API
  - For PDFs: display PDF icon with file name
  - Add remove button to clear selection
  - _Requirements: 1.2, 11.3, 11.4_

- [~] 7.5 Update RequestAccessPage to submit multipart form
  - Update `frontend/src/pages/RequestAccessPage.jsx`
  - Change form submission to multipart/form-data
  - Include document file in FormData
  - Handle 202 response with access_request_id
  - _Requirements: 1.1, 1.2_

- [~] 7.6 Add polling for decision status
  - Update RequestAccessPage to poll GET /api/v1/auth/request-access/{id}/status
  - Start polling every 2 seconds after form submission
  - Implement exponential backoff (2s, 4s, 8s, 16s, 32s, 60s max)
  - Stop polling when status is terminal (auto_approved, pending_manual_review, rejected)
  - Handle 404 errors (stop polling, show error)
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [~] 7.7 Show decision result
  - Update RequestAccessPage to display decision status
  - For AUTO_APPROVED: show success message "Your account has been automatically approved! Check your email for activation instructions."
  - For PENDING_MANUAL_REVIEW: show info message "Your request is under review. An administrator will review your document and notify you via email."
  - For REJECTED: show error message with decision_reason
  - _Requirements: 11.7, 11.8, 11.9_

- [~] 7.8 Add loading states
  - Update RequestAccessPage to show loading spinner during upload
  - Show loading spinner during verification (while polling)
  - Disable form submission button during upload/verification
  - _Requirements: 11.6_

- [~] 7.9 Style upload UI for dark mode
  - Update FileUploadField styles
  - Use existing dark mode color palette
  - Add hover states for drag-drop area
  - Add focus states for file picker button
  - Ensure accessibility (ARIA labels, keyboard navigation)
  - _Requirements: 11.1, 11.2_

- [ ]* 7.10 Write frontend integration test
  - Create `frontend/src/tests/RequestAccessPage.test.jsx`
  - Test file upload with valid image
  - Test file upload with valid PDF
  - Test file upload with invalid file (wrong type, too large)
  - Test polling for decision status
  - Test display of AUTO_APPROVED message
  - Test display of PENDING_MANUAL_REVIEW message
  - Test display of REJECTED message
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 11.7, 11.8, 11.9, 12.1_

- [~] 7.11 Checkpoint - Frontend redesign complete
  - Test file upload UI in browser (drag-drop, file picker)
  - Test image preview display
  - Test PDF icon display
  - Test client-side validation (file type, size)
  - Test form submission with document
  - Test polling for decision status
  - Test display of all decision messages
  - Ensure all tests pass, ask the user if questions arise.


### Wave MVP-8: Testing & Documentation (6 tasks)

- [ ]* 8.1 Write end-to-end test (upload → verification → decision → admin approval)
  - Create `identity_verification/tests/test_e2e.py`
  - Test full flow: upload valid Student ID → OCR extraction → rule validation → AUTO_APPROVED → activation email sent
  - Test full flow: upload valid Student ID with medium OCR confidence → PENDING_MANUAL_REVIEW → admin approval → activation email sent
  - Test full flow: upload invalid document (wrong institution) → REJECTED
  - Use real Tesseract OCR (skip if not installed)
  - _Requirements: All functional requirements_

- [ ]* 8.2 Write test for dual-write rollout (JSON and multipart)
  - Create `identity_verification/tests/test_backward_compatibility.py`
  - Test legacy request with justification field (JSON) → processed with legacy flow
  - Test new request with document field (multipart) → processed with verification flow
  - Test RequestAccessSerializer accepts both shapes
  - Verify no VerificationDocument/VerificationResult created for legacy requests
  - _Requirements: 10.1, 10.2, 10.4_

- [ ]* 8.3 Write test for existing pending requests (untouched)
  - Update `identity_verification/tests/test_backward_compatibility.py`
  - Create existing pending request with justification field
  - Verify it appears in admin list unchanged
  - Verify admin can approve/deny using existing endpoints
  - Verify no verification data is created
  - _Requirements: 10.3_

- [~] 8.4 Update README with Tesseract installation
  - Update `backend/README.md`
  - Add "OCR Dependencies" section
  - Document Tesseract installation for Ubuntu, macOS, Windows
  - Document environment variable TESSDATA_PREFIX if needed
  - Add troubleshooting section for common Tesseract issues
  - _Requirements: 3.1_

- [~] 8.5 Update README with new dependencies
  - Update `backend/README.md`
  - Document new Python dependencies: pytesseract, pdf2image, Pillow, pikepdf, python-magic
  - Document system dependencies: tesseract-ocr, poppler-utils (for pdf2image)
  - Add installation instructions for all platforms
  - _Requirements: 3.1_

- [~] 8.6 Document MVP limitations
  - Update `backend/README.md`
  - Add "MVP Limitations" section
  - Document: NO SBERT semantic validation (deferred to post-MVP)
  - Document: NO TF-IDF keyword validation (deferred to post-MVP)
  - Document: NO Celery async processing (synchronous only)
  - Document: NO Redis broker (not required for synchronous processing)
  - Document: NO retention purge jobs (manual cleanup only)
  - Document: NO anti-replay enforcement (deferred to post-MVP)
  - Document: NO advanced admin review endpoints with signed document URLs (basic review only)
  - _Requirements: All non-functional requirements_

- [~] 8.7 Final checkpoint - MVP complete
  - Run full test suite: `python manage.py test`
  - Run frontend tests: `npm test`
  - Verify all tests pass
  - Test end-to-end flow in browser with real Tesseract
  - Test backward compatibility with legacy justification flow
  - Review documentation completeness
  - Ensure all tests pass, ask the user if questions arise.


## Notes

### Regression Risk Markers

- 🔴 **HIGH RISK**: Tasks that modify existing working features (auth system, AccessRequest model)
- 🟡 **MEDIUM RISK**: Tasks that integrate with existing features (serializers, views, admin endpoints)
- 🟢 **LOW RISK**: New code, no existing features touched (most tasks)

### Migration Safety

- **Stage 1 (additive)**: New tables, nullable FKs, new status values — safe and reversible
- **Stage 2 (dual-write)**: Backend accepts both JSON and multipart — backward compatible
- **Stage 3 (deferred)**: Drop justification column — post-MVP cleanup

### Backward Compatibility

- Existing pending requests stay on legacy flow (justification field)
- Admin list includes both old and new status values
- RequestAccessSerializer accepts both shapes during rollout
- No VerificationDocument/VerificationResult created for legacy requests

### Optional Tasks

- Tasks marked with `*` are optional test-related sub-tasks
- These can be skipped for faster MVP delivery
- Core implementation tasks are NOT marked optional and MUST be implemented

### Testing Strategy

- Unit tests for validators, normalizers, extractors
- Integration tests for OCR pipeline with real Tesseract
- End-to-end tests for full verification flow
- Backward compatibility tests for dual-write rollout
- Frontend integration tests for upload UI and polling

### MVP Constraints

- **NO SBERT**: No semantic similarity validation (deferred to post-MVP)
- **NO TF-IDF**: No keyword overlap validation (deferred to post-MVP)
- **NO Celery**: Synchronous processing only (IDENTITY_VERIFICATION_SYNC=True)
- **NO Redis**: Not required for synchronous processing
- **NO async**: All processing happens inline in request thread
- **NO retention jobs**: Manual cleanup only (deferred to post-MVP)
- **NO anti-replay**: Duplicate document detection deferred to post-MVP
- **NO signed URLs**: Basic admin review only (deferred to post-MVP)

### Estimated Time

- Wave MVP-1 (Foundation): ~8-12 hours
- Wave MVP-2 (File Validation): ~6-8 hours
- Wave MVP-3 (OCR Extraction): ~12-16 hours
- Wave MVP-4 (Rule-Based Validation): ~8-10 hours
- Wave MVP-5 (Decision Engine): ~12-16 hours
- Wave MVP-6 (Admin Integration): ~4-6 hours
- Wave MVP-7 (Frontend Redesign): ~12-16 hours
- Wave MVP-8 (Testing & Documentation): ~8-12 hours

**Total: ~80-120 hours** (approximately 2-3 weeks of full-time work)


## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1", "1.2", "1.7", "1.8"]
    },
    {
      "id": 1,
      "tasks": ["1.3", "1.4", "1.5"]
    },
    {
      "id": 2,
      "tasks": ["1.6"]
    },
    {
      "id": 3,
      "tasks": ["2.1", "2.4", "3.1", "4.1", "4.3"]
    },
    {
      "id": 4,
      "tasks": ["2.2", "2.3", "3.2", "3.5", "3.6", "4.6"]
    },
    {
      "id": 5,
      "tasks": ["2.5", "2.6", "3.3", "3.4", "4.2", "4.7"]
    },
    {
      "id": 6,
      "tasks": ["3.7", "3.8", "3.9", "4.4", "4.5"]
    },
    {
      "id": 7,
      "tasks": ["5.1"]
    },
    {
      "id": 8,
      "tasks": ["5.2"]
    },
    {
      "id": 9,
      "tasks": ["5.3", "5.4", "5.5"]
    },
    {
      "id": 10,
      "tasks": ["5.6", "5.7", "5.8"]
    },
    {
      "id": 11,
      "tasks": ["5.9"]
    },
    {
      "id": 12,
      "tasks": ["6.1", "6.3", "7.1"]
    },
    {
      "id": 13,
      "tasks": ["6.2", "7.2", "7.3"]
    },
    {
      "id": 14,
      "tasks": ["6.4", "7.4", "7.5"]
    },
    {
      "id": 15,
      "tasks": ["7.6", "7.8"]
    },
    {
      "id": 16,
      "tasks": ["7.7", "7.9"]
    },
    {
      "id": 17,
      "tasks": ["7.10"]
    },
    {
      "id": 18,
      "tasks": ["8.1", "8.2", "8.3", "8.4", "8.5", "8.6"]
    }
  ]
}
```

### Dependency Graph Explanation

**Wave 0**: Foundation setup (app creation, settings, no dependencies)
- 1.1: Create Django app
- 1.2: Add to INSTALLED_APPS
- 1.7: Configure file storage
- 1.8: Add settings dict

**Wave 1**: Model definitions (depends on app setup)
- 1.3: VerificationDocument model
- 1.4: VerificationResult model
- 1.5: Extend AccessRequest model

**Wave 2**: Schema migration (depends on model definitions)
- 1.6: Write and apply migration

**Wave 3**: Core validators and dependencies (independent implementations)
- 2.1: FileValidator
- 2.4: Error codes
- 3.1: OCR dependencies
- 4.1: ProgramNormalizer
- 4.3: Canonical reference data

**Wave 4**: Enhanced validators (depends on core validators)
- 2.2: Image sanitization (depends on FileValidator)
- 2.3: PDF sanitization (depends on FileValidator)
- 3.2: OCRExtractor (depends on dependencies)
- 3.5: ProgramNormalizer integration (depends on normalizer)
- 3.6: OCR thresholds
- 4.6: Audit events

**Wave 5**: Field extraction and rule validation (depends on extractors)
- 2.5: FileValidator tests
- 2.6: Serializer update (depends on FileValidator)
- 3.3: PDF conversion (depends on OCRExtractor)
- 3.4: FieldExtractor (depends on OCRExtractor)
- 4.2: RuleValidator (depends on ProgramNormalizer)
- 4.7: Rule failures field

**Wave 6**: Testing and documentation for validators (depends on implementations)
- 3.7: OCR unit tests
- 3.8: OCR integration tests
- 3.9: Tesseract documentation
- 4.4: ProgramNormalizer tests
- 4.5: RuleValidator tests

**Wave 7**: Decision engine (depends on all validators)
- 5.1: DecisionEngine.decide_mvp()

**Wave 8**: Orchestrator (depends on decision engine)
- 5.2: VerificationOrchestrator

**Wave 9**: View updates for file handling (depends on orchestrator)
- 5.3: RequestAccessView multipart handling
- 5.4: File persistence
- 5.5: VerificationDocument creation

**Wave 10**: Pipeline execution (depends on view updates)
- 5.6: Run pipeline inline
- 5.7: Write VerificationResult
- 5.8: Update AccessRequest status

**Wave 11**: Auto-approval flow (depends on pipeline execution)
- 5.9: Call approve_request()

**Wave 12**: Admin and frontend foundation (independent)
- 6.1: Admin list update
- 6.3: Serializer update
- 7.1: FileUploadField component

**Wave 13**: Admin endpoint and form updates (depends on foundation)
- 6.2: Admin verification endpoint
- 7.2: Remove justification field
- 7.3: Client-side validation

**Wave 14**: Preview and submission (depends on form updates)
- 6.4: Admin endpoint tests
- 7.4: Image/PDF preview
- 7.5: Multipart form submission

**Wave 15**: Polling and loading states (depends on submission)
- 7.6: Status polling
- 7.8: Loading states

**Wave 16**: Decision display and styling (depends on polling)
- 7.7: Show decision result
- 7.9: Dark mode styling

**Wave 17**: Frontend tests (depends on all frontend features)
- 7.10: Frontend integration tests

**Wave 18**: Final testing and documentation (depends on all features)
- 8.1: End-to-end tests
- 8.2: Dual-write tests
- 8.3: Backward compatibility tests
- 8.4: Tesseract documentation
- 8.5: Dependencies documentation
- 8.6: MVP limitations documentation

