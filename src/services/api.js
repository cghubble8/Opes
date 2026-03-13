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
        clearStaleCacheEntries(); // purge old-version entries on every read
        const raw = localStorage.getItem(analysisCacheKey(symbol));
        if (!raw) return null;
        const data = JSON.parse(raw);
        console.log(`Analyze (${symbol}): serving from daily cache`);
        return data;
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
        console.error('API Error:', error);
        // Try stale cache (same version, any day) before surfacing the error
        try {
            const keys = Object.keys(localStorage).filter(k => k.startsWith(`analyze_v${CACHE_VERSION}_${key}_`));
            if (keys.length > 0) {
                const stale = JSON.parse(localStorage.getItem(keys[0]));
                if (stale) {
                    console.log(`Analyze (${key}): API failed, serving stale cache`);
                    return stale;
                }
            }
        } catch (_) { /* ignore */ }
        // Re-throw so the UI shows the real error instead of misleading mock data
        throw error;
    }
}

// For development/demo with mock data
export const mockData = {
    symbol: "AAPL",
    name: "Apple Inc.",
    sector: "Technology",
    quote: {
        symbol: "AAPL",
        price: 189.50,
        change: 2.35,
        change_percent: "1.26",
        volume: 52840000,
        latest_trading_day: "2024-12-04"
    },
    indicators: {
        sma_20: 187.45,
        sma_50: 183.20,
        ema_12: 188.30,
        ema_26: 185.75,
        rsi: 58.4,
        macd: 2.55,
        macd_signal: 1.89,
        macd_histogram: 0.66,
        bollinger_upper: 195.20,
        bollinger_middle: 187.45,
        bollinger_lower: 179.70,
        obv: 1250000000
    },
    signals: {
        rsi: "Neutral",
        macd: "Bullish",
        bollinger: "Within Bands",
        trend: "Uptrend"
    },
    fundamentals: {
        pe_ratio: 28.5,
        eps: 6.65,
        roe: 0.175,
        market_cap: 2950000000000,
        dividend_yield: 0.0051,
        "52_week_high": 199.62,
        "52_week_low": 164.08
    },
    prediction: {
        prediction: "Moderate Buy Signal",
        confidence: 67.5,
        direction: "bullish",
        reasoning: "Based on Returns, Volume, RSI patterns from recent trading history. Fundamentals appear strong (low P/E, high ROE).",
        model_accuracy: 71.2
    },
    chart_data: {
        dates: [...Array(60)].map((_, i) => {
            const d = new Date();
            d.setDate(d.getDate() - (59 - i));
            return d.toISOString().split('T')[0];
        }),
        closes: [...Array(60)].map((_, i) => 175 + Math.sin(i * 0.1) * 10 + i * 0.25),
        sma_20: [...Array(60)].map((_, i) => i < 19 ? null : 175 + (i - 10) * 0.2),
        bollinger_upper: [...Array(60)].map((_, i) => i < 19 ? null : 185 + (i - 10) * 0.2),
        bollinger_lower: [...Array(60)].map((_, i) => i < 19 ? null : 165 + (i - 10) * 0.2)
    }
};
