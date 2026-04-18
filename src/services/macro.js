/**
 * Macro/Market Service - Fetches broad market and sector ETF data from /api/macro
 *
 * Uses the same daily localStorage cache pattern as topStocks.js.
 * Both MarketBanner and MacroDashboard call getMacroData() — the first
 * call fetches from the network, subsequent calls within the same day
 * resolve from cache instantly.
 */

import { setTokenGetter, getAuthHeaders } from './auth';

// Re-export so App.jsx can wire in the Clerk token getter with a named alias
export { setTokenGetter };

const CACHE_KEY     = 'macro_cache';
const CACHE_VERSION = 1;

function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function readCache() {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const { version, date, data } = JSON.parse(raw);
        if (version === CACHE_VERSION && date === todayKey() && data) return data;
    } catch (_) { /* ignore parse errors */ }
    return null;
}

function writeCache(data) {
    try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ version: CACHE_VERSION, date: todayKey(), data }));
    } catch (_) { /* ignore quota errors */ }
}

export async function getMacroData({ forceRefresh = false } = {}) {
    if (!forceRefresh) {
        const cached = readCache();
        if (cached) return cached;
    }

    const headers = await getAuthHeaders();
    const response = await fetch('/api/macro', { headers });

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
        throw new Error('Market data API not available.');
    }

    const data = await response.json();

    if (!response.ok) {
        if (response.status === 401) throw new Error('Session expired. Please sign in again.');
        throw new Error(data.error || 'Failed to fetch market data.');
    }

    writeCache(data);
    return data;
}
