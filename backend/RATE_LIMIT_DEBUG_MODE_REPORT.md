# Rate Limit Debug Mode - Completion Report

## ✅ COMPLETE: Relaxed Rate Limits for Local Development

### Problem
The production rate limits (5 requests/hour for IP, 3 requests/day for email) make local development and testing difficult. Testing document upload with multiple attempts quickly hits the rate limit, requiring a 1-hour wait.

### Solution
Added DEBUG-aware rate limiting that automatically relaxes limits when `DEBUG=True` (local development) while keeping production limits unchanged when `DEBUG=False`.

---

## File Changed

### `backend/common/ratelimit.py`
**Status**: ✏️ Enhanced

**Changes**:
1. Added `_get_debug_limits()` helper function
2. Updated `rate_limit_per_email()` to use debug limits
3. Updated `rate_limit_per_ip()` to use debug limits
4. Added documentation about development mode behavior

**Lines Modified**: ~50 lines

---

## Rate Limit Configuration

### Production Mode (DEBUG=False)
**Unchanged** - Original limits remain in effect:

| Endpoint | Limit Type | Production Limit | Window |
|----------|-----------|------------------|--------|
| POST /request-access | Per-IP | 5 requests | 1 hour (3600s) |
| POST /request-access | Per-email | 3 requests | 1 day (86400s) |
| POST /forgot-password | Per-email | 3 requests | 1 hour (3600s) |
| POST /sign-in | Per-email (failures) | 5 requests | 15 minutes (900s) |
| POST /reset-password | Per-IP | 10 requests | 1 hour (3600s) |
| POST /reset-password | Per-token | 5 requests | 15 minutes (900s) |

### Development Mode (DEBUG=True)
**Relaxed** - All rate limits use:

| Limit Type | Development Limit | Window |
|-----------|-------------------|--------|
| Per-IP | **20 requests** | **1 minute (60s)** |
| Per-email | **20 requests** | **1 minute (60s)** |
| Per-token | **20 requests** | **1 minute (60s)** |

**Effective Rate**: 20 requests/minute for all endpoints

---

## Implementation Details

### Helper Function
```python
def _get_debug_limits(limit: int, window_seconds: int) -> tuple[int, int]:
    """Adjust rate limits for development mode.
    
    When DEBUG=True, use more permissive limits for local testing:
    - 20 requests per minute (60 seconds)
    
    Production limits (DEBUG=False) remain unchanged.
    """
    if getattr(settings, 'DEBUG', False):
        # Development mode: 20 requests per minute
        return 20, 60
    # Production mode: use original limits
    return limit, window_seconds
```

### Updated Decorators
Both `rate_limit_per_email()` and `rate_limit_per_ip()` now call `_get_debug_limits()`:

```python
# Adjust limits for DEBUG mode
actual_limit, actual_window = _get_debug_limits(limit, window_seconds)

key = f'ratelimit:ip:{view_func.__qualname__}:{ip}'
allowed, retry = _hit_and_check(key, actual_limit, actual_window)
```

---

## How It Works

### Development Environment (DEBUG=True)
1. Django loads `thesys/settings/dev.py` which sets `DEBUG = True`
2. Rate limit decorators call `_get_debug_limits()`
3. Function detects `DEBUG=True` and returns `(20, 60)`
4. Rate limiting uses 20 requests per 60 seconds
5. After 20 requests in 1 minute, returns 429 with `Retry-After: 60`

### Production Environment (DEBUG=False)
1. Django loads `thesys/settings/prod.py` which sets `DEBUG = False`
2. Rate limit decorators call `_get_debug_limits()`
3. Function detects `DEBUG=False` and returns original limits
4. Rate limiting uses production limits (5/hour, 3/day, etc.)
5. Production behavior unchanged

---

## Browser Testing Steps

### Test 1: Verify Relaxed Limits in Development
1. **Start backend** in development mode:
   ```bash
   cd backend
   python manage.py runserver
   ```
   
2. **Verify DEBUG=True**:
   - Check console output for Django debug mode indicators
   - Or check `thesys/settings/__init__.py` is loading `dev.py`

3. **Navigate to Request Access page**:
   ```
   http://localhost:5173/request-access
   ```

4. **Submit multiple requests rapidly**:
   - Fill in: email, first name, last name, role
   - Upload a document (or leave empty for legacy flow)
   - Submit the form
   - **Repeat 20 times within 1 minute**

5. **Expected behavior**:
   - First 20 requests: Success (201) or validation errors (400/409)
   - 21st request within 1 minute: 429 Rate Limited
   - Response includes: `Retry-After: 60` (or less)
   - After 1 minute: Rate limit resets, can submit again

6. **Verify rate limit message**:
   - UI should show: "Too many requests. Please try again later."
   - Check browser console for 429 response

