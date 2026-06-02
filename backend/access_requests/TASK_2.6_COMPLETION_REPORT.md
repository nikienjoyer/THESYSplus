# Task 2.6 Completion Report: Update RequestAccessSerializer to Accept Document Field

## Task Overview
**Task ID:** 2.6  
**Description:** Update RequestAccessSerializer to accept an optional document field (file upload)  
**Status:** ✅ COMPLETED

## Requirements Addressed
- ✅ Update RequestAccessSerializer to accept an optional document field (file upload)
- ✅ Add validation for file type and size
- ✅ Ensure backward compatibility with existing API consumers

## Implementation Details

### 1. Serializer Updates (`access_requests/serializers.py`)

#### Added Fields
- **`document`**: `FileField(required=False)` - Accepts file uploads for Student ID or COR
- **`justification`**: Made optional (`required=False`) for backward compatibility

#### Validation Logic

##### Field-Level Validation (`validate_document`)
1. **File Size Validation**
   - Maximum size: 10MB (configurable via `IDENTITY_VERIFICATION['MAX_FILE_SIZE_MB']`)
   - Error code: `FILE_TOO_LARGE`
   - Message: "File size must not exceed 10MB."

2. **File Type Validation**
   - Allowed extensions: `png`, `jpg`, `jpeg`, `pdf`
   - Case-insensitive extension checking
   - Error code: `FILE_TYPE_NOT_ALLOWED`
   - Message: "File type not allowed. Allowed types: png, jpg, jpeg, pdf."

##### Cross-Field Validation (`validate`)
1. **Mutual Exclusivity**
   - Cannot provide both `justification` and `document`
   - Error code: `CONFLICTING_FIELDS`
   - Message: "Cannot provide both justification and document. Use document upload for new requests."

2. **Required Field Check**
   - Must provide either `justification` OR `document`
   - Error code: `MISSING_REQUIRED_FIELD`
   - Message: "Either justification or document must be provided."

### 2. Backward Compatibility

The implementation maintains full backward compatibility:

1. **Legacy Flow (Justification)**
   - Existing clients can continue to submit requests with `justification` field
   - No changes required to existing API consumers
   - Validation rules for `justification` remain unchanged (10-2000 characters)

2. **New Flow (Document Upload)**
   - New clients can submit requests with `document` field
   - Multipart form data support
   - File validation happens at serializer level (early validation)

3. **Dual-Write Support**
   - Serializer accepts both shapes during rollout
   - No breaking changes to existing endpoints
   - Existing pending requests remain unaffected

### 3. Configuration

All validation settings are centralized in `settings.IDENTITY_VERIFICATION`:

```python
IDENTITY_VERIFICATION = {
    'MAX_FILE_SIZE_MB': 10,
    'ALLOWED_EXTENSIONS': ['png', 'jpg', 'jpeg', 'pdf'],
    'ALLOWED_MIME_TYPES': [
        'image/png',
        'image/jpeg',
        'application/pdf',
    ],
    # ... other settings
}
```

## Testing

### Test Coverage (`access_requests/tests.py`)

Created comprehensive test suite with 17 test cases:

#### Legacy Flow Tests
- ✅ `test_legacy_flow_with_justification` - Justification field accepted
- ✅ `test_backward_compatibility_document_optional` - Document field optional
- ✅ `test_justification_too_short` - Min length validation (10 chars)
- ✅ `test_justification_too_long` - Max length validation (2000 chars)

#### New Flow Tests
- ✅ `test_new_flow_with_document` - Document field accepted
- ✅ `test_backward_compatibility_justification_optional` - Justification field optional
- ✅ `test_document_valid_png` - PNG files accepted
- ✅ `test_document_valid_jpg` - JPG files accepted
- ✅ `test_document_valid_jpeg` - JPEG files accepted
- ✅ `test_document_valid_pdf` - PDF files accepted
- ✅ `test_document_case_insensitive_extension` - Case-insensitive extension validation

#### Validation Tests
- ✅ `test_document_file_too_large` - File size limit enforced (>10MB rejected)
- ✅ `test_document_invalid_file_type` - Invalid file types rejected
- ✅ `test_missing_both_justification_and_document` - At least one required
- ✅ `test_both_justification_and_document_provided` - Cannot provide both

#### Other Validation Tests
- ✅ `test_email_validation_institutional_domain` - Email domain validation
- ✅ `test_requested_role_validation` - Role validation (student/faculty only)

### Test Results
```
Ran 17 tests in 0.027s
OK
```

All tests pass successfully! ✅

## API Contract

### Request Format

#### Legacy Flow (JSON)
```json
POST /api/v1/auth/request-access/
Content-Type: application/json

{
  "email": "student@pampangastateu.edu.ph",
  "first_name": "Juan",
  "last_name": "Dela Cruz",
  "requested_role": "student",
  "justification": "I am a student at PSU CCS studying BSIS."
}
```

#### New Flow (Multipart)
```
POST /api/v1/auth/request-access/
Content-Type: multipart/form-data

email: student@pampangastateu.edu.ph
first_name: Juan
last_name: Dela Cruz
requested_role: student
document: [file upload: student_id.png]
```

### Error Responses

#### File Too Large
```json
{
  "document": [
    {
      "message": "File size must not exceed 10MB.",
      "code": "FILE_TOO_LARGE"
    }
  ]
}
```

#### Invalid File Type
```json
{
  "document": [
    {
      "message": "File type not allowed. Allowed types: png, jpg, jpeg, pdf.",
      "code": "FILE_TYPE_NOT_ALLOWED"
    }
  ]
}
```

#### Missing Required Field
```json
{
  "non_field_errors": [
    {
      "message": "Either justification or document must be provided.",
      "code": "MISSING_REQUIRED_FIELD"
    }
  ]
}
```

#### Conflicting Fields
```json
{
  "non_field_errors": [
    {
      "message": "Cannot provide both justification and document. Use document upload for new requests.",
      "code": "CONFLICTING_FIELDS"
    }
  ]
}
```

## Files Modified

1. **`access_requests/serializers.py`**
   - Added `document` field with validation
   - Made `justification` field optional
   - Added `validate_document()` method for file validation
   - Updated `validate()` method for cross-field validation

2. **`access_requests/tests.py`** (NEW)
   - Created comprehensive test suite
   - 17 test cases covering all validation scenarios
   - Tests for both legacy and new flows

## Dependencies

The implementation relies on existing configuration:
- `settings.IDENTITY_VERIFICATION` - Already configured in `thesys/settings/base.py`
- No new dependencies required
- No database migrations needed (serializer-level changes only)

## Next Steps

This task is complete. The serializer now accepts document uploads with proper validation. The next tasks in the pipeline are:

1. **Task 2.7**: Checkpoint - File validation complete
2. **Wave MVP-3**: OCR Extraction implementation
3. **Wave MVP-4**: Rule-Based Validation implementation

## Notes

- ✅ All validation happens at the serializer level (early validation)
- ✅ Full backward compatibility maintained
- ✅ No breaking changes to existing API
- ✅ Comprehensive test coverage
- ✅ Clear error messages with structured error codes
- ✅ Configuration-driven validation (no hardcoded values)

## Verification

To verify the implementation:

```bash
# Run tests
cd backend
python manage.py test access_requests.tests --verbosity=2

# Expected output: Ran 17 tests in 0.027s - OK
```

---

**Task Status:** ✅ COMPLETED  
**Date:** 2024  
**Implemented By:** Kiro AI Assistant
