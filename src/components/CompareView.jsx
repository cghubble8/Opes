import { useState } from 'react'
import './CompareView.css'

const METRICS = [
  { key: 'quality_score',  label: 'Quality Score', get: d => d.prediction?.quality_score, fmt: v => `${v?.toFixed(1)} / 100`, higher: true },
  { key: 'direction',      label: 'Direction',      get: d => d.prediction?.direction,    fmt: v => directionLabel(v), higher: null },
  { key: 'confidence',     label: 'AI Confidence',  get: d => d.prediction?.confidence,   fmt: v => `${v}%`, higher: true },
  { key: 'fund_score',     label: 'Fundamentals',   get: d => d.prediction?.fund_score,   fmt: v => v?.toFixed(1) ?? 'N/A', higher: true },
  { key: 'momentum_score', label: 'Momentum',       get: d => d.prediction?.momentum_score, fmt: v => v?.toFixed(1) ?? 'N/A', higher: true },
  { key: 'news_sentiment', label: 'News Sentiment', get: d => d.news?.label,              fmt: v => v ?? 'N/A', higher: null },
  { key: 'rsi',            label: 'RSI (14)',        get: d => d.indicators?.rsi,          fmt: v => v?.toFixed(1) ?? 'N/A', higher: null },
  { key: 'macd',           label: 'MACD Signal',    get: d => d.signals?.macd,            fmt: v => v ?? 'N/A', higher: null },
  { key: 'pe_ratio',       label: 'P/E Ratio',      get: d => d.fundamentals?.pe_ratio,   fmt: v => v?.toFixed(1) ?? 'N/A', higher: false },
  { key: 'roe',            label: 'ROE',             get: d => d.fundamentals?.roe,        fmt: v => v != null ? `${(v * 100).toFixed(1)}%` : 'N/A', higher: true },
]

function directionLabel(dir) {
  if (dir === 'bullish')  return '▲ Bullish'
  if (dir === 'bearish')  return '▼ Bearish'
  return '● Neutral'
}

function directionClass(dir) {
  if (dir === 'bullish') return 'compare-bullish'
  if (dir === 'bearish') return 'compare-bearish'
  return ''
}

function winner(allData, metric) {
  // Returns the symbol with the best value for this metric
  if (metric.higher === null) return null
  let best = null, bestVal = null
  for (const [sym, d] of Object.entries(allData)) {
    const val = metric.get(d)
    if (val == null) continue
    if (
      bestVal === null ||
      (metric.higher && val > bestVal) ||
      (!metric.higher && val < bestVal)
    ) {
      best = sym
      bestVal = val
    }
  }
  return best
}

export default function CompareView({ primaryData, compareData, onAdd, onRemove, formatNumber }) {
  const [inputSym, setInputSym] = useState('')
  const [loadingSym, setLoadingSym] = useState(null)

  const allData = {
    [primaryData.symbol]: primaryData,
    ...compareData,
  }
  const symbols = Object.keys(allData)
  const canAddMore = symbols.length < 3

  const handleAdd = async () => {
    const sym = inputSym.trim().toUpperCase()
    if (!sym || allData[sym]) return
    setLoadingSym(sym)
    setInputSym('')
    await onAdd(sym)
    setLoadingSym(null)
  }

  return (
    <div className="card compare-card">
      <div className="compare-header">
        <h3>Stock Comparison</h3>
        {canAddMore && (
          <div className="compare-add-row">
            <input
              type="text"
              className="compare-input"
              placeholder="Add ticker (e.g. MSFT)"
              value={inputSym}
              onChange={e => setInputSym(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
              maxLength={10}
            />
            <button className="btn-primary compare-add-btn" onClick={handleAdd} disabled={!!loadingSym}>
              {loadingSym ? `Loading ${loadingSym}…` : 'Add'}
            </button>
          </div>
        )}
      </div>

      <div className="compare-table-wrapper">
        <table className="compare-table">
          <thead>
            <tr>
              <th className="compare-metric-col">Metric</th>
              {symbols.map(sym => (
                <th key={sym} className="compare-sym-col">
                  {sym}
                  {sym !== primaryData.symbol && (
                    <button
                      className="compare-remove-btn"
                      onClick={() => onRemove(sym)}
                      title={`Remove ${sym}`}
                    >×</button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map(metric => {
              const winnerSym = winner(allData, metric)
              return (
                <tr key={metric.key}>
                  <td className="compare-metric-label">{metric.label}</td>
                  {symbols.map(sym => {
                    const d = allData[sym]
                    const val = metric.get(d)
                    const isWinner = winnerSym === sym
                    const dirClass = metric.key === 'direction' ? directionClass(val) : ''
                    return (
                      <td
                        key={sym}
                        className={`compare-cell ${isWinner ? 'compare-winner' : ''} ${dirClass}`}
                      >
                        {metric.fmt(val)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
