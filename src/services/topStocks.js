/**
 * Top Stocks Service - Fetches top buy-rated stocks from API
 */

const API_BASE = '/api';

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

export async function getTopStocks() {
    try {
        const response = await fetch(`${API_BASE}/topstocks`);

        // Check if response is HTML (error from Vite - API not running)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            console.log('API not available, using mock data');
            await new Promise(resolve => setTimeout(resolve, 800));
            return topStocksMockData;
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch top stocks');
        }

        // Return the stocks from API response
        if (data.stocks && data.stocks.length > 0) {
            return data.stocks;
        }

        // Fallback to mock data if no stocks returned
        console.log('No stocks returned from API, using mock data');
        return topStocksMockData;
    } catch (error) {
        console.error('API Error:', error);
        // Fallback to mock data if API fails
        console.log('Falling back to mock data');
        await new Promise(resolve => setTimeout(resolve, 500));
        return topStocksMockData;
    }
}
