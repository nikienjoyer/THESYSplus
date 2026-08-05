# Task 3.6 Verification: OCR Confidence Thresholds Added to Settings

## Task Description
Add OCR confidence threshold settings to IDENTITY_VERIFICATION settings dict for auto-approval and manual review thresholds.

## Changes Made

### Updated File
- `backend/thesys/settings/base.py`

### Settings Added
The following OCR confidence threshold settings have been added to the `IDENTITY_VERIFICATION` dictionary:

1. **OCR_CONFIDENCE_HIGH**: 75
   - Auto-approve threshold
   - Requests with OCR confidence ≥ 75% will be automatically approved (if rules pass)

2. **OCR_CONFIDENCE_MEDIUM**: 60
   - Manual review threshold
   - Requests with OCR confidence between 60-75% will be flagged for manual review

3. **OCR_TIMEOUT_SECONDS**: 10
   - Maximum time allowed for OCR processing
   - Prevents hanging on difficult-to-process documents

### Backward Compatibility
The legacy nested structure `OCR_CONFIDENCE_THRESHOLDS` has been retained for backward compatibility with existing tests:
```python
'OCR_CONFIDENCE_THRESHOLDS': {
    'HIGH': 75,
    'MEDIUM': 60,
}
```

## Verification

### Settings Verification
```bash
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thesys.settings.dev'); import django; django.setup(); from django.conf import settings; print('OCR_CONFIDENCE_HIGH:', settings.IDENTITY_VERIFICATION['OCR_CONFIDENCE_HIGH']); print('OCR_CONFIDENCE_MEDIUM:', settings.IDENTITY_VERIFICATION['OCR_CONFIDENCE_MEDIUM']); print('OCR_TIMEOUT_SECONDS:', settings.IDENTITY_VERIFICATION['OCR_TIMEOUT_SECONDS'])"
```

Expected output:
```
OCR_CONFIDENCE_HIGH: 75
OCR_CONFIDENCE_MEDIUM: 60
OCR_TIMEOUT_SECONDS: 10
```

### Complete Settings Structure
```json
{
  "SYNC_MODE": true,
  "MAX_FILE_SIZE_MB": 10,
  "ALLOWED_EXTENSIONS": ["png", "jpg", "jpeg", "pdf"],
  "ALLOWED_MIME_TYPES": ["image/png", "image/jpeg", "application/pdf"],
  "OCR_CONFIDENCE_HIGH": 75,
  "OCR_CONFIDENCE_MEDIUM": 60,
  "OCR_CONFIDENCE_THRESHOLDS": {
    "HIGH": 75,
    "MEDIUM": 60
  },
  "OCR_TIMEOUT_SECONDS": 10,
  "INSTITUTIONS": ["Pampanga State University"],
  "COLLEGES": ["College of Computing Studies", "CCS"],
  "PROGRAMS_CANONICAL": [
    "BS Information System",
    "BS Information Technology",
    "BS Computer Science",
    "Associate in Computer Technology"
  ]
}
```

## Requirements Satisfied
- ✅ Requirement 7.2: OCR confidence thresholds for auto-approval
- ✅ Requirement 7.3: OCR confidence thresholds for manual review
- ✅ Requirement 7.4: OCR confidence threshold configuration
- ✅ Requirement 14.1: Performance settings (timeout)
- ✅ Requirement 14.2: OCR timeout configuration

## Status
✅ **COMPLETE** - All OCR confidence threshold settings have been successfully added to the IDENTITY_VERIFICATION settings dictionary.
