# Failed Field Extraction Diagnostic Report

## Request Information
- **Access Request ID**: `600fe2b0-36af-4391-9c0d-48d719894340`
- **Verification Result ID**: `23c8d733-00b9-446a-ad11-4b08f60f9e65`
- **OCR Confidence**: 53.6%
- **Status**: `pending_manual_review`
- **Decision Reason**: `incomplete_extraction`

---

## 1. Raw OCR Text

```
«DON AGI

2S TA Tub: a ad
```

**Characteristics**:
- Length: 25 characters
- Lines: 3 lines
- Extremely corrupted/garbled text
- Contains special characters: `«`
- Fragmented words: "DON AGI", "2S TA Tub: a ad"

---

## 2. Direct FieldExtractor Output

Tested the FieldExtractor directly against the raw OCR text:

```python
ExtractedFields(
    full_name=None,
    school_name=None,
    college=None,
    program=None,
    program_raw=None,
    student_number=None
)
```

**Result**: Complete extraction failure - no fields extracted

---

## 3. Why Extraction Failed

### Pattern Detection Analysis

| Pattern | Expected | Found | Status |
|---------|----------|-------|--------|
| University name | "PAMPANGA STATE UNIVERSITY" or "DHVSU" | None | ❌ Not found |
| Program keywords | "Information Systems", "Computer Science", etc. | None | ❌ Not found |
| Student number | 8-10 digit number | None | ❌ Not found |
| Name pattern | 2-4 uppercase words | "«DON AGI" | ⚠️ Partial/corrupted |

### Specific Issues

1. **University Name**: 
   - Expected: "DON HONORIO VENTURA STATE UNIVERSITY"
   - Found: "«DON AGI" (severely truncated and corrupted)
   - The text is too fragmented to match any university pattern

2. **Program Name**:
   - Expected: "Information Systems", "Computer Science", etc.
   - Found: "2S TA Tub: a ad" (completely garbled)
   - No recognizable program keywords

3. **Student Number**:
   - Expected: 8-10 consecutive digits (e.g., "2023313528")
   - Found: "2S" (only 2 characters, mixed with letters)
   - No valid number sequence

4. **Full Name**:
   - Expected: 2-4 uppercase words (e.g., "KURT ROSS E. GONZAGA")
   - Found: "«DON AGI" (contains special character, incomplete)
   - Fallback pattern detected it as potential name but it's corrupted

---

## 4. Root Cause Analysis

### Primary Cause: **OCR Quality Issue**

**Evidence**:
- OCR confidence: 53.6% (well below 75% threshold)
- Text is severely corrupted and garbled
- Only 25 characters extracted from entire document
- Contains special characters and fragmented words
- No complete words or recognizable patterns

**Conclusion**: This is **NOT a regex/pattern issue**. The OCR extraction itself failed to produce readable text.

### Why OCR Failed

Possible reasons for low OCR quality:
1. **Image Quality**: Blurry, low resolution, or poor lighting
2. **Document Condition**: Faded, damaged, or worn document
3. **Scan Quality**: Poor scan settings or camera angle
4. **File Format**: Compressed or low-quality image format
5. **Orientation**: Document rotated or skewed
6. **Obstruction**: Glare, shadows, or partial coverage

### What the OCR Likely Tried to Read

Based on the fragments:
- "«DON AGI" → Likely part of "DON HONORIO VENTURA" (severely truncated)
- "2S TA Tub: a ad" → Completely unreadable, possibly:
  - Part of university name
  - Part of student information
  - Noise from poor image quality

---

## 5. Comparison: Expected vs Actual

### Expected OCR Text (from real PSU ID)
```
DON HONORIO VENTURA STATE UNIVERSITY
KURT ROSS E. GONZAGA
Information Systems
2023313528
```

### Actual OCR Text (from failed request)
```
«DON AGI

2S TA Tub: a ad
```

**Difference**: The actual OCR text is ~95% corrupted compared to expected format.

---

## 6. Can Regex/Patterns Fix This?

**NO** - Regex patterns cannot fix this issue because:

1. **Insufficient Data**: Only 25 characters extracted, most are corrupted
2. **No Complete Words**: No recognizable words to match against
3. **Structural Damage**: Text structure is completely lost
4. **Special Characters**: Contains non-text characters (`«`)
5. **Fragmentation**: Words are split and incomplete

**Example**:
- Pattern expects: "DON HONORIO VENTURA STATE UNIVERSITY"
- OCR provides: "«DON AGI"
- No amount of regex flexibility can bridge this gap

Even with very permissive patterns:
- `r'DON.*VENTURA'` → Would not match "«DON AGI"
- `r'.*DON.*'` → Would match but provides no useful information
- Fuzzy matching would still fail due to extreme corruption

---

## 7. Recommendations

### Immediate Action
1. **Request Better Image**: Ask user to upload a clearer, higher-quality image
2. **Manual Review**: Admin should review the original document manually
3. **Status**: Keep as `pending_manual_review` (correct decision)

### Image Quality Guidelines for Users
Provide users with upload guidelines:
- Use good lighting (no shadows or glare)
- Hold camera steady (avoid blur)
- Capture entire document (no cropping)
- Use high resolution (at least 1200x1600 pixels)
- Ensure document is flat (no wrinkles or folds)
- Avoid reflective surfaces
- Use portrait orientation
- File format: PNG or JPG (not compressed)

### System Improvements (Future)
1. **Pre-upload Validation**: Check image quality before upload
2. **Image Enhancement**: Apply preprocessing (contrast, sharpness, deskew)
3. **OCR Confidence Threshold**: Reject uploads with <50% confidence immediately
4. **User Feedback**: Show OCR confidence and suggest retake if low
5. **Multiple Attempts**: Allow users to upload multiple images

---

## 8. Summary

| Aspect | Finding |
|--------|---------|
| **OCR Confidence** | 53.6% (LOW) |
| **Text Quality** | Severely corrupted |
| **Extraction Result** | Complete failure (all fields null) |
| **Root Cause** | OCR quality issue |
| **Regex Issue?** | NO - patterns are fine |
| **Can Be Fixed?** | NO - need better image |
| **Correct Decision** | YES - `pending_manual_review` is appropriate |

---

## 9. Diagnostic Commands Used

```bash
# Run diagnostic script
cd backend
python diagnose_failed_extraction.py

# Query database directly
python manage.py shell
from identity_verification.models import VerificationResult
result = VerificationResult.objects.get(access_request_id='600fe2b0-36af-4391-9c0d-48d719894340')
print(result.ocr_raw_text)
print(result.ocr_confidence)
```

---

## Conclusion

**This is an OCR QUALITY ISSUE, not a regex/pattern issue.**

The uploaded document image was too poor quality for OCR to extract readable text. The OCR confidence of 53.6% and the severely corrupted output ("«DON AGI" instead of "DON HONORIO VENTURA STATE UNIVERSITY") indicate that the problem is with the source image, not with the field extraction patterns.

**No code changes are needed.** The system correctly identified this as `incomplete_extraction` and set the status to `pending_manual_review`, which is the appropriate response for low-quality OCR.

**User action required**: Upload a clearer, higher-quality image of the document.

---

**Report Generated**: 2025-01-XX  
**Status**: ✅ DIAGNOSTIC COMPLETE  
**Action Required**: Request better image from user
