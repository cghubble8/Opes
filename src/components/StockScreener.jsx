import { useState, useCallback } from 'react'
import { getScreenerResults } from '../services/screener'
import CandlestickLoader from './CandlestickLoader'
import './StockScreener.css'

const DIRECTIONS = [
    { value: 'any',     label: 'Any Direction' },
    { value: 'bullish', label: 'Bullish' },
    { value: 'bearish', label: 'Bearish' },
]

/** Format a raw market cap number into a human-readable string. */
function formatMarketCap(cap) {
    if (!cap) return null
    if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`
    if (cap >= 1e9)  return `$${(cap / 1e9).toFixed(1)}B`
    return `$${(cap / 1e6).toFixed(0)}M`
}

function StockScreener({ onStockSelect }) {
    const [direction, setDirection] = useState('any')
    const [stocks, setStocks]       = useState([])
    const [total, setTotal]         = useState(null)
    const [loading, setLoading]     = useState(false)
    const [hasRun, setHasRun]       = useState(false)
    const [error, setError]         = useState(null)

    const runScreener = useCallback(async (dir, forceRefresh = false) => {
        setLoading(true)
        setError(null)
        try {
            const data = await getScreenerResults({ direction: dir, forceRefresh })
            setStocks(data.stocks ?? [])
            setTotal(data.total ?? (data.stocks?.length ?? 0))
            setHasRun(true)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }, [])

    const handleDirectionChange = (newDir) => {
        setDirection(newDir)
        // Auto-refresh if the user has already run a scan (result is likely cached)
        if (hasRun) runScreener(newDir)
    }

    return (
        <div className="screener-container">
            {/* Controls */}
            <div className="screener-controls">
                <div className="screener-filter-group">
                    <span className="screener-filter-label">Direction</span>
                    <div className="screener-filter-pills">
                        {DIRECTIONS.map(d => (
                            <button
                                key={d.value}
                                className={`screener-pill ${d.value} ${direction === d.value ? 'active' : ''}`}
                                onClick={() => handleDirectionChange(d.value)}
                            >
                                {d.label}
                            </button>
                        ))}
                    </div>
                </div>
                <button
                    className="btn-primary screener-run-btn"
                    onClick={() => runScreener(direction, false)}
                    disabled={loading}
                >
                    {loading ? 'Scanning\u2026' : hasRun ? 'Refresh' : 'Run Screener'}
                </button>
            </div>

            {/* Loading */}
            {loading && (
                <CandlestickLoader message="Scanning 36 stocks\u2026 running ML models across all sectors" />
            )}

            {/* Error */}
            {!loading && error && (
                <div className="error-container">
                    <div className="error-icon">!</div>
                    <p className="error-message">{error}</p>
                    <button className="btn-primary" onClick={() => runScreener(direction, true)}>
                        Try Again
                    </button>
                </div>
            )}

            {/* Empty state — shown before first run */}
            {!loading && !error && !hasRun && (
                <div className="screener-empty-state">
                    <div className="screener-empty-icon">◈</div>
                    <h3>Apply filters and run the screener</h3>
                    <p>Scans 36 stocks across all major sectors using ML signals</p>
                </div>
            )}

            {/* Results */}
            {!loading && !error && hasRun && (
                <>
                    <div className="screener-results-header">
                        <span className="screener-match-count">
                            {total} stock{total !== 1 ? 's' : ''} matched
                        </span>
                        <button
                            className="refresh-btn"
                            onClick={() => runScreener(direction, true)}
                        >
                            🔄 Refresh
                        </button>
                    </div>

                    {stocks.length === 0 ? (
                        <div className="screener-no-matches">
                            <p>No stocks match the current filters.</p>
                        </div>
                    ) : (
                        <div className="screener-results-grid">
                            {stocks.map((stock) => (
                                <div
                                    key={stock.symbol}
                                    className={`screener-card direction-${stock.direction}`}
                                    onClick={() => onStockSelect(stock.symbol)}
                                >
                                    <div className="screener-card-header">
                                        <div className="screener-card-identity">
                                            <span className="screener-symbol">{stock.symbol}</span>
                                            <span className="screener-sector">{stock.sector}</span>
                                        </div>
                                        <div className={`prediction-badge ${stock.direction}`}>
                                            {stock.prediction}
                                        </div>
                                    </div>

                                    <div className="screener-card-name">{stock.name}</div>

                                    <div className="screener-card-price">
                                        <span className="price-value">${stock.price.toFixed(2)}</span>
                                        <span className={`price-change ${parseFloat(stock.change) >= 0 ? 'positive' : 'negative'}`}>
                                            {parseFloat(stock.change) >= 0 ? '▲' : '▼'} ${Math.abs(stock.change).toFixed(2)} ({stock.change_percent}%)
                                        </span>
                                    </div>

                                    <div className="screener-quality-bar">
                                        <div className="confidence-header">
                                            <span>Quality Score</span>
                                            <span className="confidence-value">{stock.quality_score?.toFixed(1)}</span>
                                        </div>
                                        <div className="confidence-bar-container">
                                            <div
                                                className={`confidence-bar-fill ${
                                                    stock.quality_score > 70 ? 'high'
                                                    : stock.quality_score > 50 ? 'medium'
                                                    : 'low'
                                                }`}
                                                style={{ width: `${stock.quality_score}%` }}
                                            />
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

                                    <div className="view-details">
                                        <span>View Full Analysis →</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            <div className="demo-notice">
                <span>Prices &amp; Fundamentals via Yahoo Finance · 36-stock universe</span>
            </div>
        </div>
    )
}

export default StockScreener
