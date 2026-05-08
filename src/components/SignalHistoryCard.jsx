import './SignalHistoryCard.css'

export default function SignalHistoryCard({ signalHistory, signalStats }) {
  if (!signalHistory?.length) return null

  return (
    <div className="card signal-history-card">
      <h3>Signal History</h3>
      <p className="signal-history-subtitle">
        How past ML signals performed over the following 6 months — each signal is trained on only data available at that date.
      </p>

      {signalStats?.length > 0 && (
        <div className="signal-stats-grid">
          {signalStats.map((stat, i) => (
            <div key={i} className={`signal-stat-item signal-stat-${stat.direction}`}>
              <div className="signal-stat-label">{stat.signal}</div>
              <div className={`signal-stat-return ${stat.avg_return_pct >= 0 ? 'positive' : 'negative'}`}>
                {stat.avg_return_pct >= 0 ? '+' : ''}{stat.avg_return_pct.toFixed(1)}%
              </div>
              <div className="signal-stat-count">avg · {stat.count} signal{stat.count !== 1 ? 's' : ''}</div>
            </div>
          ))}
        </div>
      )}

      <div className="signal-history-table-wrapper">
        <table className="signal-history-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Signal</th>
              <th>Price</th>
              <th>6-Month Return</th>
            </tr>
          </thead>
          <tbody>
            {signalHistory.map((s, i) => (
              <tr key={i}>
                <td>{s.date}</td>
                <td>
                  <span className={`signal-badge signal-badge-${s.direction}`}>{s.signal}</span>
                </td>
                <td>${s.price_at_signal.toFixed(2)}</td>
                <td className={s.actual_return_pct >= 0 ? 'positive' : 'negative'}>
                  {s.actual_return_pct >= 0 ? '+' : ''}{s.actual_return_pct.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="signal-history-disclaimer">
        Each signal uses only data available at that date — no future information. Returns shown are 6-month forward performance. Past performance does not guarantee future results.
      </p>
    </div>
  )
}
