/**
 * AuthContext — Real authentication state management.
 *
 * Provides authentication state and methods for sign-in, sign-out, refresh, and loadMe.
 * Access token is held in memory only (never persisted to localStorage/sessionStorage).
 * Refresh token is managed via HttpOnly cookie.
 *
 * Requirements: 9.2, 18.1, 25.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import client, { configureAuthCallbacks } from '../api/client';

const AuthContext = createContext(undefined);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const isAuthenticated = !!accessToken && !!user;

  /**
   * Load user profile from GET /auth/me/
   * @param {string} token - Optional access token to use (bypasses state for immediate use)
   */
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

  /**
   * Configure axios client callbacks on mount
   */
  useEffect(() => {
    configureAuthCallbacks({
      getAccessToken: () => accessToken,
      onRefreshSuccess: (newToken) => {
        setAccessToken(newToken);
      },
      onRefreshFailure: () => {
        setAccessToken(null);
        setUser(null);
      },
    });
  }, [accessToken]);

  /**
   * Attempt silent refresh on mount
   */
  useEffect(() => {
    const attemptSilentRefresh = async () => {
      try {
        const response = await client.post('/auth/refresh/');
        const token = response.data.access_token;
        setAccessToken(token);
        // Pass token directly to loadMe to avoid race condition with React state
        await loadMe(token);
      } catch (error) {
        // Any failure during silent refresh = unauthenticated.
        // Covers: 4xx (invalid/expired cookie), 5xx (server error),
        // and network errors (backend unreachable, CORS, DNS).
        // Previously only cleared state on 4xx, leaving accessToken=null
        // and user=null in a partially-unauthenticated limbo on network
        // failures — which caused false "session expired" redirects.
        setAccessToken(null);
        setUser(null);
      } finally {
        setIsInitializing(false);
      }
    };

    attemptSilentRefresh();
  }, [loadMe]);

  /**
   * Sign in with email, password, and optional rememberMe
   */
  const signIn = useCallback(async (email, password, rememberMe = false) => {
    try {
      const response = await client.post('/auth/login/', {
        email,
        password,
        remember_me: rememberMe,
      });
      const token = response.data.access_token;
      setAccessToken(token);
      // Pass token directly to loadMe to avoid race condition with React state
      await loadMe(token);
      return response.data;
    } catch (error) {
      setAccessToken(null);
      setUser(null);
      throw error;
    }
  }, [loadMe]);

  /**
   * Sign out - calls POST /auth/logout/ and clears state
   */
  const signOut = useCallback(async () => {
    try {
      await client.post('/auth/logout/');
    } catch (error) {
      // Log but don't throw - we want to clear state regardless
      console.error('Logout request failed:', error);
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  /**
   * Manually refresh the access token
   */
  const refresh = useCallback(async () => {
    try {
      const response = await client.post('/auth/refresh/');
      const token = response.data.access_token;
      setAccessToken(token);
      return token;
    } catch (error) {
      setAccessToken(null);
      setUser(null);
      throw error;
    }
  }, []);

  const value = {
    user,
    accessToken,
    isAuthenticated,
    isInitializing,
    signIn,
    signOut,
    refresh,
    loadMe,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}
