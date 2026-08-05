# Browser Testing Quick Reference Guide

## Starting the Server

```bash
cd backend
.\.venv\Scripts\Activate.ps1  # Windows
python manage.py runserver
```

Server will be available at: `http://localhost:8000`

---

## API Endpoint

**URL**: `POST http://localhost:8000/api/v1/auth/request-access/`

**Headers**:
```
Content-Type: multipart/form-data
Origin: http://localhost:5173
```

---

## Test with cURL

### Document Upload (New Flow)
```bash
curl -X POST http://localhost:8000/api/v1/auth/request-access/ \
  -H "Origin: http://localhost:5173" \
  -F "email=test@pampangastateu.edu.ph" \
  -F "first_name=Juan" \
  -F "last_name=Dela Cruz" \
  -F "requested_role=student" \
  -F "document=@path/to/student_id.png"
```

### Legacy Justification (Old Flow)
```bash
curl -X POST http://localhost:8000/api/v1/auth/request-access/ \
  -H "Origin: http://localhost:5173" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@pampangastateu.edu.ph",
    "first_name": "Juan",
    "last_name": "Dela Cruz",
    "requested_role": "student",
    "justification": "I am a student at PSU CCS studying BSIS."
  }'
```

---

## Response Interpretation

### Status Codes
- **202 Accepted**: Document uploaded and processed
- **201 Created**: Legacy justification flow (no document)
- **400 Bad Request**: Validation error
- **409 Conflict**: Email already exists or duplicate request
- **429 Too Many Requests**: Rate limit exceeded

### Decision Values
- **`auto_approved`**: ✅ Automatically approved (account created)
- **`pending_manual_review`**: ⏳ Needs admin review
- **`rejected`**: ❌ Automatically rejected
- **`error`**: ⚠️ Processing error
- **`processing`**: 🔄 Still processing (shouldn't happen in sync flow)

### AccessRequest Status Values
- **`approved`**: Account created, activation email sent
- **`pending`**: Waiting for admin review
- **`denied`**: Request rejected
- **`processing`**: Currently being processed

---

## Quick Test Checklist

### ✅ Valid Document Test
- [ ] Upload clear PSU CCS student ID
- [ ] Verify response: `status: "approved"`, `decision: "auto_approved"`
- [ ] Check email for activation link
- [ ] Verify extracted fields are correct

### ✅ Blurry Document Test
- [ ] Upload low-quality/blurry document
- [ ] Verify response: `status: "pending"`, `decision: "pending_manual_review"`
- [ ] Check `decision_reason` mentions low confidence
- [ ] Verify `ocr_confidence` < 0.75

### ✅ Wrong Institution Test
- [ ] Upload document from different university
- [ ] Verify response: `status: "denied"`, `decision: "rejected"`
- [ ] Check `flagged_reasons` includes "wrong_institution"
- [ ] Verify `rule_failures` shows institution mismatch

### ✅ Legacy Flow Test
- [ ] Submit with justification (no document)
- [ ] Verify response: `status: "pending"`
- [ ] Verify no `verification` field in response
- [ ] Check admin panel for pending request

### ✅ File Validation Tests
- [ ] Upload .txt file → expect 400 error
- [ ] Upload 11MB file → expect 400 error
- [ ] Upload .PNG file (uppercase) → expect success
- [ ] Upload PDF → expect success

---

## Debugging Tips

### Check Response in Browser DevTools
1. Open DevTools (F12)
2. Go to Network tab
3. Submit form
4. Click on `request-access` request
5. View Response tab

### Common Issues

**429 Rate Limit Error**:
- Wait 1 hour (IP limit: 5 requests/hour)
- Or wait 24 hours (email limit: 3 requests/day)
- Or clear cache: `python manage.py shell` → `from django.core.cache import cache; cache.clear()`

**415 Unsupported Media Type**:
- Ensure `Content-Type: multipart/form-data` header
- Check file is actually attached

**400 Validation Error**:
- Check email domain is `@pampangastateu.edu.ph`
- Check role is `student` or `faculty`
- Check either document OR justification (not both)

**409 Duplicate Request**:
- Email already has pending request
- Or email already registered
- Use different email for testing

---

## Viewing Results

### Admin Panel
1. Navigate to: `http://localhost:8000/admin/`
2. Login with admin credentials
3. Go to "Access Requests"
4. Filter by status: pending/approved/denied

### Database Query
```bash
python manage.py shell
```

```python
from access_requests.models import AccessRequest
from identity_verification.models import VerificationResult

# View all requests
for req in AccessRequest.objects.all():
    print(f"{req.email}: {req.status}")

# View verification results
for result in VerificationResult.objects.all():
    print(f"{result.access_request.email}: {result.status}")
    print(f"  Confidence: {result.ocr_confidence}")
    print(f"  Fields: {result.extracted_fields}")
    print(f"  Reason: {result.decision_reason}")
```

---

## Sample Test Documents

### Valid PSU CCS Document Should Contain:
- ✅ "Pampanga State University" or "PSU"
- ✅ "College of Computing Studies" or "CCS"
- ✅ One of: "BS Information Systems", "BS Information Technology", "BS Computer Science", "Associate in Computer Technology"
- ✅ Student name
- ✅ Student number (optional but helpful)

### Test Document Variations:
1. **Perfect quality**: Clear, well-lit, high resolution
2. **Low quality**: Blurry, dark, low resolution
3. **Partial**: Some text cut off or obscured
4. **Wrong institution**: UP, HAU, etc.
5. **Wrong college**: Engineering, Education, etc.
6. **Wrong program**: Biology, Nursing, etc.

---

## Expected Behavior Summary

| Document Type | OCR Confidence | Institution | College | Program | Result |
|--------------|----------------|-------------|---------|---------|--------|
| Clear PSU CCS | ≥ 75% | PSU | CCS | Allowed | AUTO_APPROVED |
| Blurry PSU CCS | < 75% | PSU | CCS | Allowed | PENDING_MANUAL_REVIEW |
| Clear PSU CCS | ≥ 75% | PSU | CCS | Typo | PENDING_MANUAL_REVIEW |
| Clear PSU CCS | ≥ 75% | PSU | CCS | Missing | PENDING_MANUAL_REVIEW |
| Clear UP | ≥ 75% | UP | Any | Any | REJECTED |
| Clear PSU Eng | ≥ 75% | PSU | Engineering | Any | REJECTED |
| Clear PSU CCS | ≥ 75% | PSU | CCS | Biology | REJECTED |
| Any | Any | Any | Any | Any + Email Exists | PENDING_MANUAL_REVIEW |

---

## Contact

For issues or questions during testing, check:
1. Server logs: Terminal where `runserver` is running
2. Test results: `python manage.py test access_requests.tests -v 2`
3. Audit logs: Database `audit_log` table
4. This guide: `BROWSER_TESTING_GUIDE.md`
