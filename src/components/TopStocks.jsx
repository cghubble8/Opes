import { useState, useEffect } from 'react'
import { getTopStocks } from '../services/topStocks'
import CandlestickLoader from './CandlestickLoader'

const rankEmojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣']

function TopStocks({ onStockSelect }) {
    const [stocks, setStocks] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        loadTopStocks()
    }, [])

    const loadTopStocks = async (forceRefresh = false) => {
        setLoading(true)
        setError(null)
        try {
            const data = await getTopStocks({ forceRefresh })
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
                <CandlestickLoader message="Ranking top stocks by quality score\u2026" />
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

    const formatMarketCap = (cap) => {
        if (!cap) return null
        if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`
        if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`
        return `$${(cap / 1e6).toFixed(0)}M`
    }

    return (
        <div className="top-stocks-container">
            <div className="top-stocks-header">
                <h2>Top 5 Buy-Rated Stocks</h2>
                <p>Ranked by quality score: fundamentals · AI signal · momentum</p>
                <div className="refresh-row">
                    <button
                        className="refresh-btn"
                        onClick={() => loadTopStocks(true)}
                    >
                        🔄 Refresh
                    </button>
                </div>
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

                            {/* Quality Score */}
                            {stock.quality_score != null && (
                                <div className="quality-score-section">
                                    <div className="confidence-header">
                                        <span>Quality Score</span>
                                        <span className="confidence-value">{stock.quality_score.toFixed(1)}</span>
                                    </div>
                                    <div className="confidence-bar-container">
                                        <div
                                            className={`confidence-bar-fill ${stock.quality_score > 70 ? 'high' : stock.quality_score > 50 ? 'medium' : 'low'}`}
                                            style={{ width: `${stock.quality_score}%` }}
                                        ></div>
                                    </div>
                                </div>
                            )}

                            {/* AI Confidence */}
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

                            {/* Fundamentals row */}
                            {stock.fundamentals && (
                                <div className="fundamentals-mini">
                                    {stock.fundamentals.pe_ratio != null && (
                                        <span className="fund-chip">P/E {stock.fundamentals.pe_ratio.toFixed(1)}</span>
                                    )}
                                    {stock.fundamentals.roe != null && (
                                        <span className="fund-chip">ROE {(stock.fundamentals.roe * 100).toFixed(1)}%</span>
                                    )}
                                    {stock.fundamentals.market_cap != null && (
                                        <span className="fund-chip">{formatMarketCap(stock.fundamentals.market_cap)}</span>
                                    )}
                                </div>
                            )}

                            <p className="stock-reasoning">{stock.reasoning}</p>
                        </div>

                        <div className="view-details">
                            <span>View Full Analysis →</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="demo-notice">
                <span>Prices &amp; Fundamentals via Yahoo Finance</span>
            </div>
        </div>
    )
}

export default TopStocks
