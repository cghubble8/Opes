import { useState, useEffect } from 'react'
import { getTopStocks } from '../services/topStocks'
import CandlestickLoader from './CandlestickLoader'
import StockScreener from './StockScreener'


function TopStocks({ onStockSelect }) {
    const [activeTab, setActiveTab]       = useState('top5')
    const [stocks, setStocks]             = useState([])
    const [loading, setLoading]           = useState(true)
    const [error, setError]               = useState(null)
    const [lastRefreshed, setLastRefreshed] = useState(null)

    useEffect(() => {
        loadTopStocks()
    }, [])

    const loadTopStocks = async (forceRefresh = false) => {
        setLoading(true)
        setError(null)
        try {
            const data = await getTopStocks({ forceRefresh })
            setStocks(data)
            setLastRefreshed(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
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
                <div className="ts-header-row">
                    <div className="ts-header-title">
                        <h2>Stock Intelligence</h2>
                        <p>ML-powered signals across the market</p>
                    </div>
                    {activeTab === 'top5' && !loading && !error && (
                        <div className="ts-header-actions">
                            {lastRefreshed && (
                                <span className="macro-date">As of {lastRefreshed}</span>
                            )}
                            <button
                                className="btn-refresh"
                                onClick={() => loadTopStocks(true)}
                                title="Refresh top stocks"
                            >
                                ↻ Refresh
                            </button>
                        </div>
                    )}
                </div>
                <div className="ts-tab-bar">
                    <button
                        className={`ts-tab ${activeTab === 'top5' ? 'active' : ''}`}
                        onClick={() => setActiveTab('top5')}
                    >
                        Top 5 Buys
                    </button>
                    <button
                        className={`ts-tab ${activeTab === 'screener' ? 'active' : ''}`}
                        onClick={() => setActiveTab('screener')}
                    >
                        Screener
                    </button>
                </div>
            </div>

            {/* Top 5 Tab */}
            {activeTab === 'top5' && (
                <>
                    {loading && (
                        <CandlestickLoader message="Ranking top stocks by quality score\u2026" />
                    )}

                    {!loading && error && (
                        <div className="error-container">
                            <div className="error-icon">!</div>
                            <p className="error-message">{error}</p>
                            <button className="btn-primary" onClick={() => loadTopStocks()}>Try Again</button>
                        </div>
                    )}

                    {!loading && !error && (
                        <>
                            <div className="top-stocks-grid">
                                {stocks.map((stock, index) => (
                                    <div
                                        key={stock.symbol}
                                        className={`stock-rank-card rank-${index + 1}`}
                                        onClick={() => onStockSelect(stock.symbol)}
                                    >
                                        <div className={`rank-badge rank-badge-${index + 1}`}>
                                            <span className="rank-number">{index + 1}</span>
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
                        </>
                    )}
                </>
            )}

            {/* Screener Tab */}
            {activeTab === 'screener' && (
                <StockScreener onStockSelect={onStockSelect} />
            )}
        </div>
    )
}

export default TopStocks
