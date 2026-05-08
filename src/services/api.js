/**
 * API Service for Stock Analysis
 * Results are cached in localStorage per symbol per day.
 * Stale at midnight so data stays current with market moves.
 *
 * SECURITY:
 *  - validateSymbol() enforces a client-side regex whitelist before the
 *    request is sent. This is a UX guard — the server enforces the same
 *    rule independently. Never rely on client-side validation alone.
 *  - Symbol is URL-encoded via encodeURIComponent() before interpolation
 *    into the fetch URL, preventing any parameter-injection attempt even
 *    if the regex were somehow bypassed (defence-in-depth).
 *  - No API keys or secrets are present in this file; Yahoo Finance is a
 *    public endpoint that requires no auth tokens.
 *  - localStorage caches only public stock data — no PII, no credentials.
 *    Cached entries are keyed by symbol + date so stale data auto-expires.
 */

import { setTokenGetter, getAuthHeaders } from './auth';

const API_BASE = '/api';

// Re-export setTokenGetter for backwards compatibility with App.jsx
export { setTokenGetter };

// ── Client-side input validation ───────────────────────────────────────────
// Mirrors the server-side regex in api/utils/security.py.
// Must match: 1-10 uppercase letters, optional single dot + 1-2 letters (e.g. BRK.B).
// This is a UX guard only — the backend validates independently.
const SYMBOL_RE = /^[A-Z]{1,10}(\.[A-Z]{1,2})?$/;

/**
 * Validate a stock symbol client-side.
 * Returns the normalised (trimmed + uppercased) symbol, or throws on invalid input.
 * @param {string} raw - Raw user input
 * @returns {string} Normalised symbol
 */
function validateSymbol(raw) {
    if (typeof raw !== 'string') throw new Error('Symbol must be a string.');
    const sym = raw.trim().toUpperCase();
    if (!sym) throw new Error('Please enter a stock symbol.');
    if (sym.length > 20) throw new Error('Symbol is too long.');
    if (!SYMBOL_RE.test(sym)) {
        throw new Error('Invalid symbol. Use 1–10 letters (e.g. AAPL, BRK.B).');
    }
    return sym;
}

// Bump this when a deployment changes the data shape or fixes bad cached data.
// Any localStorage entry from an older version is automatically discarded.
const CACHE_VERSION = 3;

// ── Cache helpers ──────────────────────────────────────────────
function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function analysisCacheKey(symbol) {
    return `analyze_v${CACHE_VERSION}_${symbol.toUpperCase()}_${todayStr()}`;
}

const MAX_CACHED_SYMBOLS = 20;

/** Wipe analyze cache entries with wrong version or a stale date. */
function clearStaleCacheEntries() {
    try {
        const currentPrefix = `analyze_v${CACHE_VERSION}_`;
        const today = todayStr();
        Object.keys(localStorage)
            .filter(k => {
                if (!k.startsWith('analyze_')) return false;
                if (!k.startsWith(currentPrefix)) return true;  // wrong version
                return !k.endsWith(`_${today}`);                // right version, old date
            })
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
        const currentPrefix = `analyze_v${CACHE_VERSION}_`;
        const existing = Object.keys(localStorage).filter(k => k.startsWith(currentPrefix));
        // Evict oldest keys (lexicographic sort puts older dates first) when over cap
        if (existing.length >= MAX_CACHED_SYMBOLS) {
            existing.sort().slice(0, existing.length - MAX_CACHED_SYMBOLS + 1)
                .forEach(k => localStorage.removeItem(k));
        }
        localStorage.setItem(analysisCacheKey(symbol), JSON.stringify(data));
    } catch (_) { /* ignore quota errors */ }
}

// ── Public API ─────────────────────────────────────────────────
export async function analyzeStock(symbol, { forceRefresh = false } = {}) {
    // Validate and normalise before any cache lookup or network request.
    // validateSymbol() throws a user-friendly Error if input is invalid.
    const key = validateSymbol(symbol);

    // Return cached result if available and not force-refreshing
    if (!forceRefresh) {
        const cached = readAnalysisCache(key);
        if (cached) return cached;
    }

    try {
        const headers = await getAuthHeaders();

        const response = await fetch(`${API_BASE}/analyze?symbol=${encodeURIComponent(key)}`, { headers });

        // Check if response is HTML (error from Vite - API not running)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error(`Backend API is not running. Please start the Python server and try again.`);
        }

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Session expired. Please sign in again.');
            }
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
