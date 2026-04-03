/**
 * API Service for Stock Analysis
 * Results are cached in localStorage per symbol per day.
 * Stale at midnight so data stays current with market moves.
 */

const API_BASE = '/api';

// Bump this when a deployment changes the data shape or fixes bad cached data.
// Any localStorage entry from an older version is automatically discarded.
const CACHE_VERSION = 2;

// ── Cache helpers ──────────────────────────────────────────────
function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function analysisCacheKey(symbol) {
    return `analyze_v${CACHE_VERSION}_${symbol.toUpperCase()}_${todayStr()}`;
}

/** Wipe any analyze cache entries that don't have the current version prefix. */
function clearStaleCacheEntries() {
    try {
        const currentPrefix = `analyze_v${CACHE_VERSION}_`;
        Object.keys(localStorage)
            .filter(k => k.startsWith('analyze_') && !k.startsWith(currentPrefix))
            .forEach(k => localStorage.removeItem(k));
    } catch (_) { /* ignore */ }
}

function readAnalysisCache(symbol) {
    try {
        clearStaleCacheEntries();
        const raw = localStorage.getItem(analysisCacheKey(symbol));
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (_) { return null; }
}

function writeAnalysisCache(symbol, data) {
    try {
        localStorage.setItem(analysisCacheKey(symbol), JSON.stringify(data));
    } catch (_) { /* ignore quota errors */ }
}

// ── Public API ─────────────────────────────────────────────────
export async function analyzeStock(symbol, { forceRefresh = false } = {}) {
    const key = symbol.trim().toUpperCase();

    // Return cached result if available and not force-refreshing
    if (!forceRefresh) {
        const cached = readAnalysisCache(key);
        if (cached) return cached;
    }

    try {
        const response = await fetch(`${API_BASE}/analyze?symbol=${encodeURIComponent(key)}`);

        // Check if response is HTML (error from Vite - API not running)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error(`Backend API is not running. Please start the Python server and try again.`);
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze stock');
        }

        // Cache the fresh result
        writeAnalysisCache(key, data);
        return data;
    } catch (error) {
        // Try stale cache (same version, any day) before surfacing the error
        try {
            const keys = Object.keys(localStorage).filter(k => k.startsWith(`analyze_v${CACHE_VERSION}_${key}_`));
            if (keys.length > 0) {
                const stale = JSON.parse(localStorage.getItem(keys[0]));
                if (stale) return stale;
            }
        } catch (_) { /* ignore */ }
        throw error;
    }
}