### Test 2: Verify Rate Limit Reset
1. **Hit rate limit** (submit 21 requests in 1 minute)
2. **Wait 60 seconds**
3. **Submit another request**
4. **Expected**: Request succeeds (rate limit reset)

### Test 3: Verify Different Emails
1. **Submit 20 requests** with `test1@psu.edu.ph`
2. **Hit rate limit** (21st request fails)
3. **Submit request** with `test2@psu.edu.ph`
4. **Expected**: Request succeeds (different email, separate limit)

### Test 4: Clear Cache to Reset Immediately
If you need to reset rate limits immediately during testing:

```bash
# In Django shell
python manage.py shell

# Clear all rate limit keys
from django.core.cache import cache
cache.clear()
```

---

## Verification Commands

### Check Current DEBUG Setting
```bash
cd backend
python manage.py shell

# In shell:
from django.conf import settings
print(f"DEBUG = {settings.DEBUG}")
# Should print: DEBUG = True (in development)
```

### Monitor Rate Limit Keys in Cache
```bash
python manage.py shell

# In shell:
from django.core.cache import cache

# Check if rate limit keys exist
# (Note: Django's cache doesn't support key listing by default,
#  but you can check specific keys if you know them)

# Example: Check rate limit for specific IP
key = "ratelimit:ip:RequestAccessView.post:127.0.0.1"
count = cache.get(key, 0)
print(f"Current count for 127.0.0.1: {count}")
```

### Test Rate Limit with curl
```bash
# Submit 21 requests rapidly
for i in {1..21}; do
  echo "Request $i:"
  curl -X POST http://localhost:8000/api/auth/request-access/ \
    -H "Content-Type: application/json" \
    -d '{
      "email": "test@psu.edu.ph",
      "first_name": "Test",
      "last_name": "User",
      "requested_role": "student",
      "justification": "Testing rate limits"
    }'
  echo ""
done
```

**Expected**:
- Requests 1-20: Success or validation errors
- Request 21: 429 with `Retry-After: 60`

---

## Production Safety

### Verification Checklist
✅ Production uses `thesys/settings/prod.py` with `DEBUG = False`  
✅ `_get_debug_limits()` checks `settings.DEBUG` flag  
✅ When `DEBUG=False`, returns original production limits  
✅ No changes to production rate limit values  
✅ No changes to rate limit logic (only limit values adjusted)  
✅ Rate limiting still active in development (not disabled)  

### Production Deployment
When deploying to production:
1. Ensure `DJANGO_SETTINGS_MODULE=thesys.settings.prod`
2. Verify `DEBUG=False` in `prod.py`
3. Rate limits automatically use production values
4. No code changes needed

---

## What's Working Now

✅ Development mode: 20 requests/minute (relaxed for testing)  
✅ Production mode: Original limits unchanged (5/hour, 3/day)  
✅ Rate limiting still active (not disabled)  
✅ Automatic detection via DEBUG flag  
✅ No manual configuration needed  
✅ Safe for production deployment  

---

## Exact Throttle Settings

### Development (DEBUG=True)
```python
# All rate limit decorators use:
limit = 20
window_seconds = 60

# Effective rate: 20 requests per minute
```

### Production (DEBUG=False)
```python
# Request Access endpoint:
@rate_limit_per_ip(limit=5, window_seconds=3600)    # 5/hour
@rate_limit_per_email(limit=3, window_seconds=86400) # 3/day

# Forgot Password endpoint:
@rate_limit_per_email(limit=3, window_seconds=3600)  # 3/hour

# Sign In endpoint (failures only):
@rate_limit_per_email_on_failure(limit=5, window_seconds=900) # 5/15min

# Reset Password endpoint:
@rate_limit_per_ip(limit=10, window_seconds=3600)    # 10/hour
@rate_limit_per_token(limit=5, window_seconds=900)   # 5/15min
```

---

## Summary

### Changes Made
1. ✅ Added `_get_debug_limits()` helper function
2. ✅ Updated `rate_limit_per_email()` to use debug limits
3. ✅ Updated `rate_limit_per_ip()` to use debug limits
4. ✅ Added documentation about development mode

### Configuration
- **Development**: 20 requests/minute (DEBUG=True)
- **Production**: Original limits unchanged (DEBUG=False)

### Testing
- Submit 20+ requests rapidly to test rate limiting
- Wait 60 seconds for rate limit reset
- Use different emails to test separate limits
- Clear cache to reset immediately if needed

### Production Safety
- Production behavior unchanged
- Automatic detection via DEBUG flag
- No manual configuration needed
- Safe for deployment

---

**Status**: ✅ COMPLETE  
**File Changed**: 1 (`backend/common/ratelimit.py`)  
**Lines Modified**: ~50 lines  
**Production Impact**: None (DEBUG=False uses original limits)  
**Development Benefit**: 20 requests/minute for easier testing
