import { useState, useEffect } from 'react'
import { AreaChart, Area, ResponsiveContainer, LineChart, Line } from 'recharts'
import { getPortfolio } from '../services/portfolio'

function Portfolio({ onStockSelect }) {
    const [portfolio, setPortfolio] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [selectedPeriod, setSelectedPeriod] = useState('3M')

    useEffect(() => {
        loadPortfolio()
    }, [])

    const loadPortfolio = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await getPortfolio()
            setPortfolio(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const formatCurrency = (num) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
        }).format(num)
    }

    // Convert sparkline array to chart data format
    const getSparklineData = (sparkline) => {
        return sparkline.map((value, index) => ({ value }))
    }

    // Mini sparkline component for each holding
    const Sparkline = ({ data, positive }) => (
        <div className="sparkline-container">
            <ResponsiveContainer width="100%" height={40}>
                <AreaChart data={getSparklineData(data)}>
                    <defs>
                        <linearGradient id={`spark-${positive ? 'up' : 'down'}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={positive ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={positive ? '#10b981' : '#ef4444'} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <Area
                        type="monotone"
                        dataKey="value"
                        stroke={positive ? '#10b981' : '#ef4444'}
                        fill={`url(#spark-${positive ? 'up' : 'down'})`}
                        strokeWidth={1.5}
                        dot={false}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )

    if (loading) {
        return (
            <div className="portfolio-container">
                <div className="portfolio-hero skeleton-hero">
                    <div className="skeleton-chart"></div>
                </div>
                <div className="holdings-section">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="holding-card-new card skeleton">
                            <div className="skeleton-line wide"></div>
                            <div className="skeleton-line medium"></div>
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="portfolio-container">
                <div className="error-container">
                    <div className="error-icon">⚠️</div>
                    <p className="error-message">{error}</p>
                    <button className="btn-primary" onClick={loadPortfolio}>Try Again</button>
                </div>
            </div>
        )
    }

    return (
        <div className="portfolio-container">
            {/* Portfolio Hero with Chart */}
            <div className="portfolio-hero">
                <div className="hero-content">
                    <span className="hero-label">Portfolio Value</span>
                    <div className="hero-value">{formatCurrency(portfolio.totalValue)}</div>
                    <div className={`hero-change ${portfolio.dayChange >= 0 ? 'positive' : 'negative'}`}>
                        <span>{portfolio.dayChange >= 0 ? '▲' : '▼'}</span>
                        <span>{formatCurrency(Math.abs(portfolio.dayChange))}</span>
                        <span>({portfolio.dayChangePercent >= 0 ? '+' : ''}{portfolio.dayChangePercent}%)</span>
                        <span className="period-label">Today</span>
                    </div>
                </div>

                {/* Portfolio Value Chart */}
                <div className="portfolio-chart">
                    <ResponsiveContainer width="100%" height={180}>
                        <AreaChart data={portfolio.portfolioHistory}>
                            <defs>
                                <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <Area
                                type="monotone"
                                dataKey="value"
                                stroke="#10b981"
                                fill="url(#portfolioGradient)"
                                strokeWidth={2}
                                dot={false}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>

                {/* Time Period Selector */}
                <div className="period-selector">
                    {['1D', '1W', '1M', '3M', '1Y', 'ALL'].map(period => (
                        <button
                            key={period}
                            className={`period-btn ${selectedPeriod === period ? 'active' : ''}`}
                            onClick={() => setSelectedPeriod(period)}
                        >
                            {period}
                        </button>
                    ))}
                </div>
            </div>

            {/* Stats Row */}
            <div className="stats-row">
                <div className="stat-card card">
                    <span className="stat-card-label">Total Gain</span>
                    <span className={`stat-card-value ${portfolio.totalGain >= 0 ? 'positive' : 'negative'}`}>
                        {portfolio.totalGain >= 0 ? '+' : ''}{formatCurrency(portfolio.totalGain)}
                    </span>
                    <span className="stat-card-percent positive">+{portfolio.totalGainPercent}%</span>
                </div>
                <div className="stat-card card">
                    <span className="stat-card-label">Invested</span>
                    <span className="stat-card-value">{formatCurrency(portfolio.totalCost)}</span>
                </div>
            </div>

            {/* Holdings List */}
            <div className="holdings-section">
                <div className="section-header">
                    <h3>Holdings</h3>
                    <span className="holdings-count">{portfolio.holdings.length} stocks</span>
                </div>

                <div className="holdings-list-new">
                    {portfolio.holdings.map((holding) => (
                        <div
                            key={holding.symbol}
                            className="holding-card-new card"
                            onClick={() => onStockSelect(holding.symbol)}
                        >
                            <div className="holding-left">
                                <div className="holding-icon">
                                    {holding.symbol.slice(0, 2)}
                                </div>
                                <div className="holding-details">
                                    <span className="holding-symbol-new">{holding.symbol}</span>
                                    <span className="holding-shares-new">{holding.shares} shares</span>
                                </div>
                            </div>

                            <div className="holding-center">
                                <Sparkline data={holding.sparkline} positive={holding.dayChange >= 0} />
                            </div>

                            <div className="holding-right">
                                <span className="holding-price">{formatCurrency(holding.currentPrice)}</span>
                                <span className={`holding-change ${holding.dayChange >= 0 ? 'positive' : 'negative'}`}>
                                    {holding.dayChange >= 0 ? '+' : ''}{holding.dayChangePercent}%
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="demo-notice">
                <span>Demo portfolio with simulated data</span>
            </div>
        </div>
    )
}

export default Portfolio
