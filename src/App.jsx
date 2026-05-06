import { useState, useEffect } from 'react'
import { useUser, useAuth, Show, SignIn, UserButton } from '@clerk/react'
import { Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, ComposedChart } from 'recharts'
import { analyzeStock, setTokenGetter as setAnalyzeTokenGetter } from './services/api'
import { setTokenGetter as setTopStocksTokenGetter } from './services/topStocks'
import { setTokenGetter as setScreenerTokenGetter } from './services/screener'
import { getMacroData, setTokenGetter as setMacroTokenGetter } from './services/macro'
import CandlestickLoader from './components/CandlestickLoader'
import TopStocks from './components/TopStocks'
import Portfolio from './components/Portfolio'
import Budget from './components/Budget'
import CompareView from './components/CompareView'
import MarketBanner from './components/MarketBanner'
import MacroDashboard from './components/MacroDashboard'
import './App.css'

const indicatorDefs = {
    rsi: {
      title: 'RSI — Relative Strength Index',
      desc: 'Measures how overbought or oversold a stock is on a 0–100 scale. Above 70 = likely overbought (due for a pullback). Below 30 = likely oversold (potential bounce). The sweet spot for buying is often 40–60.',
    },
    macd: {
      title: 'MACD — Moving Avg Convergence Divergence',
      desc: 'Tracks momentum by comparing two moving averages. When the MACD line crosses above its signal line, it\'s a bullish sign. When it crosses below, it\'s bearish. Think of it as a momentum speedometer.',
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

const SECTOR_ETF_MAP = {
    'Technology':             'XLK',
    'Financial Services':     'XLF',
    'Energy':                 'XLE',
    'Healthcare':             'XLV',
    'Industrials':            'XLI',
    'Consumer Cyclical':      'XLY',
    'Consumer Defensive':     'XLP',
    'Real Estate':            'XLRE',
    'Basic Materials':        'XLB',
    'Utilities':              'XLU',
    'Communication Services': 'XLC',
}

function getSectorContextWarning(stockData, macroData) {
    if (!stockData?.sector || !macroData?.sectors) return null
    const etfSymbol = SECTOR_ETF_MAP[stockData.sector]
    if (!etfSymbol) return null
    const etf = macroData.sectors[etfSymbol]
    if (!etf) return null
    const parts = []
    const rsi = etf.indicators?.rsi
    if (rsi != null) {
        if (rsi > 70) parts.push(`RSI ${rsi.toFixed(0)}, Overbought`)
        else if (rsi < 30) parts.push(`RSI ${rsi.toFixed(0)}, Oversold`)
    }
    if (etf.direction === 'bearish') parts.push(`sector trending ${etf.rating || etf.prediction}`)
    if (parts.length === 0) return null
    return `${stockData.sector} (${etfSymbol}): ${parts.join(', ')} ⚠`
}

function App() {
  const { user } = useUser()
  const { getToken } = useAuth()
  const [symbol, setSymbol] = useState('')
  const [flippedCards, setFlippedCards] = useState(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [currentView, setCurrentView] = useState('market') // 'analyze', 'topstocks', 'portfolio', 'budget', or 'market'
  const [macroData, setMacroData] = useState(null)
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareData, setCompareData] = useState({}) // keyed by symbol

  // Wire token getter into services
  useEffect(() => {
    const getter = () => getToken()
    setAnalyzeTokenGetter(getter)
    setTopStocksTokenGetter(getter)
    setScreenerTokenGetter(getter)
    setMacroTokenGetter(getter)
  }, [getToken])

  // Pre-fetch macro data on mount so sector warnings are ready when user analyzes a stock
  useEffect(() => {
    getMacroData().then(setMacroData).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!symbol.trim()) return

    setLoading(true)
    setError(null)

    try {
      const result = await analyzeStock(symbol.trim())
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleQuickSearch = (sym) => {
    setSymbol(sym)
    setLoading(true)
    setError(null)
    setCurrentView('analyze')

    analyzeStock(sym)
      .then(result => setData(result))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  const handleAddCompare = async (sym) => {
    if (!sym || compareData[sym]) return
    try {
      const result = await analyzeStock(sym)
      setCompareData(prev => ({ ...prev, [sym]: result }))
    } catch (err) {
      console.error('Compare fetch failed:', err.message)
    }
  }

  const handleRemoveCompare = (sym) => {
    setCompareData(prev => {
      const next = { ...prev }
      delete next[sym]
      return next
    })
  }

  const handleRetry = () => handleQuickSearch(symbol)

  // Format large numbers
  const formatNumber = (num) => {
    if (!num) return 'N/A'
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`
    return num.toLocaleString()
  }

  // Prepare chart data
  const getChartData = () => {
    if (!data?.chart_data?.dates) return []
    return data.chart_data.dates.map((date, i) => ({
      date: date.slice(5), // MM-DD format
      price: data.chart_data.closes[i],
      sma: data.chart_data.sma_20[i],
      upper: data.chart_data.bollinger_upper[i],
      lower: data.chart_data.bollinger_lower[i],
    })).reverse()
  }

  // Toggle flip state for indicator cards
  const toggleFlip = (key) => {
    setFlippedCards(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  return (
    <>
      <Show when="signed-out">
        <div className="auth-page">
          <div className="auth-content">
            <div className="auth-header">
              <h1 className="auth-title">Opes</h1>
              <p className="auth-subtitle">AI-Powered Stock Analysis</p>
            </div>
            <SignIn
              appearance={{
                elements: {
                  rootBox: "w-full",
                  card: "shadow-lg rounded-xl border border-[rgba(201,168,76,0.2)] bg-[#0f0e0b]"
                }
              }}
            />
          </div>
          <div className="auth-bg-decoration">
            <div className="bg-circle bg-circle-1"></div>
            <div className="bg-circle bg-circle-2"></div>
            <div className="bg-circle bg-circle-3"></div>
          </div>
        </div>
      </Show>
      <Show when="signed-in">
        <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-logo">
          <span className="gradient-text">Opes</span>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-tab ${currentView === 'analyze' ? 'active' : ''}`}
            onClick={() => setCurrentView('analyze')}
          >
            Analyze
          </button>
          <button
            className={`nav-tab ${currentView === 'topstocks' ? 'active' : ''}`}
            onClick={() => setCurrentView('topstocks')}
          >
            Top 5 Buys
          </button>
          <button
            className={`nav-tab ${currentView === 'portfolio' ? 'active' : ''}`}
            onClick={() => setCurrentView('portfolio')}
          >
            Portfolio
          </button>
          <button
            className={`nav-tab ${currentView === 'budget' ? 'active' : ''}`}
            onClick={() => setCurrentView('budget')}
          >
            Budget
          </button>
          <button
            className={`nav-tab ${currentView === 'market' ? 'active' : ''}`}
            onClick={() => setCurrentView('market')}
          >
            Market
          </button>
        </nav>

        <div className="header-user">
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      {/* Persistent market context strip — visible across all views */}
      <MarketBanner />

      {/* Market View */}
      {currentView === 'market' && (
        <MacroDashboard />
      )}

      {/* Top Stocks View */}
      {currentView === 'topstocks' && (
        <TopStocks onStockSelect={handleQuickSearch} />
      )}

      {/* Portfolio View */}
      {currentView === 'portfolio' && (
        <Portfolio onStockSelect={handleQuickSearch} />
      )}

      {/* Budget View */}
      {currentView === 'budget' && (
        <Budget />
      )}

      {/* Analyze View */}
      {currentView === 'analyze' && (
        <>
          {/* Search */}
          <section className="search-section">
            <form className="search-form" onSubmit={handleSubmit}>
              <input
                type="text"
                className="search-input"
                placeholder="Enter stock symbol (e.g., AAPL)"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              />
              <button type="submit" className="btn-primary search-btn" disabled={loading}>
                {loading ? 'Analyzing...' : 'Analyze'}
              </button>
            </form>
          </section>

          {/* Loading State */}
          {loading && (
            <CandlestickLoader message={`Analyzing ${symbol}\u2026 fetching data, calculating indicators & running ML model`} />
          )}

          {/* Error State */}
          {error && (
            <div className="error-container">
              <div className="error-icon">⚠</div>
              <h3 className="error-title">Analysis failed</h3>
              <p className="error-message">{error}</p>
              <button className="btn-primary error-retry-btn" onClick={handleRetry}>
                Try Again
              </button>
            </div>
          )}

          {/* Welcome State */}
          {!loading && !error && !data && (
            <div className="welcome-container">
              <div className="welcome-wordmark">Opes</div>
              <h2 className="welcome-title">Enter a symbol to begin</h2>
              <p className="welcome-subtitle">AI-powered · Technical indicators · ML predictions</p>
              <div className="popular-stocks">
                <button className="stock-chip" onClick={() => handleQuickSearch('AAPL')}>AAPL</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('GOOGL')}>GOOGL</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('MSFT')}>MSFT</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('TSLA')}>TSLA</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('AMZN')}>AMZN</button>
              </div>
              <p className="welcome-stats">Updated daily · ML-powered · 18-stock watchlist</p>
            </div>
          )}

          {/* Results */}
          {!loading && !error && data && (
            <div className="results-container">
              {/* Stock Header */}
              <div className="stock-header glass">
                <div className="stock-info">
                  <h2>
                    <span className="stock-symbol">{data.symbol}</span>
                    <span className="stock-name">{data.name}</span>
                  </h2>
                  <p className="stock-sector">{data.sector}</p>
                </div>
                <div className="stock-price">
                  <div className="price">${data.quote?.price?.toFixed(2) || 'N/A'}</div>
                  <div className={`price-change ${data.quote?.change >= 0 ? 'positive' : 'negative'}`}>
                    {data.quote?.change >= 0 ? '▲' : '▼'} ${Math.abs(data.quote?.change || 0).toFixed(2)} ({data.quote?.change_percent}%)
                  </div>
                  <button
                    className="btn-compare"
                    onClick={() => setCompareOpen(o => !o)}
                    title="Compare with other stocks"
                  >
                    {compareOpen ? 'Close Compare' : 'Compare'}
                  </button>
                </div>
              </div>

              {/* Earnings Banner */}
              {data.earnings && (
                <div className={`earnings-banner ${data.earnings.days_until <= 7 ? 'earnings-warning' : 'earnings-info'}`}>
                  {data.earnings.days_until <= 7
                    ? `⚠ Earnings in ${data.earnings.days_until} day${data.earnings.days_until !== 1 ? 's' : ''} (${data.earnings.date}) — high volatility risk.`
                    : `Earnings: ${data.earnings.date} (in ${data.earnings.days_until} days)`
                  }
                </div>
              )}

              {/* Sector Context Warning — sourced from macro data */}
              {(() => {
                const w = getSectorContextWarning(data, macroData)
                return w ? (
                  <div className="earnings-banner earnings-info">
                    Sector context — {w}
                  </div>
                ) : null
              })()}

              {/* Technical Indicators Grid */}
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
                        <div className="indicator-value">{data.indicators?.rsi?.toFixed(1) || 'N/A'}</div>
                        <div className={`indicator-signal signal-${data.signals?.rsi?.toLowerCase().replace(' ', '-')}`}>
                          {data.signals?.rsi}
                        </div>
                        {data.indicators?.rsi && (
                          <div className="rsi-gauge-wrapper">
                            <div className="rsi-gauge">
                              <div className="rsi-marker" style={{ left: `${data.indicators.rsi}%` }}></div>
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
                        <div className="indicator-value">{data.indicators?.macd?.toFixed(4) || 'N/A'}</div>
                        <div className={`indicator-signal signal-${data.signals?.macd?.toLowerCase()}`}>
                          {data.signals?.macd}
                        </div>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                          Signal: {data.indicators?.macd_signal?.toFixed(4) || 'N/A'}
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
                        <div className="indicator-value">
                          {data.signals?.trend?.toLowerCase().includes('up') ? '↑ ' : data.signals?.trend?.toLowerCase().includes('down') ? '↓ ' : '→ '}
                          {data.signals?.trend || 'N/A'}
                        </div>
                        <div className={`indicator-signal signal-${data.signals?.trend?.toLowerCase().includes('up') ? 'bullish' : data.signals?.trend?.toLowerCase().includes('down') ? 'bearish' : 'neutral'}`}>
                          {data.signals?.trend?.toLowerCase().includes('up') ? 'Bullish' : data.signals?.trend?.toLowerCase().includes('down') ? 'Bearish' : 'Neutral'}
                        </div>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                          SMA20: ${data.indicators?.sma_20?.toFixed(2)} | SMA50: ${data.indicators?.sma_50?.toFixed(2)}
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
                        <div className="indicator-value">{data.signals?.bollinger}</div>
                        <div className={`indicator-signal signal-${data.signals?.bollinger?.toLowerCase().replace(/ /g, '-')}`}>
                          {data.signals?.bollinger}
                        </div>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                          Upper: ${data.indicators?.bollinger_upper?.toFixed(2)} | Lower: ${data.indicators?.bollinger_lower?.toFixed(2)}
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

              {/* Chart and Prediction */}
              <div className="chart-prediction-grid">
                {/* Price Chart */}
                <div className="card chart-card">
                  <h3>{data.symbol} — 1 Year Price History</h3>
                  <div className="chart-legend">
                    <span className="legend-item"><span className="legend-swatch legend-price"></span>Price</span>
                    <span className="legend-item"><span className="legend-swatch legend-sma"></span>SMA 20</span>
                    <span className="legend-item"><span className="legend-swatch legend-upper-bb"></span>Upper BB</span>
                    <span className="legend-item"><span className="legend-swatch legend-lower-bb"></span>Lower BB</span>
                  </div>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={getChartData()} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <defs>
                          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor="#C9A84C" stopOpacity={0.28} />
                            <stop offset="95%" stopColor="#C9A84C" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(201,168,76,0.08)" />
                        <XAxis dataKey="date" stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }} />
                        <YAxis stroke="#5C5248" fontSize={11} tick={{ fill: '#5C5248' }} domain={['auto', 'auto']} width={52} />
                        <Tooltip
                          contentStyle={{
                            background: '#1a1a1a',
                            border: '1px solid rgba(201,168,76,0.22)',
                            borderRadius: '10px',
                            color: '#F0EAD6',
                            fontSize: '0.8125rem',
                          }}
                          labelStyle={{ color: '#A89880', marginBottom: '4px' }}
                        />
                        <Area type="monotone" dataKey="upper" stroke="none" fill="rgba(255,96,88,0.06)" />
                        <Area type="monotone" dataKey="lower" stroke="none" fill="#080808" />
                        <Line type="monotone" dataKey="upper" stroke="#FF6058" strokeDasharray="5 5" dot={false} strokeWidth={1} opacity={0.7} />
                        <Line type="monotone" dataKey="lower" stroke="#34D27A" strokeDasharray="5 5" dot={false} strokeWidth={1} opacity={0.7} />
                        <Line type="monotone" dataKey="sma" stroke="#E2C27A" dot={false} strokeWidth={1.5} opacity={0.85} />
                        <Area type="monotone" dataKey="price" stroke="#C9A84C" fill="url(#priceGradient)" strokeWidth={2} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* AI Prediction — 4-Pillar Rating */}
                <div className={`card prediction-card ${data.prediction?.direction === 'bullish' ? 'bullish-glow' : data.prediction?.direction === 'bearish' ? 'bearish-glow' : ''}`}>
                  <h3>4-Pillar Rating</h3>

                  {/* Composite rating label */}
                  <div className={`prediction-title ${data.prediction?.direction}`}>
                    {data.prediction?.rating || data.prediction?.prediction}
                  </div>

                  {/* Quality Score bar */}
                  {data.prediction?.quality_score != null && (
                    <div className="confidence-meter">
                      <div className="confidence-label">
                        <span>Quality Score</span>
                        <span>{data.prediction.quality_score.toFixed(1)} / 100</span>
                      </div>
                      <div className="confidence-bar">
                        <div
                          className={`confidence-fill ${data.prediction.quality_score > 70 ? 'high' : data.prediction.quality_score > 50 ? 'medium' : 'low'}`}
                          style={{ width: `${data.prediction.quality_score}%` }}
                        ></div>
                      </div>
                    </div>
                  )}

                  {/* Sub-score breakdown */}
                  <div className="pillar-breakdown">
                    <div className="pillar-row">
                      <span className="pillar-label">AI Confidence</span>
                      <div className="pillar-bar-track">
                        <div className={`pillar-bar-fill ${(data.prediction?.confidence || 0) > 70 ? 'high' : (data.prediction?.confidence || 0) > 50 ? 'medium' : 'low'}`}
                             style={{ width: `${data.prediction?.confidence || 0}%` }}></div>
                      </div>
                      <span className="pillar-value">{data.prediction?.confidence}%</span>
                    </div>
                    {data.prediction?.fund_score != null && (
                      <div className="pillar-row">
                        <span className="pillar-label">Fundamentals</span>
                        <div className="pillar-bar-track">
                          <div className={`pillar-bar-fill ${data.prediction.fund_score > 70 ? 'high' : data.prediction.fund_score > 50 ? 'medium' : 'low'}`}
                               style={{ width: `${data.prediction.fund_score}%` }}></div>
                        </div>
                        <span className="pillar-value">{data.prediction.fund_score.toFixed(1)}</span>
                      </div>
                    )}
                    <div className="pillar-row">
                      <span className="pillar-label">Momentum</span>
                      <div className="pillar-bar-track">
                        <div className={`pillar-bar-fill ${(data.prediction?.momentum_score || 0) > 70 ? 'high' : (data.prediction?.momentum_score || 0) > 50 ? 'medium' : 'low'}`}
                             style={{ width: `${data.prediction?.momentum_score || 0}%` }}></div>
                      </div>
                      <span className="pillar-value">{data.prediction?.momentum_score?.toFixed(1)}</span>
                    </div>
                    {data.prediction?.news_score != null && (
                      <div className="pillar-row">
                        <span className="pillar-label">News Sentiment</span>
                        <div className="pillar-bar-track">
                          <div className={`pillar-bar-fill ${data.prediction.news_score > 70 ? 'high' : data.prediction.news_score > 50 ? 'medium' : 'low'}`}
                               style={{ width: `${data.prediction.news_score}%` }}></div>
                        </div>
                        <span className="pillar-value">{data.news?.label || data.prediction.news_score.toFixed(1)}</span>
                      </div>
                    )}
                  </div>

                  {/* News Headlines */}
                  {data.news?.headlines?.length > 0 && (
                    <div className="news-headlines">
                      <h4 className="key-factors-title">Recent News</h4>
                      <ul className="news-list">
                        {data.news.headlines.map((h, i) => (
                          <li key={i} className="news-item">{h}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {data.prediction?.key_factors && (
                    (data.prediction.key_factors.bullish?.length > 0 || data.prediction.key_factors.bearish?.length > 0) && (
                      <div className="key-factors">
                        <h4 className="key-factors-title">Key Drivers</h4>
                        <ul className="key-factors-list">
                          {data.prediction.key_factors.bullish.map((f, i) => (
                            <li key={`b${i}`} className="factor bullish-factor">{f}</li>
                          ))}
                          {data.prediction.key_factors.bearish.map((f, i) => (
                            <li key={`r${i}`} className="factor bearish-factor">{f}</li>
                          ))}
                        </ul>
                      </div>
                    )
                  )}
                  <p className="model-accuracy">Model Training Accuracy: {data.prediction?.model_accuracy}%</p>
                </div>

              </div>

              {/* Fundamentals */}
              <div className="card fundamentals-card">
                <h3>Fundamentals</h3>
                <div className="fundamentals-grid">
                  <div className="fundamental-item">
                    <div className="fundamental-label">P/E Ratio</div>
                    <div className="fundamental-value">{data.fundamentals?.pe_ratio?.toFixed(2) || 'N/A'}</div>
                  </div>
                  <div className="fundamental-item">
                    <div className="fundamental-label">EPS</div>
                    <div className="fundamental-value">${data.fundamentals?.eps?.toFixed(2) || 'N/A'}</div>
                  </div>
                  <div className="fundamental-item">
                    <div className="fundamental-label">ROE</div>
                    <div className="fundamental-value">{data.fundamentals?.roe ? (data.fundamentals.roe * 100).toFixed(1) + '%' : 'N/A'}</div>
                  </div>
                  <div className="fundamental-item">
                    <div className="fundamental-label">Market Cap</div>
                    <div className="fundamental-value">{formatNumber(data.fundamentals?.market_cap)}</div>
                  </div>
                  <div className="fundamental-item">
                    <div className="fundamental-label">52W High</div>
                    <div className="fundamental-value">${data.fundamentals?.['52_week_high']?.toFixed(2) || 'N/A'}</div>
                  </div>
                  <div className="fundamental-item">
                    <div className="fundamental-label">52W Low</div>
                    <div className="fundamental-value">${data.fundamentals?.['52_week_low']?.toFixed(2) || 'N/A'}</div>
                  </div>
                </div>
              </div>

              {/* Signal History */}
              {data.signal_history?.length > 0 && (
                <div className="card signal-history-card">
                  <h3>Signal History</h3>
                  <p className="signal-history-subtitle">
                    How past ML signals performed over the following 30 days — each signal is trained on only data available at that date.
                  </p>

                  {data.signal_stats?.length > 0 && (
                    <div className="signal-stats-grid">
                      {data.signal_stats.map((stat, i) => (
                        <div key={i} className={`signal-stat-item signal-stat-${stat.direction}`}>
                          <div className="signal-stat-label">{stat.signal}</div>
                          <div className={`signal-stat-return ${stat.avg_return_pct_30d >= 0 ? 'positive' : 'negative'}`}>
                            {stat.avg_return_pct_30d >= 0 ? '+' : ''}{stat.avg_return_pct_30d.toFixed(1)}%
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
                          <th>30d Return</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.signal_history.map((s, i) => (
                          <tr key={i}>
                            <td>{s.date}</td>
                            <td>
                              <span className={`signal-badge signal-badge-${s.direction}`}>{s.signal}</span>
                            </td>
                            <td>${s.price_at_signal.toFixed(2)}</td>
                            <td className={s.actual_return_pct_30d >= 0 ? 'positive' : 'negative'}>
                              {s.actual_return_pct_30d >= 0 ? '+' : ''}{s.actual_return_pct_30d.toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <p className="signal-history-disclaimer">
                    Each signal uses only data available at that date — no future information. Past performance does not guarantee future results.
                  </p>
                </div>
              )}

              {/* Compare Panel */}
              {compareOpen && (
                <CompareView
                  primaryData={data}
                  compareData={compareData}
                  onAdd={handleAddCompare}
                  onRemove={handleRemoveCompare}
                  formatNumber={formatNumber}
                />
              )}
            </div>
          )}
        </>
      )}
        </div>
      </Show>
    </>
  )
}

export default App

