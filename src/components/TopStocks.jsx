import { useState, useEffect } from 'react'
import { getTopStocks } from '../services/topStocks'

const rankEmojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

function TopStocks({ onStockSelect }) {
    const [stocks, setStocks] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        loadTopStocks()
    }, [])

    const loadTopStocks = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await getTopStocks()
            setStocks(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="top-stocks-container">
                <div className="top-stocks-header">
                    <h2>Top 5 Buy-Rated Stocks</h2>
                    <p>AI-powered analysis of market leaders</p>
                </div>
                <div className="top-stocks-grid">
                    {[1, 2, 3, 4, 5].map(i => (
                        <div key={i} className="stock-rank-card skeleton">
                            <div className="skeleton-rank"></div>
                            <div className="skeleton-content">
                                <div className="skeleton-line wide"></div>
                                <div className="skeleton-line medium"></div>
                                <div className="skeleton-line narrow"></div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="top-stocks-container">
                <div className="error-container">
                    <div className="error-icon">⚠️</div>
                    <p className="error-message">{error}</p>
                    <button className="btn-primary" onClick={loadTopStocks}>Try Again</button>
                </div>
            </div>
        )
    }

    return (
        <div className="top-stocks-container">
            <div className="top-stocks-header">
                <h2>Top 5 Buy-Rated Stocks</h2>
                <p>AI-powered analysis of market leaders</p>
            </div>

            <div className="top-stocks-grid">
                {stocks.map((stock, index) => (
                    <div
                        key={stock.symbol}
                        className={`stock-rank-card rank-${index + 1}`}
                        onClick={() => onStockSelect(stock.symbol)}
                    >
                        <div className="rank-badge">
                            <span className="rank-emoji">{rankEmojis[index]}</span>
                            <span className="rank-number">#{index + 1}</span>
                        </div>

                        <div className="stock-rank-info">
                            <div className="stock-rank-header">
                                <span className="stock-rank-symbol">{stock.symbol}</span>
                                <span className="stock-rank-sector">{stock.sector}</span>
                            </div>
                            <div className="stock-rank-name">{stock.name}</div>

                            <div className="stock-rank-price">
                                <span className="price-value">${stock.price.toFixed(2)}</span>
                                <span className={`price-change ${stock.change >= 0 ? 'positive' : 'negative'}`}>
                                    {stock.change >= 0 ? '▲' : '▼'} ${Math.abs(stock.change).toFixed(2)} ({stock.change_percent}%)
                                </span>
                            </div>
                        </div>

                        <div className="stock-rank-prediction">
                            <div className={`prediction-badge ${stock.direction}`}>
                                {stock.prediction}
                            </div>
                            <div className="confidence-section">
                                <div className="confidence-header">
                                    <span>AI Confidence</span>
                                    <span className="confidence-value">{stock.confidence}%</span>
                                </div>
                                <div className="confidence-bar-container">
                                    <div
                                        className={`confidence-bar-fill ${stock.confidence > 70 ? 'high' : stock.confidence > 55 ? 'medium' : 'low'}`}
                                        style={{ width: `${stock.confidence}%` }}
                                    ></div>
                                </div>
                            </div>
                            <p className="stock-reasoning">{stock.reasoning}</p>
                        </div>

                        <div className="view-details">
                            <span>View Full Analysis →</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="demo-notice">
                <span>Live market data via yfinance</span>
            </div>
        </div>
    )
}

export default TopStocks
