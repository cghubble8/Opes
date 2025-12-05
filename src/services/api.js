/**
 * API Service for Stock Analysis
 */

const API_BASE = '/api';

export async function analyzeStock(symbol) {
    try {
        const response = await fetch(`${API_BASE}/analyze?symbol=${encodeURIComponent(symbol)}`);

        // Check if response is HTML (error from Vite - API not running)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            console.log('API not available, using mock data');
            await new Promise(resolve => setTimeout(resolve, 1000));
            return { ...mockData, symbol: symbol.toUpperCase() };
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze stock');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        // Fallback to mock data if API fails
        console.log('Falling back to mock data');
        await new Promise(resolve => setTimeout(resolve, 500));
        return { ...mockData, symbol: symbol.toUpperCase() };
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
