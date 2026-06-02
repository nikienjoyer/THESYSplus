# Requirements Document

## Introduction

This document specifies the requirements for the **AI-Assisted Identity Verification MVP** feature for THESYS+. This MVP replaces the free-text `justification` field on the Request Access form with an uploaded **Student ID** or **Certificate of Registration (COR)** document. The system uses OCR (Tesseract) and rule-based validation to automatically verify that applicants belong to the College of Computing Studies at Pampanga State University.

### MVP Scope

This is a **capstone-safe MVP implementation** that delivers core identity verification functionality using synchronous processing and rule-based validation only. The MVP includes:

- File upload interface (replaces justification field)
- OCR extraction using Tesseract
- Rule-based validation (institution, college, program)
- Program name normalization
- Simplified decision engine (OCR confidence + rule validation only)
- Admin review integration with existing approve/deny endpoints
- Backward compatibility with legacy justification flow

### Explicitly Out of Scope (Deferred to Post-MVP)

The following features are architecturally planned in the design document but **NOT included in this MVP**:

- **SBERT semantic validation** (V5) — no machine learning models
- **TF-IDF keyword validation** (V6) — no machine learning models
- **Celery async processing** (V8) — synchronous processing only
- **Redis broker** (V8) — not required for synchronous processing
- **Advanced admin review endpoints** with signed document URLs (V9) — basic review only
- **Property-based testing expansion** (V11) — standard unit/integration tests only
- **Retention purge jobs** (V12) — manual cleanup only
- **Anti-replay enforcement** (V12) — deferred to post-MVP

These features may be implemented after the capstone project is complete.

### Relationship to Existing System

This feature **does not modify** the existing authentication system (Waves A1–A12). The verification pipeline integrates with the existing `approve_request()` and `deny_request()` services without changing their contracts. Existing pending requests remain on the legacy justification flow and continue to be reviewed manually.

---

## Glossary

- **Student ID**: A physical or digital identification card issued by Pampanga State University containing the student's photo, name, student number, program, and college affiliation.
- **COR (Certificate of Registration)**: An official document issued by Pampanga State University each semester listing the student's enrolled courses, program, college, and academic year.
- **OCR (Optical Character Recognition)**: Technology that extracts text from images or PDF documents. This MVP uses Tesseract OCR.
- **Tesseract**: An open-source OCR engine that converts images of text into machine-readable text with confidence scores.
- **Rule-Based Validation**: A deterministic validation process that checks extracted fields against exact institutional requirements (institution name, college name, program name).
- **Program Normalization**: The process of mapping OCR-extracted program name variations and abbreviations (e.g., "BSIS", "BS-IS", "BS Information Systems") to canonical program names (e.g., "BS Information System").
- **Verification Pipeline**: The complete automated process: file upload → validation → OCR extraction → field extraction → program normalization → rule validation → decision.
- **Decision Engine**: The component that determines the final status (AUTO_APPROVED, PENDING_MANUAL_REVIEW, REJECTED) based on OCR confidence and rule validation results.
- **AUTO_APPROVED**: A verification status indicating all validation checks passed with high OCR confidence (≥75%), triggering automatic account provisioning.
- **PENDING_MANUAL_REVIEW**: A verification status indicating medium OCR confidence (60-75%) or other uncertainty, requiring administrator review.
- **REJECTED**: A verification status indicating validation failure (wrong institution, college, or program, or missing required information).
- **Verification_System**: The identity verification subsystem responsible for processing uploaded documents.
- **Request_Access_Form**: The web form where unprovisioned users submit their information and documents to request system access.
- **Admin_Panel**: The administrative interface where administrators review and approve/deny access requests.

---

## Functional Requirements

### Requirement 1: File Upload Interface

**User Story:** As an unprovisioned user, I want to upload my Student ID or COR instead of writing a justification, so that my identity can be verified automatically.

#### Acceptance Criteria

1. WHERE the user is on the Request Access form, THE Request_Access_Form SHALL accept file uploads of type png, jpg, jpeg, pdf
2. WHERE the user uploads a file, THE Request_Access_Form SHALL display a preview of the uploaded document
3. WHERE the user uploads a file larger than 10 MB, THE Request_Access_Form SHALL reject the upload with error code FILE_TOO_LARGE
4. WHERE the user uploads an unsupported file type, THE Request_Access_Form SHALL reject the upload with error code FILE_TYPE_NOT_ALLOWED
5. WHERE the user submits the form without a document, THE Request_Access_Form SHALL reject the submission with error code MISSING_DOCUMENT
6. WHERE the user drags and drops a file onto the upload area, THE Request_Access_Form SHALL accept the file as if selected via file picker
7. WHERE the user uploads a valid file, THE Request_Access_Form SHALL display the file name and size

