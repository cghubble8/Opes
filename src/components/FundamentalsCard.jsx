function formatNumber(num) {
  if (!num) return 'N/A'
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`
  if (num >= 1e9)  return `$${(num / 1e9).toFixed(2)}B`
  if (num >= 1e6)  return `$${(num / 1e6).toFixed(2)}M`
  return num.toLocaleString()
}

export default function FundamentalsCard({ fundamentals }) {
  const f = fundamentals || {}

  return (
    <div className="card fundamentals-card">
      <h3>Fundamentals</h3>
      <div className="fundamentals-grid">
        <div className="fundamental-item">
          <div className="fundamental-label">P/E Ratio</div>
          <div className="fundamental-value">{f.pe_ratio?.toFixed(2) || 'N/A'}</div>
        </div>
        <div className="fundamental-item">
          <div className="fundamental-label">EPS</div>
          <div className="fundamental-value">${f.eps?.toFixed(2) || 'N/A'}</div>
        </div>
        <div className="fundamental-item">
          <div className="fundamental-label">ROE</div>
          <div className="fundamental-value">{f.roe ? (f.roe * 100).toFixed(1) + '%' : 'N/A'}</div>
        </div>
        <div className="fundamental-item">
          <div className="fundamental-label">Market Cap</div>
          <div className="fundamental-value">{formatNumber(f.market_cap)}</div>
        </div>
        <div className="fundamental-item">
          <div className="fundamental-label">52W High</div>
          <div className="fundamental-value">${f['52_week_high']?.toFixed(2) || 'N/A'}</div>
        </div>
        <div className="fundamental-item">
          <div className="fundamental-label">52W Low</div>
          <div className="fundamental-value">${f['52_week_low']?.toFixed(2) || 'N/A'}</div>
        </div>
      </div>
    </div>
  )
}
