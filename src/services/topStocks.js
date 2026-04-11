/**
 * Top Stocks Service - Fetches top buy-rated stocks from API
 */

import { setTokenGetter, getAuthHeaders } from './auth';

const API_BASE = '/api';

// Re-export setTokenGetter for backwards compatibility with App.jsx
export { setTokenGetter };

// Mock data for development fallback
export const topStocksMockData = [
    {
        symbol: "NVDA",
        name: "NVIDIA Corporation",
        sector: "Technology",
        price: 467.85,
        change: 12.45,
        change_percent: "2.73",
        prediction: "Strong Buy Signal",
        confidence: 84.2,
        direction: "bullish",
        reasoning: "Strong momentum with AI/GPU demand surge. Excellent fundamentals.",
    },
    {
        symbol: "META",
        name: "Meta Platforms Inc.",
        sector: "Technology",
        price: 325.42,
        change: 5.67,
        change_percent: "1.77",
        prediction: "Strong Buy Signal",
        confidence: 78.5,
        direction: "bullish",
        reasoning: "Solid revenue growth, AI investments paying off.",
    },
    {
        symbol: "AMZN",
        name: "Amazon.com Inc.",
        sector: "Consumer Cyclical",
        price: 153.89,
        change: 2.34,
        change_percent: "1.54",
        prediction: "Moderate Buy Signal",
        confidence: 71.3,
        direction: "bullish",
        reasoning: "AWS growth strong, e-commerce stabilizing.",
    },
    {
        symbol: "AAPL",
        name: "Apple Inc.",
        sector: "Technology",
        price: 189.50,
        change: 1.85,
        change_percent: "0.99",
        prediction: "Moderate Buy Signal",
        confidence: 67.8,
        direction: "bullish",
        reasoning: "Consistent performance, strong services revenue.",
    },
    {
        symbol: "GOOGL",
        name: "Alphabet Inc.",
        sector: "Technology",
        price: 141.23,
        change: 0.95,
        change_percent: "0.68",
        prediction: "Moderate Buy Signal",
        confidence: 64.2,
        direction: "bullish",
        reasoning: "Cloud growth accelerating, AI integration positive.",
    },
];

const CACHE_KEY = 'topstocks_cache';

/**
 * Returns today's date string (YYYY-MM-DD) in local time.
 * Used as the cache key so results refresh daily.
 */
function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Read a valid cache entry for today. Returns null if stale or missing. */
function readCache() {
    try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return null;
        const { date, stocks } = JSON.parse(raw);
        if (date === todayKey() && Array.isArray(stocks) && stocks.length > 0) return stocks;
    } catch (_) { /* ignore parse errors */ }
    return null;
}

/** Persist results to localStorage with today's date. */
function writeCache(stocks) {
    try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ date: todayKey(), stocks }));
    } catch (_) { /* ignore quota errors */ }
}

export async function getTopStocks({ forceRefresh = false } = {}) {
    // Serve from cache if we already fetched today and forceRefresh is not set
    if (!forceRefresh) {
        const cached = readCache();
        if (cached) return cached;
    }

    try {
        const headers = await getAuthHeaders();

        const response = await fetch(`${API_BASE}/topstocks`, { headers });

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            return topStocksMockData;
        }

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Session expired. Please sign in again.');
            }
            throw new Error(data.error || 'Failed to fetch top stocks');
        }

        if (data.stocks && data.stocks.length > 0) {
            writeCache(data.stocks);
            return data.stocks;
        }

        return topStocksMockData;
    } catch (error) {
        try {
            const raw = localStorage.getItem(CACHE_KEY);
            if (raw) {
                const { stocks } = JSON.parse(raw);
                if (Array.isArray(stocks) && stocks.length > 0) return stocks;
            }
        } catch (_) { /* ignore */ }
        return topStocksMockData;
    }
}
