/**
 * Mock Portfolio Data with Chart Data
 */

// Generate sparkline data for each stock
const generateSparkline = (basePrice, trend = 'up', volatility = 0.02) => {
    const points = [];
    let price = basePrice * 0.95;
    for (let i = 0; i < 30; i++) {
        const trendFactor = trend === 'up' ? 0.003 : trend === 'down' ? -0.002 : 0;
        const change = (Math.random() - 0.5) * volatility + trendFactor;
        price = price * (1 + change);
        points.push(price);
    }
    return points;
};

// Generate portfolio value history
const generatePortfolioHistory = () => {
    const points = [];
    let value = 115000;
    for (let i = 0; i < 90; i++) {
        const change = (Math.random() - 0.45) * 0.015;
        value = value * (1 + change);
        points.push({
            date: new Date(Date.now() - (89 - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
            value: Math.round(value * 100) / 100
        });
    }
    return points;
};

export const portfolioMockData = {
    totalValue: 127845.32,
    totalCost: 105000.00,
    totalGain: 22845.32,
    totalGainPercent: 21.76,
    dayChange: 1234.56,
    dayChangePercent: 0.97,
    portfolioHistory: generatePortfolioHistory(),
    holdings: [
        {
            symbol: "AAPL",
            name: "Apple Inc.",
            shares: 50,
            avgCost: 165.00,
            currentPrice: 189.50,
            value: 9475.00,
            gain: 1225.00,
            gainPercent: 14.85,
            dayChange: 92.50,
            dayChangePercent: 0.99,
            sparkline: generateSparkline(189.50, 'up'),
        },
        {
            symbol: "NVDA",
            name: "NVIDIA Corporation",
            shares: 25,
            avgCost: 380.00,
            currentPrice: 467.85,
            value: 11696.25,
            gain: 2196.25,
            gainPercent: 23.12,
            dayChange: 311.25,
            dayChangePercent: 2.73,
            sparkline: generateSparkline(467.85, 'up', 0.03),
        },
        {
            symbol: "MSFT",
            name: "Microsoft Corporation",
            shares: 30,
            avgCost: 350.00,
            currentPrice: 378.91,
            value: 11367.30,
            gain: 867.30,
            gainPercent: 8.26,
            dayChange: 85.20,
            dayChangePercent: 0.75,
            sparkline: generateSparkline(378.91, 'up', 0.015),
        },
        {
            symbol: "GOOGL",
            name: "Alphabet Inc.",
            shares: 75,
            avgCost: 125.00,
            currentPrice: 141.23,
            value: 10592.25,
            gain: 1217.25,
            gainPercent: 12.98,
            dayChange: 71.25,
            dayChangePercent: 0.68,
            sparkline: generateSparkline(141.23, 'neutral'),
        },
        {
            symbol: "AMZN",
            name: "Amazon.com Inc.",
            shares: 40,
            avgCost: 140.00,
            currentPrice: 153.89,
            value: 6155.60,
            gain: 555.60,
            gainPercent: 9.92,
            dayChange: 93.60,
            dayChangePercent: 1.54,
            sparkline: generateSparkline(153.89, 'up'),
        },
        {
            symbol: "TSLA",
            name: "Tesla Inc.",
            shares: 20,
            avgCost: 220.00,
            currentPrice: 251.44,
            value: 5028.80,
            gain: 628.80,
            gainPercent: 14.29,
            dayChange: -85.40,
            dayChangePercent: -1.67,
            sparkline: generateSparkline(251.44, 'down', 0.025),
        },
    ],
};

export async function getPortfolio() {
    await new Promise(resolve => setTimeout(resolve, 600));
    return portfolioMockData;
}
