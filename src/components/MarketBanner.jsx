import { useState, useEffect } from 'react'
import { getMacroData } from '../services/macro'
import './MarketBanner.css'

// VIX color by volatility regime
function vixColor(label) {
    if (label === 'Low')          return '#34D27A'
    if (label === 'Moderate')     return '#C9A84C'
    if (label === 'Elevated')     return '#FF9858'
    return '#FF6058' // Extreme Fear
}

// Change text color
function changeColor(pct) {
    return parseFloat(pct) >= 0 ? '#34D27A' : '#FF6058'
}

// Direction color for the sector chip
function dirColor(direction) {
    if (direction === 'bullish') return '#34D27A'
    if (direction === 'bearish') return '#FF6058'
    return '#A89880'
}

export default function MarketBanner() {
    const [macroData, setMacroData] = useState(null)
    const [loading, setLoading]     = useState(true)
    const [collapsed, setCollapsed] = useState(() => {
        try { return localStorage.getItem('macro_banner_collapsed') === 'true' }
        catch (_) { return false }
    })

    useEffect(() => {
        getMacroData()
            .then(setMacroData)
            .catch(() => {})
            .finally(() => setLoading(false))
    }, [])

    const toggleCollapsed = () => {
        setCollapsed(prev => {
            const next = !prev
            try { localStorage.setItem('macro_banner_collapsed', String(next)) } catch (_) {}
            return next
        })
    }

    const spy     = macroData?.indices?.SPY
    const qqq     = macroData?.indices?.QQQ
    const vix     = macroData?.indices?.['^VIX']
    const dom     = macroData?.dominant_sector

    if (collapsed) {
        return (
            <div className="mb-bar mb-collapsed" onClick={toggleCollapsed} title="Expand market overview">
                <span className="mb-collapsed-label">Market Overview</span>
                <span className="mb-toggle">˅</span>
            </div>
        )
    }

    return (
        <div className="mb-bar mb-expanded">
            {loading ? (
                <div className="mb-shimmer-row">
                    <div className="mb-shimmer" style={{ width: 80 }} />
                    <div className="mb-shimmer" style={{ width: 80 }} />
                    <div className="mb-shimmer" style={{ width: 70 }} />
                    <div className="mb-shimmer" style={{ width: 110 }} />
                </div>
            ) : !macroData ? (
                <span className="mb-unavailable">Market data unavailable</span>
            ) : (
                <div className="mb-items">
                    {/* S&P 500 */}
                    {spy && (
                        <div className="mb-item">
                            <span className="mb-label">SPY</span>
                            <span className="mb-price">${spy.price?.toFixed(2)}</span>
                            <span className="mb-change" style={{ color: changeColor(spy.change_percent) }}>
                                {parseFloat(spy.change_percent) >= 0 ? '▲' : '▼'}{Math.abs(parseFloat(spy.change_percent)).toFixed(2)}%
                            </span>
                        </div>
                    )}
                    {/* Nasdaq */}
                    {qqq && (
                        <div className="mb-item">
                            <span className="mb-label">QQQ</span>
                            <span className="mb-price">${qqq.price?.toFixed(2)}</span>
                            <span className="mb-change" style={{ color: changeColor(qqq.change_percent) }}>
                                {parseFloat(qqq.change_percent) >= 0 ? '▲' : '▼'}{Math.abs(parseFloat(qqq.change_percent)).toFixed(2)}%
                            </span>
                        </div>
                    )}
                    {/* VIX */}
                    {vix && (
                        <div className="mb-item">
                            <span className="mb-label">VIX</span>
                            <span className="mb-price" style={{ color: vixColor(vix.label) }}>
                                {vix.price?.toFixed(1)}
                            </span>
                            <span className="mb-vix-label" style={{ color: vixColor(vix.label) }}>
                                ({vix.label})
                            </span>
                        </div>
                    )}
                    {/* Dominant Sector */}
                    {dom && (
                        <div className="mb-sector-chip" style={{ borderColor: dirColor(dom.direction), color: dirColor(dom.direction) }}>
                            {dom.sector_name} · {dom.symbol} · {dom.direction.charAt(0).toUpperCase() + dom.direction.slice(1)}
                        </div>
                    )}
                </div>
            )}
            <button className="mb-toggle-btn" onClick={toggleCollapsed} title="Collapse market overview" aria-label="Collapse market banner">
                ^
            </button>
        </div>
    )
}
