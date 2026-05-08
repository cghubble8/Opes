import { useState } from 'react'

const indicatorDefs = {
  rsi: {
    title: 'RSI — Relative Strength Index',
    desc: 'Measures how overbought or oversold a stock is on a 0–100 scale. Above 70 = likely overbought (due for a pullback). Below 30 = likely oversold (potential bounce). The sweet spot for buying is often 40–60.',
  },
  macd: {
    title: 'MACD — Moving Avg Convergence Divergence',
    desc: "Tracks momentum by comparing two moving averages. When the MACD line crosses above its signal line, it's a bullish sign. When it crosses below, it's bearish. Think of it as a momentum speedometer.",
  },
  trend: {
    title: 'Moving Averages & Trend',
    desc: 'Compares the 20-day and 50-day average prices to identify the trend direction. Price above both averages = uptrend. Below both = downtrend. Traders use these as dynamic support and resistance levels.',
  },
  bollinger: {
    title: 'Bollinger Bands',
    desc: 'Two bands plotted around a 20-day moving average. When price touches the upper band, it may be overextended. Near the lower band, it may be undervalued. A squeeze (bands narrowing) often signals a big move ahead.',
  },
}

export default function IndicatorsGrid({ indicators, signals }) {
  const [flippedCards, setFlippedCards] = useState(new Set())

  const toggleFlip = (key) => {
    setFlippedCards(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const trendDir = signals?.trend?.toLowerCase()
  const trendClass = trendDir?.includes('up') ? 'bullish' : trendDir?.includes('down') ? 'bearish' : 'neutral'
  const trendArrow = trendDir?.includes('up') ? '↑ ' : trendDir?.includes('down') ? '↓ ' : '→ '

  return (
    <div className="indicators-grid">
      {/* RSI */}
      <div
        className={`flip-card-wrapper ${flippedCards.has('rsi') ? 'flipped' : ''}`}
        onClick={() => toggleFlip('rsi')}
        role="button"
        tabIndex={0}
        aria-label="RSI indicator — tap to learn more"
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleFlip('rsi')}
      >
        <div className="flip-card-inner">
          <div className="flip-card-front">
            <div className="card indicator-card">
              <span className="flip-hint">ℹ</span>
              <h3>RSI (14)</h3>
              <div className="indicator-value">{indicators?.rsi?.toFixed(1) || 'N/A'}</div>
              <div className={`indicator-signal signal-${signals?.rsi?.toLowerCase().replace(' ', '-')}`}>
                {signals?.rsi}
              </div>
              {indicators?.rsi && (
                <div className="rsi-gauge-wrapper">
                  <div className="rsi-gauge">
                    <div className="rsi-marker" style={{ left: `${indicators.rsi}%` }}></div>
                    <div className="rsi-tick" style={{ left: '30%' }}></div>
                    <div className="rsi-tick" style={{ left: '70%' }}></div>
                  </div>
                  <div className="rsi-gauge-labels">
                    <span>Oversold (30)</span>
                    <span>Neutral</span>
                    <span>Overbought (70)</span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="flip-card-back">
            <div className="flip-card-back-icon">RSI</div>
            <div className="flip-card-back-title">{indicatorDefs.rsi.title}</div>
            <p className="flip-card-back-desc">{indicatorDefs.rsi.desc}</p>
          </div>
        </div>
      </div>

      {/* MACD */}
      <div
        className={`flip-card-wrapper ${flippedCards.has('macd') ? 'flipped' : ''}`}
        onClick={() => toggleFlip('macd')}
        role="button"
        tabIndex={0}
        aria-label="MACD indicator — tap to learn more"
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleFlip('macd')}
      >
        <div className="flip-card-inner">
          <div className="flip-card-front">
            <div className="card indicator-card">
              <span className="flip-hint">ℹ</span>
              <h3>MACD</h3>
              <div className="indicator-value">{indicators?.macd?.toFixed(4) || 'N/A'}</div>
              <div className={`indicator-signal signal-${signals?.macd?.toLowerCase()}`}>
                {signals?.macd}
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                Signal: {indicators?.macd_signal?.toFixed(4) || 'N/A'}
              </p>
            </div>
          </div>
          <div className="flip-card-back">
            <div className="flip-card-back-icon">MACD</div>
            <div className="flip-card-back-title">{indicatorDefs.macd.title}</div>
            <p className="flip-card-back-desc">{indicatorDefs.macd.desc}</p>
          </div>
        </div>
      </div>

      {/* Moving Averages */}
      <div
        className={`flip-card-wrapper ${flippedCards.has('trend') ? 'flipped' : ''}`}
        onClick={() => toggleFlip('trend')}
        role="button"
        tabIndex={0}
        aria-label="Moving Averages indicator — tap to learn more"
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleFlip('trend')}
      >
        <div className="flip-card-inner">
          <div className="flip-card-front">
            <div className="card indicator-card">
              <span className="flip-hint">ℹ</span>
              <h3>Moving Averages</h3>
              <div className="indicator-value">{trendArrow}{signals?.trend || 'N/A'}</div>
              <div className={`indicator-signal signal-${trendClass}`}>
                {trendDir?.includes('up') ? 'Bullish' : trendDir?.includes('down') ? 'Bearish' : 'Neutral'}
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                SMA20: ${indicators?.sma_20?.toFixed(2)} | SMA50: ${indicators?.sma_50?.toFixed(2)}
              </p>
            </div>
          </div>
          <div className="flip-card-back">
            <div className="flip-card-back-icon">MA</div>
            <div className="flip-card-back-title">{indicatorDefs.trend.title}</div>
            <p className="flip-card-back-desc">{indicatorDefs.trend.desc}</p>
          </div>
        </div>
      </div>

      {/* Bollinger Bands */}
      <div
        className={`flip-card-wrapper ${flippedCards.has('bollinger') ? 'flipped' : ''}`}
        onClick={() => toggleFlip('bollinger')}
        role="button"
        tabIndex={0}
        aria-label="Bollinger Bands indicator — tap to learn more"
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleFlip('bollinger')}
      >
        <div className="flip-card-inner">
          <div className="flip-card-front">
            <div className="card indicator-card">
              <span className="flip-hint">ℹ</span>
              <h3>Bollinger Bands</h3>
              <div className="indicator-value">{signals?.bollinger}</div>
              <div className={`indicator-signal signal-${signals?.bollinger?.toLowerCase().replace(/ /g, '-')}`}>
                {signals?.bollinger}
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                Upper: ${indicators?.bollinger_upper?.toFixed(2)} | Lower: ${indicators?.bollinger_lower?.toFixed(2)}
              </p>
            </div>
          </div>
          <div className="flip-card-back">
            <div className="flip-card-back-icon">BB</div>
            <div className="flip-card-back-title">{indicatorDefs.bollinger.title}</div>
            <p className="flip-card-back-desc">{indicatorDefs.bollinger.desc}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
