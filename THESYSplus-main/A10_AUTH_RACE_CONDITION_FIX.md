# Wave A10 — Auth Race Condition Fix

## Issue Identified
After successful login, the `/auth/me/` request was failing with 401 Unauthorized.

### Sequence of Events
1. `POST /auth/login/` → **200 OK** ✅ (returns access token)
2. `setAccessToken(token)` called (React state update - **asynchronous**)
3. `loadMe()` called immediately
4. `GET /auth/me/` → **401 Unauthorized** ❌ (no Authorization header)

### Root Cause
**React state timing issue**: `setAccessToken()` is asynchronous, but `loadMe()` was called immediately after. The axios request interceptor tried to read the access token from state, but it wasn't available yet.

```javascript
// BEFORE (broken):
const token = response.data.access_token;
setAccessToken(token);        // Async - doesn't update immediately
await loadMe();               // Runs before state updates
// → axios interceptor reads null token → no Authorization header
```

## Solution
Pass the token **directly** to `loadMe()` instead of relying on React state.

### Changes Applied

#### 1. Updated `loadMe()` Function
**File**: `frontend/src/context/AuthContext.jsx`

```javascript
// AFTER (fixed):
const loadMe = useCallback(async (token = null) => {
  try {
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await client.get('/auth/me/', { headers });
    setUser(response.data);
    return response.data;
  } catch (error) {
    console.error('Failed to load user profile:', error);
    setUser(null);
    setAccessToken(null);
    throw error;
  }
}, []);
```

**Key changes**:
- Added optional `token` parameter
- If token provided, directly set `Authorization` header
- Bypasses axios interceptor for immediate use
- Falls back to interceptor if no token provided (for subsequent calls)

#### 2. Updated `signIn()` Function
```javascript
// AFTER (fixed):
const signIn = useCallback(async (email, password, rememberMe = false) => {
  try {
    const response = await client.post('/auth/login/', {
      email,
      password,
      remember_me: rememberMe,
    });
    const token = response.data.access_token;
    setAccessToken(token);
    // Pass token directly to loadMe to avoid race condition
    await loadMe(token);  // ← Token passed directly
    return response.data;
  } catch (error) {
    setAccessToken(null);
    setUser(null);
    throw error;
  }
}, [loadMe]);
```

#### 3. Updated Silent Refresh
```javascript
// AFTER (fixed):
const attemptSilentRefresh = async () => {
  try {
    const response = await client.post('/auth/refresh/');
    const token = response.data.access_token;
    setAccessToken(token);
    // Pass token directly to loadMe to avoid race condition
    await loadMe(token);  // ← Token passed directly
  } catch (error) {
    // ...
  }
};
```

## Why This Works

### Before (Race Condition)
```
1. setAccessToken(token)     → State update queued
2. loadMe()                  → Runs immediately
3. axios interceptor         → Reads state (still null)
4. GET /auth/me/             → No Authorization header
5. State update completes    → Too late!
```

### After (Direct Token Pass)
```
1. setAccessToken(token)     → State update queued (for future requests)
2. loadMe(token)             → Token passed as parameter
3. Direct header set         → Authorization: Bearer <token>
4. GET /auth/me/             → With Authorization header ✅
5. State update completes    → Ready for subsequent requests
```

## Benefits

### 1. Eliminates Race Condition
- Token available immediately for `/auth/me/` request
- No dependency on React state timing
- Reliable authentication flow

### 2. Maintains Backward Compatibility
- `loadMe()` can still be called without token parameter
- Falls back to axios interceptor (uses state)
- Works for both immediate and subsequent calls

### 3. Consistent Pattern
- Same fix applied to both `signIn()` and silent refresh
- Predictable behavior across auth flows

## Verification

### ✅ Expected Flow
1. User enters credentials
2. `POST /auth/login/` → 200 OK (access token received)
3. `setAccessToken(token)` → State update queued
4. `loadMe(token)` → Token passed directly
5. `GET /auth/me/` → 200 OK (with Authorization header) ✅
6. User profile loaded
7. Redirect to home page

### ✅ Network Tab Should Show
```
POST /api/v1/auth/login/
  Status: 200 OK
  Response: { access_token: "...", user: {...} }

GET /api/v1/auth/me/
  Status: 200 OK
  Request Headers: Authorization: Bearer eyJ...
  Response: { id: "...", email: "...", role: "..." }
```

## Files Modified

### Frontend
1. `frontend/src/context/AuthContext.jsx`
   - Updated `loadMe()` to accept optional token parameter
   - Updated `signIn()` to pass token directly to `loadMe()`
   - Updated silent refresh to pass token directly to `loadMe()`

### Backend
- **No changes required** ✅

## Build Status
✅ Frontend build successful: **601ms**

## Test Credentials
- **Email**: `admin@pampangastateu.edu.ph`
- **Password**: `Admin123!`

## Testing Instructions

### 1. Clear Browser Cache
- Hard reload: Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)

### 2. Open DevTools
- Press F12
- Go to Network tab
- Filter: XHR or Fetch

### 3. Test Sign In
1. Navigate to **http://localhost:5173/sign-in**
2. Enter test credentials
3. Click "Sign In"

### 4. Verify Network Requests
Should see in order:
1. `POST /api/v1/auth/login/` → **200 OK**
2. `GET /api/v1/auth/me/` → **200 OK** (with Authorization header)

### 5. Expected Behavior
- ✅ Login succeeds
- ✅ User profile loads
- ✅ Redirects to home page (/)
- ✅ No 401 errors
- ✅ Access token in memory
- ✅ Refresh cookie set

## Troubleshooting

### If Still Getting 401 on /auth/me/
1. Check Network tab → `/auth/me/` request
2. Verify Request Headers include: `Authorization: Bearer <token>`
3. If missing, check browser console for errors
4. Ensure frontend dev server reloaded (Vite HMR)

### If Login Succeeds But No Redirect
1. Check browser console for navigation errors
2. Verify home route exists in App.jsx
3. Check for JavaScript errors blocking navigation

## Summary

### ✅ Root Cause
React state timing issue - `setAccessToken()` is async, but `loadMe()` was called immediately.

### ✅ Solution
Pass token directly to `loadMe(token)` instead of relying on React state.

### ✅ Result
- `/auth/me/` now receives Authorization header
- Authentication flow works correctly
- Login → Profile load → Redirect to home

### 🧪 Ready for Testing
Test at **http://localhost:5173/sign-in** with credentials above.
Since Vite dev server supports hot module reloading, changes should be live.
