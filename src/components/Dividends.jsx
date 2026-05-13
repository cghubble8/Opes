import { useState, useEffect, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getDividendProfile, getTopDividends } from '../services/dividends'
import CandlestickLoader from './CandlestickLoader'

function SafeScoreBar({ score, label }) {
    const color =
        score >= 60 ? 'var(--success-light)' :
        score >= 40 ? 'var(--warning-light)' :
        'var(--danger-light)'

    return (
        <div className="safety-score-bar">
            <div className="safety-score-header">
                <span className="safety-score-label">Safety Score</span>
                <span className="safety-score-value" style={{ color }}>{score}/100</span>
            </div>
            <div className="safety-score-track">
                <div
                    className="safety-score-fill"
                    style={{ width: `${score}%`, background: color }}
                />
            </div>
            <span className="safety-score-badge" style={{ color }}>{label}</span>
        </div>
    )
}

function DividendHistoryChart({ history, growthRate }) {
    if (!history || history.length === 0) return null

    // Aggregate into annual totals for a cleaner chart
    const byYear = {}
    history.forEach(({ date, amount }) => {
        const yr = date.slice(0, 4)
        byYear[yr] = (byYear[yr] || 0) + amount
    })
    const chartData = Object.entries(byYear)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([year, total]) => ({ year, total: +total.toFixed(2) }))

    const growthLabel = growthRate != null
        ? `${growthRate >= 0 ? '+' : ''}${growthRate.toFixed(1)}% avg annual growth`
        : null

    return (
        <div className="dividend-history-chart">
            <div className="div-chart-header">
                <h3>Dividend History (5yr)</h3>
                {growthLabel && <span className="div-chart-growth">{growthLabel}</span>}
            </div>
            <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                    <XAxis dataKey="year" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} width={40} />
                    <Tooltip
                        contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 8 }}
                        labelStyle={{ color: 'var(--text-secondary)' }}
                        itemStyle={{ color: 'var(--gold-primary)' }}
                        formatter={(v) => [`$${v.toFixed(2)}`, 'Annual Div']}
                    />
                    <Bar dataKey="total" fill="var(--gold-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    )
}

function TopDivCard({ stock, onSelect }) {
    const safeColor =
        stock.safety_score >= 60 ? 'var(--success-light)' :
        stock.safety_score >= 40 ? 'var(--warning-light)' :
        'var(--danger-light)'

    const dirClass = stock.direction === 'bullish' ? 'bullish' : stock.direction === 'bearish' ? 'bearish' : 'neutral'

    return (
        <div className="dividend-stock-card" onClick={() => onSelect(stock.symbol)}>
            <div className="div-card-top">
                <div>
                    <span className="div-card-symbol">{stock.symbol}</span>
                    <span className="div-card-sector">{stock.sector}</span>
                </div>
                <div className={`prediction-badge ${dirClass}`} style={{ fontSize: '0.7rem' }}>
                    {stock.direction}
                </div>
            </div>
            <div className="div-card-name">{stock.name}</div>
            <div className="div-card-stats">
                <div className="div-card-yield">
                    <span className="div-stat-label">Yield</span>
                    <span className="div-stat-value gold">{stock.dividend_yield?.toFixed(2)}%</span>
                </div>
                <div className="div-card-safety">
                    <span className="div-stat-label">Safety</span>
                    <span className="div-stat-value" style={{ color: safeColor }}>{stock.safety_score}</span>
                </div>
                {stock.price != null && (
                    <div className="div-card-price">
                        <span className="div-stat-label">Price</span>
                        <span className="div-stat-value">${stock.price.toFixed(2)}</span>
                    </div>
                )}
            </div>
        </div>
    )
}

