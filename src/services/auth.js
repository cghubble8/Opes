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
  const token = _getToken ? await _getToken() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
