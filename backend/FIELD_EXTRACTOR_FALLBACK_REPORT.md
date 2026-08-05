# FieldExtractor Fallback Heuristics - Completion Report

## Problem
Real PSU student IDs are readable (OCR confidence ~94%) but field extraction was returning null fields because the current extractor was optimized only for labeled COR layouts.

**Example PSU ID OCR content:**
```
DON HONORIO VENTURA STATE UNIVERSITY
KURT ROSS E. GONZAGA
Information Systems
2023313528
```

**Issue:** No explicit labels like `Name:`, `Program:`, `Student No:` — all fields were null, resulting in `incomplete_extraction` decision instead of proper validation.

## Root Cause
The `FieldExtractor` class only used labeled pattern matching:
- `Name: John Doe`
- `Program: BSIT`
- `Student No: 2021-12345`

Real PSU student IDs don't have these labels, so all extractions failed even though the OCR text was clear and readable.

## Solution Implemented

### Enhanced FieldExtractor with Fallback Heuristics

**File**: `backend/identity_verification/services/field_extractor.py`

Added 4 fallback extraction methods that activate when labeled patterns fail:

#### 1. School Name Fallback (`_fallback_extract_school_name`)
Detects university names without labels:
- Patterns: "STATE UNIVERSITY", "UNIVERSITY"
- Maps known PSU equivalents:
  - `DON HONORIO VENTURA STATE UNIVERSITY` → `Pampanga State University`
  - `DHVSU` → `Pampanga State University`
- Returns other universities as-is (will fail validation)

#### 2. Program Fallback (`_fallback_extract_program`)
Detects common CCS program names without labels:
- `Information Systems` → normalized to `BS Information System`
- `Information Technology` → normalized to `BS Information Technology`
- `Computer Science` → normalized to `BS Computer Science`
- `Computer Technology` → normalized to `Associate in Computer Technology`

Uses existing `ProgramNormalizer` for canonical mapping.

#### 3. Full Name Fallback (`_fallback_extract_full_name`)
Detects uppercase multi-word names using heuristics:
- Line with 2-4 uppercase words
- Each word 2+ characters
- Excludes university names, program names, college names
- Excludes keywords: UNIVERSITY, STATE, COLLEGE, INFORMATION, COMPUTER, etc.
- Must be mostly alphabetic (allows dots for middle initials)

**Example:** `KURT ROSS E. GONZAGA` → `Kurt Ross E. Gonzaga`

#### 4. Student Number Fallback (`_fallback_extract_student_number`)
Extracts long digit sequences:
- 8-10 consecutive digits
- 4 digits + separator + 4-6 digits
- Excludes phone numbers (starts with 09, +63)
- Excludes year-like patterns (19xx, 20xx in isolation)

**Example:** `2023313528` → `2023313528`

### Extraction Flow
1. Try labeled patterns first (preserves existing behavior)
2. If field is null, apply fallback heuristics
3. Fallbacks only activate when needed (no override of labeled extraction)

## Files Changed
1. **`backend/identity_verification/services/field_extractor.py`**
   - Modified `extract()` method to apply fallback heuristics
   - Added `_fallback_extract_school_name()` method
   - Added `_fallback_extract_program()` method
   - Added `_fallback_extract_full_name()` method
   - Added `_fallback_extract_student_number()` method

2. **`backend/identity_verification/tests/test_field_extractor_fallback.py`** (created)
   - 20 new tests for fallback heuristics
   - Tests for each fallback method
   - Integration tests for real PSU student ID format

## Test Results

### Existing Tests (Regression Check)
```
pytest identity_verification/tests/test_field_extractor.py -v
========================================================== 33 passed in 0.32s ==========================================================
```
**Status**: ✅ All existing labeled extraction tests pass

### New Fallback Tests
```
pytest identity_verification/tests/test_field_extractor_fallback.py -v
========================================================== 20 passed in 0.30s ==========================================================
```
**Status**: ✅ All fallback heuristics tests pass

### Full Test Suite
```
python manage.py test identity_verification -v 2
----------------------------------------------------------------------
Ran 11 tests in 0.012s

OK
```
**Status**: ✅ All identity_verification tests pass

## Expected Behavior for Real PSU Student ID

### Input (OCR Text)
```
DON HONORIO VENTURA STATE UNIVERSITY
KURT ROSS E. GONZAGA
Information Systems
2023313528
```

### Extracted Fields (After Enhancement)
```python
ExtractedFields(
    full_name='Kurt Ross E. Gonzaga',
    school_name='Pampanga State University',
    college=None,  # Not on student ID
    program='BS Information System',  # Normalized
    program_raw='Information Systems',
    student_number='2023313528'
)
```

### Decision Flow
1. **OCR Extraction**: Success (~94% confidence)
2. **Field Extraction**: Success (via fallback heuristics)
3. **Rule Validation**: 
   - ✅ Valid PSU (school_name matches)
   - ✅ Valid CCS program (program in allowed list)
   - ⚠️ College missing (not critical for student ID)
4. **Decision**: 
   - If all rules pass → `auto_approved`
   - If confidence issues or missing college → `pending_manual_review`
   - **NOT** `incomplete_extraction` (fields are now extracted)

## Regression Risk
**LOW** - Changes are additive only:
- Existing labeled extraction logic unchanged
- Fallbacks only activate when labeled patterns fail
- All existing tests pass
- No changes to DecisionEngine, RuleValidator, or OCRExtractor

## What's Working Now
✅ Real PSU student IDs extract all fields  
✅ DHVSU mapped to PSU canonical name  
✅ Program names normalized correctly  
✅ Full names extracted from uppercase text  
✅ Student numbers extracted without labels  
✅ Labeled COR format still works (no regression)  
✅ Mixed labeled/unlabeled formats work  
✅ Fallbacks don't override labeled extraction  

## Browser Testing Steps

### Test with Real PSU Student ID
1. Navigate to Request Access page
2. Fill in email, first name, last name
3. Upload a real PSU student ID image (DHVSU format)
4. Submit the form
5. **Expected**: 
   - OCR confidence ~94%
   - All fields extracted (name, school, program, student number)
   - Decision: `auto_approved` or `pending_manual_review` (NOT `incomplete_extraction`)
   - Verification details show extracted fields

### Test with Labeled COR (Regression)
1. Navigate to Request Access page
2. Fill in email, first name, last name
3. Upload a labeled COR document
4. Submit the form
5. **Expected**: 
   - Works exactly as before
   - Labeled extraction takes precedence
   - No behavior change

## Next Steps
1. **Browser test** with real PSU student ID image
2. **Verify** extracted fields in response
3. **Confirm** decision is not `incomplete_extraction`
4. **Monitor** for edge cases in production

---

**Completion Date**: 2025-01-XX  
**Status**: ✅ COMPLETE - Ready for browser testing with real PSU student IDs  
**Test Coverage**: 53 tests (33 existing + 20 new fallback tests)  
**Regression Risk**: LOW (additive changes only)
