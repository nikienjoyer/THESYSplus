/**
 * userStorage.js — User-scoped localStorage utilities
 *
 * Provides helpers to read/write localStorage keys scoped to the authenticated user.
 * This prevents data leakage when multiple users log in on the same browser.
 *
 * Key format: `thesys.<dataType>.<userId>` or `thesys.<dataType>.<email>`
 * Example: `thesys.avatar.123` or `thesys.profile.user@example.com`
 *
 * TODO: For production, profile photo, bio, research interests, and saved theses
 * should be persisted in the backend per user instead of localStorage.
 */

/**
 * Generate a user-scoped localStorage key
 * @param {string} dataType - The type of data (e.g., 'avatar', 'profile', 'savedTheses')
 * @param {object} user - The authenticated user object from AuthContext
 * @returns {string|null} - The scoped key, or null if user is not available
 */
export function getUserKey(dataType, user) {
  if (!user) return null;
  
  // Prefer user.id (more stable), fall back to user.email
  const identifier = user.id || user.email;
  if (!identifier) return null;
  
  return `thesys.${dataType}.${identifier}`;
}

/**
 * Read user-scoped data from localStorage
 * @param {string} dataType - The type of data
 * @param {object} user - The authenticated user object
 * @param {*} defaultValue - Default value if key doesn't exist
 * @returns {*} - The parsed data or defaultValue
 */
export function getUserData(dataType, user, defaultValue = null) {
  const key = getUserKey(dataType, user);
  if (!key) return defaultValue;
  
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return defaultValue;
    
    // Try to parse as JSON, fall back to raw string
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  } catch {
    return defaultValue;
  }
}

/**
 * Write user-scoped data to localStorage
 * @param {string} dataType - The type of data
 * @param {object} user - The authenticated user object
 * @param {*} value - The value to store (will be JSON.stringify'd if not a string)
 * @returns {boolean} - True if successful, false otherwise
 */
export function setUserData(dataType, user, value) {
  const key = getUserKey(dataType, user);
  if (!key) return false;
  
  try {
    if (value === null || value === undefined) {
      localStorage.removeItem(key);
    } else {
      const serialized = typeof value === 'string' ? value : JSON.stringify(value);
      localStorage.setItem(key, serialized);
    }
    return true;
  } catch {
    return false;
  }
}

/**
 * Remove user-scoped data from localStorage
 * @param {string} dataType - The type of data
 * @param {object} user - The authenticated user object
 * @returns {boolean} - True if successful, false otherwise
 */
export function removeUserData(dataType, user) {
  const key = getUserKey(dataType, user);
  if (!key) return false;
  
  try {
    localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