### Requirement 2: File Validation and Security

**User Story:** As the system, I want to validate uploaded files for security and integrity, so that malicious files cannot compromise the system.

#### Acceptance Criteria

1. WHERE a file is uploaded, THE Verification_System SHALL verify the file's magic bytes match the declared MIME type
2. WHERE an image file is uploaded, THE Verification_System SHALL re-encode the image through Pillow to strip EXIF metadata
3. WHERE a PDF file is uploaded, THE Verification_System SHALL strip JavaScript and embedded files via pikepdf
4. WHERE file validation fails due to corrupt or malicious content, THE Verification_System SHALL reject the upload with error code FILE_CORRUPT
5. WHERE the file's magic bytes do not match the file extension, THE Verification_System SHALL reject the upload with error code FILE_TYPE_MISMATCH
6. WHERE a file passes validation, THE Verification_System SHALL compute and store the SHA256 hash of the file contents

### Requirement 3: OCR Text Extraction

**User Story:** As the system, I want to extract identity fields from uploaded documents using OCR, so that I can validate the user's institution and program.

#### Acceptance Criteria

1. WHERE a valid image document is uploaded, THE Verification_System SHALL extract text using Tesseract OCR
2. WHERE a valid PDF document is uploaded, THE Verification_System SHALL convert the PDF to images using pdf2image then extract text using Tesseract OCR
3. WHERE OCR extraction completes, THE Verification_System SHALL record the overall OCR confidence score on a scale of 0 to 100
4. WHERE OCR extraction completes, THE Verification_System SHALL record per-field confidence scores for each extracted field
5. WHERE OCR extraction fails due to unreadable content, THE Verification_System SHALL record an overall confidence score of 0

### Requirement 4: Field Extraction from OCR Text

**User Story:** As the system, I want to extract structured identity fields from raw OCR text, so that I can perform rule-based validation.

#### Acceptance Criteria

1. WHERE OCR text is available, THE Verification_System SHALL extract the Full Name field using regex and heuristic patterns
2. WHERE OCR text is available, THE Verification_System SHALL extract the School Name field using regex and heuristic patterns
3. WHERE OCR text is available, THE Verification_System SHALL extract the College field using regex and heuristic patterns
4. WHERE OCR text is available, THE Verification_System SHALL extract the Program field using regex and heuristic patterns
5. WHERE OCR text contains a student number, THE Verification_System SHALL optionally extract the Student Number field
6. WHERE a required field cannot be extracted, THE Verification_System SHALL record the field value as null
7. WHERE field extraction completes, THE Verification_System SHALL store both the raw OCR text and the extracted structured fields

### Requirement 5: Program Name Normalization

**User Story:** As the system, I want to normalize program name aliases and abbreviations, so that OCR variations are handled correctly.

#### Acceptance Criteria

1. WHERE the extracted Program is "BSIS" or "BS-IS" or "BS Information Systems" or "Bachelor of Science in Information Systems", THE Verification_System SHALL normalize to "BS Information System"
2. WHERE the extracted Program is "BSIT" or "BS-IT" or "BS Information Technologies" or "Bachelor of Science in Information Technology", THE Verification_System SHALL normalize to "BS Information Technology"
3. WHERE the extracted Program is "BSCS" or "BS-CS" or "Bachelor of Science in Computer Science", THE Verification_System SHALL normalize to "BS Computer Science"
4. WHERE the extracted Program is "ACT" or "Associate in Computer Tech", THE Verification_System SHALL normalize to "Associate in Computer Technology"
5. WHERE program normalization is performed, THE Verification_System SHALL store both the raw extracted program name and the normalized canonical program name
6. WHERE the extracted Program does not match any known alias, THE Verification_System SHALL preserve the original extracted value without normalization

### Requirement 6: Rule-Based Validation

**User Story:** As the system, I want to validate that extracted fields match institutional requirements, so that only CCS students and faculty are approved.

#### Acceptance Criteria

