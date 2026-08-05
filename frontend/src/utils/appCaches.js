/**
 * appCaches — central registry for module-level in-memory caches.
 *
 * Each page that uses a module-level cache registers a clear callback here.
 * AuthContext calls clearAllCaches() on logout so User B never sees User A's
 * cached analytics, trend, or repository data after signing in on the same tab.
 */

const _clearers = [];

/** Register a cache-clearing function (called once per module at load time). */
export function registerCacheClearer(fn) {
  _clearers.push(fn);
}

/** Clear all registered caches — call on logout. */
export function clearAllCaches() {
  _clearers.forEach((fn) => { try { fn(); } catch (_) {} });
}