export default function Dividends({ onStockSelect, initialSymbol }) {
    const [symbol, setSymbol]             = useState('')
    const [profile, setProfile]           = useState(null)
    const [profileLoading, setProfileLoading] = useState(false)
    const [profileError, setProfileError] = useState(null)
    const [topStocks, setTopStocks]       = useState([])
    const [topLoading, setTopLoading]     = useState(true)
    const [topError, setTopError]         = useState(null)

    const loadProfile = useCallback(async (sym) => {
        if (!sym) return
        setProfileLoading(true)
        setProfileError(null)
        try {
            const data = await getDividendProfile(sym)
            setProfile(data)
        } catch (err) {
            setProfileError(err.message)
        } finally {
            setProfileLoading(false)
        }
    }, [])

    const loadTopDividends = useCallback(async (forceRefresh = false) => {
        setTopLoading(true)
        setTopError(null)
        try {
            const stocks = await getTopDividends({ forceRefresh })
            setTopStocks(stocks)
        } catch (err) {
            setTopError(err.message)
        } finally {
            setTopLoading(false)
        }
    }, [])

    useEffect(() => {
        loadTopDividends()
    }, [loadTopDividends])

    // Pre-load when navigated from Analyze "View Full Profile" button
    useEffect(() => {
        if (initialSymbol) {
            setSymbol(initialSymbol)
            loadProfile(initialSymbol)
        }
    }, [initialSymbol, loadProfile])

    const handleSubmit = (e) => {
        e.preventDefault()
        if (!symbol.trim()) return
        loadProfile(symbol.trim().toUpperCase())
    }

    const handleCardSelect = (sym) => {
        setSymbol(sym)
        loadProfile(sym)
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    const p = profile

    return (
        <div className="dividends-container">
            {/* ── Search Row ── */}
            <div className="div-search-row">
                <form className="search-form" onSubmit={handleSubmit} style={{ margin: 0 }}>
                    <input
                        type="text"
                        className="search-input"
                        placeholder="Symbol (e.g. KO, ABBV, JNJ)"
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                    />
                    <button type="submit" className="btn-primary search-btn" disabled={profileLoading}>
                        {profileLoading ? 'Loading…' : 'Analyze'}
                    </button>
                </form>
            </div>

            {/* ── Dividend Profile ── */}
            {profileLoading && (
                <CandlestickLoader message={`Loading dividend profile for ${symbol}…`} />
            )}

            {profileError && (
                <div className="error-container" style={{ marginBottom: 24 }}>
                    <div className="error-icon">!</div>
                    <p className="error-message">{profileError}</p>
                </div>
            )}

            {!profileLoading && !profileError && p && (
                <div className="card dividend-profile-card">
                    <div className="div-profile-header">
                        <h2 className="div-profile-symbol">{p.symbol}</h2>
                        <span className="div-profile-name">{p.name}</span>
                    </div>

                    {!p.pays_dividend ? (
                        <div className="no-dividend-card">
                            <div className="no-div-icon">—</div>
                            <p className="no-div-text">This stock does not pay a dividend.</p>
                            {onStockSelect && (
                                <button className="btn-primary" style={{ marginTop: 12 }} onClick={() => onStockSelect(p.symbol)}>
                                    View Full Analysis →
                                </button>
                            )}
                        </div>
                    ) : (
                        <>
                            {/* Hero stat row */}
                            <div className="dividend-profile-hero">
                                <div className="div-hero-stat">
                                    <span className="div-hero-label">Yield</span>
                                    <span className="div-stat-large gold">{p.dividend_yield?.toFixed(2)}%</span>
                                </div>
                                <div className="div-hero-stat">
                                    <span className="div-hero-label">Annual $/share</span>
                                    <span className="div-stat-large">${p.dividend_rate?.toFixed(2) ?? '—'}</span>
                                </div>
                                {p.ex_dividend_date && (
                                    <div className="div-hero-stat">
                                        <span className="div-hero-label">Ex-Div Date</span>
                                        <span className="div-stat-large">{p.ex_dividend_date}</span>
                                    </div>
                                )}
                                {p.next_dividend_date && (
                                    <div className="div-hero-stat">
                                        <span className="div-hero-label">Next Payment</span>
                                        <span className="div-stat-large">{p.next_dividend_date}</span>
                                    </div>
                                )}
                            </div>

                            {/* Safety score */}
                            {p.safety_score != null && (
                                <SafeScoreBar score={p.safety_score} label={p.safety_label} />
                            )}

                            {/* Metrics row */}
                            <div className="div-metrics-row">
                                {p.payout_ratio != null && (
                                    <div className="div-metric">
                                        <span className="div-metric-label">Payout Ratio</span>
                                        <span className="div-metric-value">{(p.payout_ratio * 100).toFixed(1)}%</span>
                                    </div>
                                )}
                                {p.payment_frequency && (
                                    <div className="div-metric">
                                        <span className="div-metric-label">Frequency</span>
                                        <span className="div-metric-value" style={{ textTransform: 'capitalize' }}>{p.payment_frequency}</span>
                                    </div>
                                )}
                                {p.consecutive_growth_years != null && (
                                    <div className="div-metric">
                                        <span className="div-metric-label">Growth Streak</span>
                                        <span className="div-metric-value">{p.consecutive_growth_years} yr{p.consecutive_growth_years !== 1 ? 's' : ''}</span>
                                    </div>
                                )}
                            </div>

                            {/* Aristocrat badge */}
                            {p.consecutive_growth_years >= 25 && (
                                <div className="dividend-aristocrat-badge">
                                    ★ Dividend Aristocrat — {p.consecutive_growth_years}+ years of growth
                                </div>
                            )}

                            {/* History chart */}
                            <DividendHistoryChart history={p.history} growthRate={p.growth_rate_3yr} />

                            {onStockSelect && (
                                <button
                                    className="btn-compare"
                                    style={{ marginTop: 16, width: '100%' }}
                                    onClick={() => onStockSelect(p.symbol)}
                                >
                                    View Full Analysis →
                                </button>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ── Top Dividend Stocks ── */}
            <div className="div-top-section">
                <div className="div-top-header">
                    <h2>Top Dividend Stocks</h2>
                    <button
                        className="btn-refresh"
                        onClick={() => loadTopDividends(true)}
                        disabled={topLoading}
                    >
                        ↻ Refresh
                    </button>
                </div>
                <p className="div-top-subtitle">Ranked by yield × safety × fundamentals across the 36-stock watchlist</p>

                {topLoading && (
                    <CandlestickLoader message="Screening watchlist for top dividend payers…" />
                )}

                {topError && !topLoading && (
                    <div className="error-container">
                        <div className="error-icon">!</div>
                        <p className="error-message">{topError}</p>
                        <button className="btn-primary" onClick={() => loadTopDividends()}>Try Again</button>
                    </div>
                )}

                {!topLoading && !topError && (
                    <div className="dividend-stocks-grid">
                        {topStocks.map((stock) => (
                            <TopDivCard key={stock.symbol} stock={stock} onSelect={handleCardSelect} />
                        ))}
                        {topStocks.length === 0 && (
                            <p style={{ color: 'var(--text-muted)' }}>No dividend stocks found.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
