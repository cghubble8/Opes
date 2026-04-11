/**
 * Screener Service — fetches filtered stock results from /api/screener.
 * Results are cached for 1 hour per direction to avoid redundant ML runs.
 */

import { setTokenGetter, getAuthHeaders } from './auth';

// Re-export so App.jsx can wire up the Clerk token getter explicitly,
// matching the same pattern used by api.js and topStocks.js.
export { setTokenGetter };

const API_BASE = '/api';
const CACHE_VERSION = 1;

/**
 * Returns an hourly bucket string like "2026-04-11T14".
 * Cache entries keyed by this expire automatically each hour.
 */
function hourlyBucket() {
    return new Date().toISOString().slice(0, 13);
}

function screenerCacheKey(direction) {
    return `screener_v${CACHE_VERSION}_${direction}_${hourlyBucket()}`;
}

/** Read a valid cache entry for this direction and hour. Returns null if missing. */
function readScreenerCache(direction) {
    try {
        const currentKey = screenerCacheKey(direction);
        // Evict stale screener keys from prior hours or prior versions
        Object.keys(localStorage)
            .filter(k => k.startsWith('screener_') && k !== currentKey)
            .forEach(k => localStorage.removeItem(k));

        const raw = localStorage.getItem(currentKey);
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

/** Persist screener results to localStorage. */
function writeScreenerCache(direction, data) {
    try {
        localStorage.setItem(screenerCacheKey(direction), JSON.stringify(data));
    } catch (_) { /* ignore quota errors */ }
}

/**
 * Fetch screener results for the given direction filter.
 * Returns the full API response: { stocks, total, direction }.
 *
 * @param {Object} options
 * @param {'any'|'bullish'|'bearish'} options.direction
 * @param {boolean} options.forceRefresh
 */
export async function getScreenerResults({ direction = 'any', forceRefresh = false } = {}) {
    if (!forceRefresh) {
        const cached = readScreenerCache(direction);
        if (cached) return cached;
    }

    const headers = await getAuthHeaders();
    const response = await fetch(
        `${API_BASE}/screener?direction=${encodeURIComponent(direction)}`,
        { headers }
    );

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
        throw new Error('Backend API is not running. Please start the Python server.');
    }

    const data = await response.json();

    if (!response.ok) {
        if (response.status === 401) {
            throw new Error('Session expired. Please sign in again.');
        }
        throw new Error(data.error || 'Failed to fetch screener results');
    }

    writeScreenerCache(direction, data);
    return data;
}