1. WHERE the extracted School Name is not "Pampanga State University", THE Verification_System SHALL fail validation with reason "wrong_institution"
2. WHERE the extracted College is not "College of Computing Studies" and not "CCS", THE Verification_System SHALL fail validation with reason "wrong_college"
3. WHERE the normalized Program is not one of "BS Information System", "BS Information Technology", "BS Computer Science", "Associate in Computer Technology", THE Verification_System SHALL fail validation with reason "wrong_program"
4. WHERE the Full Name field is missing or null, THE Verification_System SHALL fail validation with reason "missing_required_information"
5. WHERE the School Name field is missing or null, THE Verification_System SHALL fail validation with reason "missing_required_information"
6. WHERE the College field is missing or null, THE Verification_System SHALL fail validation with reason "missing_required_information"
7. WHERE the Program field is missing or null, THE Verification_System SHALL fail validation with reason "missing_required_information"
8. WHERE all required fields are present and match institutional requirements, THE Verification_System SHALL pass rule validation

### Requirement 7: Decision Engine (MVP - Simplified)

**User Story:** As the system, I want to automatically approve valid requests or flag uncertain ones for manual review, so that administrators only review edge cases.

#### Acceptance Criteria

1. WHERE rule validation fails, THE Verification_System SHALL set status to REJECTED with the specific rule failure reason
2. WHERE rule validation passes AND OCR overall confidence is greater than or equal to 75, THE Verification_System SHALL set status to AUTO_APPROVED
3. WHERE rule validation passes AND OCR overall confidence is between 60 and 75 inclusive, THE Verification_System SHALL set status to PENDING_MANUAL_REVIEW with reason "ocr_medium_confidence"
4. WHERE rule validation passes AND OCR overall confidence is less than 60, THE Verification_System SHALL set status to PENDING_MANUAL_REVIEW with reason "ocr_low_confidence"
5. WHERE the decision is made, THE Verification_System SHALL record the decision reason in the verification result
6. WHERE the decision is made, THE Verification_System SHALL record a confidence summary containing the OCR confidence score

### Requirement 8: AUTO_APPROVED Flow

**User Story:** As the system, I want to automatically provision accounts for high-confidence valid requests, so that users don't wait for manual review.

#### Acceptance Criteria

1. WHERE a request is AUTO_APPROVED, THE Verification_System SHALL call the existing approve_request service
2. WHERE the approve_request service succeeds, THE Verification_System SHALL trigger the activation email to be sent to the user
3. WHERE the approve_request service fails due to email collision, THE Verification_System SHALL change the status to PENDING_MANUAL_REVIEW with reason "email_collision"
4. WHERE a request is AUTO_APPROVED, THE Verification_System SHALL update the AccessRequest status to APPROVED
5. WHERE a request is AUTO_APPROVED, THE Verification_System SHALL write an audit event access_request.verification.auto_approved

### Requirement 9: Admin Review Integration

**User Story:** As an administrator, I want to review PENDING_MANUAL_REVIEW requests with extracted fields visible, so that I can make informed approval decisions.

#### Acceptance Criteria

1. WHERE an administrator views the access request list, THE Admin_Panel SHALL include requests with status PENDING_MANUAL_REVIEW
2. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the extracted Full Name field
3. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the extracted School Name field
4. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the extracted College field
5. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the extracted Program field
6. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the extracted Student Number field if available
7. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the OCR raw text
8. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the OCR confidence score
9. WHERE an administrator views a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL display the decision reason
10. WHERE an administrator approves a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL call the existing approve_request service unchanged
11. WHERE an administrator denies a PENDING_MANUAL_REVIEW request, THE Admin_Panel SHALL call the existing deny_request service unchanged

### Requirement 10: Backward Compatibility

**User Story:** As the system, I want to support both the legacy justification flow and the new document upload flow during rollout, so that existing clients don't break.

#### Acceptance Criteria

1. WHERE a request is submitted with a justification field in JSON format, THE Verification_System SHALL process it using the legacy flow without verification
2. WHERE a request is submitted with a document field in multipart format, THE Verification_System SHALL process it using the new verification flow
3. WHERE existing pending requests exist with justification field populated, THE Admin_Panel SHALL continue to display them in the admin list unchanged
4. WHERE a legacy request is submitted, THE Verification_System SHALL not create VerificationDocument or VerificationResult records
5. WHERE a new verification request is submitted, THE Verification_System SHALL create both VerificationDocument and VerificationResult records

### Requirement 11: Frontend Upload UI

**User Story:** As an unprovisioned user, I want a clear upload interface with preview and validation feedback, so that I know my document was received correctly.

#### Acceptance Criteria

