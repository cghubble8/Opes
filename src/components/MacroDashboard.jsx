import { useState, useEffect } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Cell,
} from 'recharts'
import { getMacroData } from '../services/macro'
import CandlestickLoader from './CandlestickLoader'

function changeColor(pct) {
    return parseFloat(pct) >= 0 ? '#34D27A' : '#FF6058'
}

function dirColor(direction) {
    if (direction === 'bullish') return '#34D27A'
    if (direction === 'bearish') return '#FF6058'
    return '#A89880'
}

function rsiColor(rsi) {
    if (rsi == null) return 'var(--text-muted)'
    if (rsi > 70) return '#FF6058'
    if (rsi < 30) return '#34D27A'
    return 'var(--text-secondary)'
}

function vixColor(label) {
    if (label === 'Low')      return '#34D27A'
    if (label === 'Moderate') return '#C9A84C'
    if (label === 'Elevated') return '#FF9858'
    return '#FF6058'
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function IndexCard({ sym, data }) {
    if (!data) return null
    const isVix = data.is_vix

    return (
        <div className={`card macro-index-card ${!isVix && data.direction ? `macro-${data.direction}` : ''}`}>
            <div className="macro-card-header">
                <span className="macro-card-symbol">{sym}</span>
                <span className="macro-card-name">{data.name || sym}</span>
            </div>
            <div className="macro-card-price">
                <span className="macro-price">${data.price?.toFixed(2)}</span>
                {!isVix && (
                    <span className="macro-change" style={{ color: changeColor(data.change_percent) }}>
                        {parseFloat(data.change_percent) >= 0 ? '▲' : '▼'} {Math.abs(parseFloat(data.change_percent)).toFixed(2)}%
                    </span>
                )}
            </div>

            {isVix ? (
                <div className="macro-vix-label" style={{ color: vixColor(data.label) }}>
                    {data.label} Volatility
                </div>
            ) : (
                <>
                    <div className="macro-rating" style={{ color: dirColor(data.direction) }}>
                        {data.rating || data.prediction}
                    </div>
                    {data.quality_score != null && (
                        <div className="confidence-meter" style={{ marginTop: 8 }}>
                            <div className="confidence-label">
                                <span>Quality Score</span>
                                <span>{data.quality_score} / 100</span>
                            </div>
                            <div className="confidence-bar">
                                <div
                                    className={`confidence-fill ${data.quality_score > 70 ? 'high' : data.quality_score > 50 ? 'medium' : 'low'}`}
                                    style={{ width: `${data.quality_score}%` }}
                                />
                            </div>
                        </div>
                    )}
                    <div className="macro-stats-row">
                        <span className="macro-stat">
                            RSI <span style={{ color: rsiColor(data.indicators?.rsi) }}>{data.indicators?.rsi ?? 'N/A'}</span>
                        </span>
                        <span className="macro-stat">{data.signals?.trend}</span>
                    </div>
                </>
            )}
        </div>
    )
}

function SectorCard({ sym, data }) {
    if (!data) return null
    const rsi = data.indicators?.rsi

    return (
        <div className="card macro-sector-card">
            <div className="macro-sector-header">
                <div>
                    <span className="macro-sector-sym">{sym}</span>
                    <span className="macro-sector-name">{data.sector_name}</span>
                </div>
                <span className={`prediction-badge ${data.direction}`}>
                    {data.direction}
                </span>
            </div>

            <div className="macro-sector-price-row">
                <span className="macro-sector-price">${data.price?.toFixed(2)}</span>
                <span style={{ color: changeColor(data.change_percent), fontSize: '0.85rem' }}>
                    {parseFloat(data.change_percent) >= 0 ? '▲' : '▼'} {Math.abs(parseFloat(data.change_percent)).toFixed(2)}%
                </span>
            </div>

            <div className="macro-sector-metrics">
                <div className="macro-metric">
                    <span className="macro-metric-label">RSI</span>
                    <span className="macro-metric-value" style={{ color: rsiColor(rsi) }}>
                        {rsi ?? 'N/A'}
                        {rsi > 70 ? ' OB' : rsi < 30 ? ' OS' : ''}
                    </span>
                </div>
                {data.perf_1m != null && (
                    <div className="macro-metric">
                        <span className="macro-metric-label">1M</span>
                        <span className="macro-metric-value" style={{ color: changeColor(data.perf_1m) }}>
                            {data.perf_1m > 0 ? '+' : ''}{data.perf_1m}%
                        </span>
                    </div>
                )}
                {data.perf_3m != null && (
                    <div className="macro-metric">
                        <span className="macro-metric-label">3M</span>
                        <span className="macro-metric-value" style={{ color: changeColor(data.perf_3m) }}>
                            {data.perf_3m > 0 ? '+' : ''}{data.perf_3m}%
                        </span>
                    </div>
                )}
            </div>
        </div>
    )
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function MacroDashboard() {
    const [macroData, setMacroData] = useState(null)
    const [loading, setLoading]     = useState(true)
    const [error, setError]         = useState(null)

    useEffect(() => {
        getMacroData()
            .then(setMacroData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }, [])

    const handleRefresh = () => {
        setLoading(true)
        setError(null)
        getMacroData({ forceRefresh: true })
            .then(setMacroData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }

    if (loading) {
        return <CandlestickLoader message="Fetching market data & running sector analysis…" />
    }

    if (error) {
        return (
            <div className="error-container">
                <div className="error-icon">!</div>
                <p className="error-message">{error}</p>
                <button className="btn-primary" onClick={handleRefresh} style={{ marginTop: 12 }}>Retry</button>
            </div>
        )
    }

    if (!macroData) return null

    const indices = macroData.indices || {}
    const sectors = macroData.sectors || {}

    // Build sorted bar chart data by 1-month performance
    const chartData = Object.values(sectors)
        .filter(s => s.perf_1m != null)
        .map(s => ({ name: s.symbol, perf: s.perf_1m, direction: s.direction }))
        .sort((a, b) => b.perf - a.perf)

    // Count bullish sectors for breadth
    const bullishCount = Object.values(sectors).filter(s => s.direction === 'bullish').length
    const totalSectors = Object.keys(sectors).length

    return (
        <div className="macro-dashboard">
            <div className="macro-header-row">
                <h2 className="macro-title">Market Overview</h2>
                <div className="macro-header-right">
                    {macroData.generated_at && (
                        <span className="macro-date">As of {macroData.generated_at}</span>
                    )}
                    <button className="btn-refresh" onClick={handleRefresh} title="Refresh market data">↻ Refresh</button>
                </div>
            </div>

            {/* Breadth summary */}
            <div className="macro-breadth">
                <span className="macro-breadth-label">Market Breadth:</span>
                <span style={{ color: bullishCount > totalSectors / 2 ? '#34D27A' : '#FF6058', fontWeight: 600 }}>
                    {bullishCount}/{totalSectors} sectors bullish
                </span>
            </div>

            {/* Index Cards */}
            <div className="macro-indices-grid">
                {['SPY', 'QQQ'].map(sym => (
                    <IndexCard key={sym} sym={sym} data={indices[sym]} />
                ))}
                <IndexCard sym="VIX" data={indices['^VIX']} />
            </div>

            {/* Sector Performance Chart */}
            {chartData.length > 0 && (
                <div className="card macro-chart-card">
                    <h3>1-Month Sector Performance</h3>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={chartData} margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(201,168,76,0.08)" />
                            <XAxis dataKey="name" stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }} />
                            <YAxis
                                stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }}
                                tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`}
                            />
                            <Tooltip
                                formatter={(v, _name, props) => [
                                    `${v > 0 ? '+' : ''}${v}%`,
                                    props.payload?.name,
                                ]}
                                contentStyle={{
                                    background: '#1a1a1a',
                                    border: '1px solid rgba(201,168,76,0.22)',
                                    borderRadius: '10px',
                                    color: '#F0EAD6',
                                    fontSize: '0.8125rem',
                                }}
                                labelStyle={{ color: '#A89880', marginBottom: 4 }}
                            />
                            <Bar dataKey="perf" radius={[3, 3, 0, 0]}>
                                {chartData.map((entry, i) => (
                                    <Cell
                                        key={i}
                                        fill={entry.direction === 'bullish' ? '#34D27A' : entry.direction === 'bearish' ? '#FF6058' : '#A89880'}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}

            {/* Sector Grid */}
            <h3 className="macro-section-title">Sector ETFs</h3>
            <div className="macro-sectors-grid">
                {Object.entries(sectors).map(([sym, data]) => (
                    <SectorCard key={sym} sym={sym} data={data} />
                ))}
            </div>
        </div>
    )
}
