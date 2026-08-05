/**
 * useProfilePicture — reads/writes the profile picture from localStorage.
 *
 * The picture is stored as a base64 data URL under user-scoped keys:
 * 'thesys.avatar.<userId>' or 'thesys.avatar.<email>'
 *
 * Returns the current data URL (or null) and a setter that both writes to
 * localStorage and triggers a re-render.
 *
 * All components (AppNavbar, ProfilePage, SettingsPage) import this hook so
 * they always show the same value and re-render synchronously when it changes.
 *
 * TODO: For production, profile photos should be persisted in the backend per user.
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './useAuth';
import { getUserData, setUserData, removeUserData } from '../utils/userStorage';

// Global storage event so different hook instances on the same page
// re-render when another instance writes a new value.
const AVATAR_EVENT = 'thesys:avatar-changed';

export function useProfilePicture() {
  const { user } = useAuth();
  const [dataUrl, setDataUrl] = useState(() => getUserData('avatar', user, null));

  // Re-read from localStorage when user changes (e.g., after login)
  useEffect(() => {
    setDataUrl(getUserData('avatar', user, null));
  }, [user]);

  // Listen for changes from other hook instances (e.g. Settings saving
  // while AppNavbar is mounted on the same page)
  useEffect(() => {
    function onAvatarChanged() {
      setDataUrl(getUserData('avatar', user, null));
    }
    window.addEventListener(AVATAR_EVENT, onAvatarChanged);
    return () => window.removeEventListener(AVATAR_EVENT, onAvatarChanged);
  }, [user]);

  const save = useCallback((newDataUrl) => {
    if (newDataUrl) {
      setUserData('avatar', user, newDataUrl);
    } else {
      removeUserData('avatar', user);
    }
    setDataUrl(newDataUrl);
    // Notify all other hook instances on this page
    window.dispatchEvent(new Event(AVATAR_EVENT));
  }, [user]);

  const clear = useCallback(() => save(null), [save]);

  return { dataUrl, save, clear };
}