1. WHERE the user is on the Request Access form, THE Request_Access_Form SHALL display a file upload field with drag-drop support
2. WHERE the user is on the Request Access form, THE Request_Access_Form SHALL display a file upload field with file picker button
3. WHERE the user uploads an image file, THE Request_Access_Form SHALL display a thumbnail preview of the image
4. WHERE the user uploads a PDF file, THE Request_Access_Form SHALL display a PDF icon placeholder
5. WHERE the user uploads an invalid file, THE Request_Access_Form SHALL display an error message immediately via client-side validation
6. WHERE the user submits the form, THE Request_Access_Form SHALL display a loading state during upload and verification
7. WHERE verification completes with AUTO_APPROVED status, THE Request_Access_Form SHALL display a success message indicating automatic approval
8. WHERE verification completes with PENDING_MANUAL_REVIEW status, THE Request_Access_Form SHALL display a message indicating manual review is required
9. WHERE verification completes with REJECTED status, THE Request_Access_Form SHALL display an error message with the rejection reason

### Requirement 12: Verification Status Polling

**User Story:** As an unprovisioned user, I want to see the verification status update in real-time, so that I know when my request has been processed.

#### Acceptance Criteria

1. WHERE a document upload is submitted, THE Request_Access_Form SHALL begin polling the status endpoint every 2 seconds
2. WHERE the status remains PROCESSING after multiple polls, THE Request_Access_Form SHALL increase the polling interval using exponential backoff
3. WHERE the polling interval reaches 60 seconds, THE Request_Access_Form SHALL not increase the interval further
4. WHERE the status changes to a terminal state, THE Request_Access_Form SHALL stop polling
5. WHERE the status endpoint returns 404, THE Request_Access_Form SHALL stop polling and display an error message
6. WHERE the status endpoint returns an error, THE Request_Access_Form SHALL retry with exponential backoff up to 3 times

### Requirement 13: Data Persistence

**User Story:** As the system, I want to persist verification artifacts for audit and review, so that administrators can investigate decisions.

#### Acceptance Criteria

1. WHERE a document is uploaded, THE Verification_System SHALL create a VerificationDocument record with file path, MIME type, SHA256 hash, and size
2. WHERE verification completes, THE Verification_System SHALL create a VerificationResult record with status, extracted fields, OCR text, OCR confidence, and decision reason
3. WHERE a VerificationDocument is created, THE Verification_System SHALL store the file in private storage at MEDIA_ROOT/private/verification_docs/{uuid}/{sha256}.{ext}
4. WHERE a VerificationResult is created, THE Verification_System SHALL link it to the corresponding AccessRequest via foreign key
5. WHERE a VerificationDocument is created, THE Verification_System SHALL link it to the corresponding AccessRequest via foreign key
6. WHERE verification completes, THE Verification_System SHALL update the AccessRequest status field to match the verification decision

---

## Non-Functional Requirements

### Requirement 14: Performance

**User Story:** As a user, I want document verification to complete quickly, so that I receive feedback without long delays.

#### Acceptance Criteria

1. WHERE a document is uploaded, THE Verification_System SHALL complete verification within 10 seconds for synchronous processing
2. WHERE OCR processing takes longer than 10 seconds, THE Verification_System SHALL timeout and set status to PENDING_MANUAL_REVIEW with reason "ocr_timeout"
3. WHERE the verification pipeline encounters a performance bottleneck, THE Verification_System SHALL log performance metrics for investigation

### Requirement 15: Security - File Storage

**User Story:** As the system, I want to store uploaded documents securely, so that sensitive PII is protected.

#### Acceptance Criteria

1. WHERE a file is uploaded, THE Verification_System SHALL store it in private storage that is not publicly accessible
2. WHERE an administrator views a document, THE Verification_System SHALL serve it through an authenticated endpoint that requires administrator privileges
3. WHERE a file path is generated, THE Verification_System SHALL use a UUID-based path that is not user-controllable
4. WHERE a file is stored, THE Verification_System SHALL ensure the storage directory has appropriate filesystem permissions

### Requirement 16: Security - File Validation

**User Story:** As the system, I want to validate file integrity using cryptographic methods, so that file tampering is detectable.

#### Acceptance Criteria

1. WHERE a file is uploaded, THE Verification_System SHALL verify magic bytes match the declared MIME type, not just the file extension
2. WHERE a file is persisted, THE Verification_System SHALL compute the SHA256 hash of the file contents
3. WHERE a file is retrieved from storage, THE Verification_System SHALL verify the SHA256 hash matches the stored hash value

### Requirement 17: Auditability

