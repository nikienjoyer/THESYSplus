/**
 * Shared axios client for the THESYS+ Auth_UI.
 *
 * Configured with:
 * - baseURL from VITE_API_BASE_URL env var
 * - withCredentials: true (so the refresh-token HttpOnly cookie is sent)
 * - Content-Type: application/json
 *
 * Implements:
 * - Request interceptor: attaches Authorization header with access token
 * - Response interceptor: handles 401 ACCESS_TOKEN_EXPIRED with single-flight refresh
 * - Dispatches axios:request:success event on 2xx responses for idle timeout tracking
 *
 * Requirements: 2.2, 9.2, 9.6.
 */

import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Singleton refresh promise to ensure only one refresh happens at a time
let refreshing = null;

// Function to get the current access token from AuthContext
// This will be set by AuthContext after it mounts
let getAccessToken = () => null;
let onRefreshSuccess = () => {};
let onRefreshFailure = () => {};

/**
 * Configure the client with AuthContext callbacks
 * Called by AuthContext on mount
 */
export function configureAuthCallbacks(callbacks) {
  getAccessToken = callbacks.getAccessToken;
  onRefreshSuccess = callbacks.onRefreshSuccess;
  onRefreshFailure = callbacks.onRefreshFailure;
}

// ---------------------------------------------------------------------------
// Request interceptor - attach Authorization header
// ---------------------------------------------------------------------------
client.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// Response interceptor - handle 401 with single-flight refresh
// ---------------------------------------------------------------------------
client.interceptors.response.use(
  (response) => {
    // Dispatch custom event for idle timeout tracking (Wave A13)
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('axios:request:success'));
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Check if this is a 401 with ACCESS_TOKEN_EXPIRED
    // Backend returns errors in format: {"error": {"code": "...", "message": "..."}}
    if (
      error.response?.status === 401 &&
      error.response?.data?.error?.code === 'ACCESS_TOKEN_EXPIRED' &&
      !originalRequest._retry
    ) {
      // Mark this request as retried to prevent infinite loops
      originalRequest._retry = true;

      try {
        // Single-flight refresh: if already refreshing, wait for that promise
        if (!refreshing) {
          refreshing = client.post('/auth/refresh/');
        }

        const response = await refreshing;
        const newToken = response.data.access_token;

        // Notify AuthContext of the new token
        onRefreshSuccess(newToken);

        // Update the original request with the new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`;

        // Retry the original request
        return client(originalRequest);
      } catch (refreshError) {
        // Refresh failed - check for REFRESH_TOKEN_* error codes
        const errorCode = refreshError.response?.data?.error?.code;
        if (errorCode && errorCode.startsWith('REFRESH_TOKEN_')) {
          // Clear auth state and redirect to sign-in
          onRefreshFailure();
          
          // Redirect to sign-in with session_expired reason
          if (typeof window !== 'undefined') {
            window.location.href = '/sign-in?reason=session_expired';
          }
        }

        return Promise.reject(refreshError);
      } finally {
        // Clear the refreshing promise
        refreshing = null;
      }
    }

    return Promise.reject(error);
  },
);

export default client;
