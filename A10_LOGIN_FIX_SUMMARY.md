# Wave A10 — Login Issue Resolution

## Issue Reported
- Frontend displays: "An error occurred. Please try again."
- Browser Network tab showed HTTP 500 (reported by user)
- Backend /api/v1/health returns OK
- Issue with valid admin credentials

## Root Cause Identified
The frontend was checking for error codes at the **wrong path** in the response object.

### Backend Error Response Format
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect."
  }
}
```

### Frontend Bug
**Incorrect path**: `error?.response?.data?.code`  
**Correct path**: `error?.response?.data?.error?.code`

This caused the error mapping function to fail, resulting in generic error messages.

## Fixes Applied

### 1. SignInPage.jsx - Error Mapping Function
**File**: `frontend/src/pages/SignInPage.jsx`

**Before**:
```javascript
const errorCode = error?.response?.data?.code;
const errorMessage = error?.response?.data?.message;
```

**After**:
```javascript
const errorCode = error?.response?.data?.error?.code;
const errorMessage = error?.response?.data?.error?.message;
```

### 2. API Client - Response Interceptor
**File**: `frontend/src/api/client.js`

The axios interceptor was already checking the correct path:
```javascript
error.response?.data?.error?.code === 'ACCESS_TOKEN_EXPIRED'
```

## Verification Tests

### Backend Test (✅ PASSING)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"email":"admin@pampangastateu.edu.ph","password":"Admin123!"}'
```

**Result**: HTTP 200 OK with access token and refresh cookie

### Test Credentials
- **Email**: `admin@pampangastateu.edu.ph`
- **Password**: `Admin123!`

## Current Status

### ✅ Backend
- Django server running on http://127.0.0.1:8000
- Login endpoint working correctly
- Returns proper error response format
- CORS configured correctly
- Rate limiting active
- Audit logging working

### ✅ Frontend
- Vite dev server running on http://localhost:5173
- Error response parsing fixed
- UI improvements complete (logo + password toggle)
- Build successful (602ms)

## Testing Instructions

### 1. Clear Browser Cache
- Open DevTools (F12)
- Right-click refresh button → "Empty Cache and Hard Reload"
- Or use Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)

### 2. Test Login Flow
1. Navigate to http://localhost:5173/sign-in
2. Enter email: `admin@pampangastateu.edu.ph`
3. Enter password: `Admin123!`
4. Click "Sign In"

### Expected Behavior
- ✅ Login succeeds
- ✅ Redirects to home page (/)
- ✅ Access token stored in memory
- ✅ Refresh cookie set (HttpOnly)
- ✅ User profile loaded

### 3. Test Error Handling
1. Try invalid password
2. Should display: "Email or password is incorrect"
3. Try non-institutional email
4. Should display: "Please use your institutional email address."

### 4. Check Network Tab
- POST http://localhost:8000/api/v1/auth/login/
- Status: 200 OK (for valid credentials)
- Status: 401 Unauthorized (for invalid credentials)
- Response includes `access_token`, `user` object
- Set-Cookie header includes `refresh_token`

## Troubleshooting

### If Still Seeing HTTP 500
1. **Check browser console** for actual error
2. **Clear browser cache** completely
3. **Restart Vite dev server**:
   ```bash
   cd frontend
   npm run dev
   ```
4. **Check Django logs** in terminal for traceback
5. **Verify database** has admin user:
   ```bash
   cd backend
   .venv\Scripts\python.exe manage.py shell -c "from accounts.models import User; print(User.objects.filter(email='admin@pampangastateu.edu.ph').exists())"
   ```

### If Login Returns 401
- Verify password is correct: `Admin123!`
- Check email is exact: `admin@pampangastateu.edu.ph`
- Ensure user is active in database

### If CORS Error
- Verify Origin header: `http://localhost:5173`
- Check CORS_ALLOWED_ORIGINS in backend/.env
- Restart Django server

## Files Modified

### Frontend
1. `frontend/src/pages/SignInPage.jsx` - Fixed error response parsing
2. `frontend/src/components/auth/SignInCard.jsx` - Added password toggle
3. `frontend/src/components/ui/Logo.jsx` - New logo component
4. `frontend/src/components/ui/Icon.jsx` - New icon components
5. `frontend/src/components/ui/index.js` - Added exports

### Backend
- No backend changes required
- All auth logic working correctly

## Next Steps
1. Test login from browser at http://localhost:5173/sign-in
2. Verify successful authentication
3. Confirm error messages display correctly
4. Mark Wave A10 as complete once verified