**User Story:** As a system administrator, I want comprehensive audit logs of all verification activities, so that I can investigate issues and ensure compliance.

#### Acceptance Criteria

1. WHERE verification starts, THE Verification_System SHALL write audit event access_request.verification.started with document SHA256
2. WHERE verification completes, THE Verification_System SHALL write audit event access_request.verification.completed with decision and processor version
3. WHERE a request is AUTO_APPROVED, THE Verification_System SHALL write audit event access_request.verification.auto_approved with confidence summary
4. WHERE a request is PENDING_MANUAL_REVIEW, THE Verification_System SHALL write audit event access_request.verification.pending_review with flagged reasons
5. WHERE a request is REJECTED, THE Verification_System SHALL write audit event access_request.verification.rejected with decision reason and rule failures
6. WHERE an administrator overrides a decision, THE Verification_System SHALL write audit event access_request.verification.admin_override with original decision, override decision, and reason

### Requirement 18: Error Handling

**User Story:** As the system, I want to handle errors gracefully, so that users receive clear feedback and administrators can investigate failures.

#### Acceptance Criteria

1. WHERE file validation fails, THE Verification_System SHALL return HTTP 400 with a structured error code
2. WHERE Tesseract OCR fails, THE Verification_System SHALL set status to PENDING_MANUAL_REVIEW with reason "ocr_failure"
3. WHERE field extraction fails to find required fields, THE Verification_System SHALL proceed with null values and let rule validation handle the failure
4. WHERE database write fails during result persist, THE Verification_System SHALL log the error and return HTTP 500
5. WHERE an uncaught exception occurs in the pipeline, THE Verification_System SHALL set status to PENDING_MANUAL_REVIEW with reason "pipeline_error"
6. WHERE an error occurs, THE Verification_System SHALL write audit event access_request.verification.error with exception class

### Requirement 19: Rate Limiting

**User Story:** As the system, I want to rate limit document uploads, so that abuse and resource exhaustion are prevented.

#### Acceptance Criteria

1. THE Verification_System SHALL enforce the existing rate limit of 5 requests per hour per IP address
2. THE Verification_System SHALL enforce the existing rate limit of 3 requests per day per email address
3. WHERE the status polling endpoint is called, THE Verification_System SHALL enforce a rate limit of 30 requests per minute per IP address
4. WHERE a rate limit is exceeded, THE Verification_System SHALL return HTTP 429 with a Retry-After header

### Requirement 20: Observability

**User Story:** As a system operator, I want structured logs and metrics for verification activities, so that I can monitor system health and performance.

#### Acceptance Criteria

1. WHERE verification occurs, THE Verification_System SHALL log structured JSON with fields access_request_id, document_sha256, decision, ocr_confidence
2. WHERE OCR extraction occurs, THE Verification_System SHALL record the latency in seconds
3. WHERE a decision is made, THE Verification_System SHALL increment a counter metric verification_decision_total with label status
4. WHERE an error occurs, THE Verification_System SHALL increment a counter metric verification_error_total with label error_type

---

## Acceptance Criteria Summary

The MVP is considered complete when:

1. Users can upload Student ID or COR files (PNG, JPG, JPEG, PDF) instead of writing a justification
2. The system validates uploaded files for security (magic bytes, MIME type, size, sanitization)
3. Tesseract OCR extracts text from uploaded documents with confidence scores
4. Field extraction identifies Full Name, School Name, College, Program, and optionally Student Number
5. Program name normalization handles common aliases (BSIS, BSIT, BSCS, ACT)
6. Rule-based validation rejects documents from wrong institution, college, or program
7. The decision engine produces AUTO_APPROVED (OCR ≥75%), PENDING_MANUAL_REVIEW (OCR 60-75%), or REJECTED (rule failure or OCR <60%)
8. AUTO_APPROVED requests trigger the existing activation email flow automatically
9. Administrators can review PENDING_MANUAL_REVIEW requests with all extracted fields and OCR data visible
10. The admin panel integrates with existing approve_request and deny_request services without modification
11. Existing pending requests with justification field continue to work unchanged (backward compatibility)
12. The frontend displays a file upload interface with drag-drop, preview, and real-time status updates
13. All verification steps complete synchronously within 10 seconds
14. Comprehensive audit events are written for all verification activities
15. Uploaded documents are stored securely in private storage
16. Rate limiting prevents abuse (5/hr per IP, 3/day per email, 30/min for status polling)
17. Structured logs and metrics enable monitoring and troubleshooting
