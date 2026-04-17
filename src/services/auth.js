/**
 * Shared authentication utilities for API services.
 * Centralizes token injection for Clerk JWT auth across all API calls.
 */

let _getToken = null;

/**
 * Set the token getter function (usually from useAuth() hook).
 * Called once by App.jsx to wire up Clerk token access in services.
 */
export function setTokenGetter(fn) {
  _getToken = fn;
}

/**
 * Get headers for an authenticated API request.
 * Returns { Authorization: 'Bearer <token>' } if available, or {} if not signed in.
 */
export async function getAuthHeaders() {
  if (!_getToken) {
    console.warn('[AUTH] Token getter not wired up — setTokenGetter() was never called');
    return {};
  }
  try {
    const token = await _getToken();
    if (!token) {
      console.warn('[AUTH] getToken() returned null — Clerk session may not be ready');
    }
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch (err) {
    console.error('[AUTH] getToken() threw:', err);
    return {};
  }
}
