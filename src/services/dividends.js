/**
 * Dividend Service — API calls for dividend profile and top dividend screener.
 * Results are cached in localStorage per symbol per day (same pattern as api.js).
 */

import { setTokenGetter, getAuthHeaders } from './auth';

const API_BASE = '/api';

export { setTokenGetter };

const CACHE_VERSION = 1;

function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function profileCacheKey(symbol) {
    return `div_profile_v${CACHE_VERSION}_${symbol.toUpperCase()}_${todayStr()}`;
}

const TOP_DIV_CACHE_KEY = `div_top_v${CACHE_VERSION}`;

function clearStaleProfileEntries() {
    try {
        const prefix  = `div_profile_v${CACHE_VERSION}_`;
        const today   = todayStr();
        Object.keys(localStorage)
            .filter(k => k.startsWith('div_profile_') && (!k.startsWith(prefix) || !k.endsWith(`_${today}`)))
            .forEach(k => localStorage.removeItem(k));
    } catch (_) { /* ignore */ }
}

function readProfileCache(symbol) {
    try {
        clearStaleProfileEntries();
        const raw = localStorage.getItem(profileCacheKey(symbol));
        return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
}

function writeProfileCache(symbol, data) {
    try {
        localStorage.setItem(profileCacheKey(symbol), JSON.stringify(data));
    } catch (_) { /* ignore quota errors */ }
}

function readTopDivCache() {
    try {
        const raw = localStorage.getItem(TOP_DIV_CACHE_KEY);
        if (!raw) return null;
        const { date, stocks } = JSON.parse(raw);
        return date === todayStr() && Array.isArray(stocks) ? stocks : null;
    } catch (_) { return null; }
}

function writeTopDivCache(stocks) {
    try {
        localStorage.setItem(TOP_DIV_CACHE_KEY, JSON.stringify({ date: todayStr(), stocks }));
    } catch (_) { /* ignore quota errors */ }
}

export async function getDividendProfile(symbol, { forceRefresh = false } = {}) {
    const key = symbol.trim().toUpperCase();

    if (!forceRefresh) {
        const cached = readProfileCache(key);
        if (cached) return cached;
    }

    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE}/dividends?symbol=${encodeURIComponent(key)}`, { headers });

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
        throw new Error('Backend API is not running. Please start the Python server.');
    }

    const data = await response.json();

    if (!response.ok) {
        if (response.status === 401) throw new Error('Session expired. Please sign in again.');
        throw new Error(data.error || 'Failed to fetch dividend data');
    }

    writeProfileCache(key, data);
    return data;
}

export async function getTopDividends({ forceRefresh = false } = {}) {
    if (!forceRefresh) {
        const cached = readTopDivCache();
        if (cached) return cached;
    }

    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE}/topdividends`, { headers });

    const contentType = response.headers.get('content-type');
    if (!contentType?.includes('application/json')) {
        throw new Error('Backend API is not running. Please start the Python server.');
    }

    const data = await response.json();

    if (!response.ok) {
        if (response.status === 401) throw new Error('Session expired. Please sign in again.');
        throw new Error(data.error || 'Failed to fetch top dividend stocks');
    }

    const stocks = data.stocks || [];
    writeTopDivCache(stocks);
    return stocks;
}
