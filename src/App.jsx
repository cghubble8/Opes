import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart, ComposedChart } from 'recharts'
import { analyzeStock, mockData } from './services/api'
import TopStocks from './components/TopStocks'
import Portfolio from './components/Portfolio'
import Login from './components/Login'
import './App.css'

function App() {
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [currentView, setCurrentView] = useState('analyze') // 'analyze', 'topstocks', or 'portfolio'
  const [user, setUser] = useState(null) // authentication state

  const handleLogin = (userData) => {
    setUser(userData)
  }

  const handleLogout = () => {
    setUser(null)
    setData(null)
    setSymbol('')
  }

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

  // Show login page if not authenticated
  if (!user) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-top">
          <h1>
            <span className="header-icon">📊</span>
            <span className="gradient-text">FinAssist</span>
          </h1>
          <button className="logout-btn" onClick={handleLogout}>
            Sign Out
          </button>
        </div>
        <p>Welcome back, {user.name}</p>

        {/* Navigation Tabs */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${currentView === 'analyze' ? 'active' : ''}`}
            onClick={() => setCurrentView('analyze')}
          >
            🔍 Analyze Stock
          </button>
          <button
            className={`nav-tab ${currentView === 'topstocks' ? 'active' : ''}`}
            onClick={() => setCurrentView('topstocks')}
          >
            🏆 Top 5 Buys
          </button>
          <button
            className={`nav-tab ${currentView === 'portfolio' ? 'active' : ''}`}
            onClick={() => setCurrentView('portfolio')}
          >
            💼 Portfolio
          </button>
        </nav>
      </header>

      {/* Top Stocks View */}
      {currentView === 'topstocks' && (
        <TopStocks onStockSelect={handleQuickSearch} />
      )}

      {/* Portfolio View */}
      {currentView === 'portfolio' && (
        <Portfolio onStockSelect={handleQuickSearch} />
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
                {loading ? '⏳' : '🔍'} Analyze
              </button>
            </form>
          </section>

          {/* Loading State */}
          {loading && (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p className="loading-text">Analyzing {symbol}... Fetching data, calculating indicators, and running ML model</p>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="error-container">
              <div className="error-icon">⚠️</div>
              <p className="error-message">{error}</p>
            </div>
          )}

          {/* Welcome State */}
          {!loading && !error && !data && (
            <div className="welcome-container">
              <div className="welcome-icon">📈</div>
              <h2 className="welcome-title">Enter a stock symbol to begin analysis</h2>
              <p className="welcome-subtitle">Get technical indicators, fundamentals, and AI predictions</p>
              <div className="popular-stocks">
                <button className="stock-chip" onClick={() => handleQuickSearch('AAPL')}>AAPL</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('GOOGL')}>GOOGL</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('MSFT')}>MSFT</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('TSLA')}>TSLA</button>
                <button className="stock-chip" onClick={() => handleQuickSearch('AMZN')}>AMZN</button>
              </div>
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
                </div>
              </div>

              {/* Technical Indicators Grid */}
              <div className="indicators-grid">
                {/* RSI */}
                <div className="card indicator-card">
                  <h3>📉 RSI (14)</h3>
                  <div className="indicator-value">{data.indicators?.rsi?.toFixed(1) || 'N/A'}</div>
                  <div className={`indicator-signal signal-${data.signals?.rsi?.toLowerCase().replace(' ', '-')}`}>
                    {data.signals?.rsi}
                  </div>
                  {data.indicators?.rsi && (
                    <div className="rsi-gauge">
                      <div className="rsi-marker" style={{ left: `${data.indicators.rsi}%` }}></div>
                    </div>
                  )}
                </div>

                {/* MACD */}
                <div className="card indicator-card">
                  <h3>📊 MACD</h3>
                  <div className="indicator-value">{data.indicators?.macd?.toFixed(4) || 'N/A'}</div>
                  <div className={`indicator-signal signal-${data.signals?.macd?.toLowerCase()}`}>
                    {data.signals?.macd}
                  </div>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                    Signal: {data.indicators?.macd_signal?.toFixed(4) || 'N/A'}
                  </p>
                </div>

                {/* Moving Averages */}
                <div className="card indicator-card">
                  <h3>📈 Moving Averages</h3>
                  <div className="indicator-value">{data.signals?.trend}</div>
                  <div className={`indicator-signal signal-${data.signals?.trend?.toLowerCase().replace(' ', '-')}`}>
                    {data.signals?.trend}
                  </div>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                    SMA20: ${data.indicators?.sma_20?.toFixed(2)} | SMA50: ${data.indicators?.sma_50?.toFixed(2)}
                  </p>
                </div>

                {/* Bollinger Bands */}
                <div className="card indicator-card">
                  <h3>🎯 Bollinger Bands</h3>
                  <div className="indicator-value">{data.signals?.bollinger}</div>
                  <div className={`indicator-signal signal-${data.signals?.bollinger?.toLowerCase().replace(/ /g, '-')}`}>
                    {data.signals?.bollinger}
                  </div>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '8px' }}>
                    Upper: ${data.indicators?.bollinger_upper?.toFixed(2)} | Lower: ${data.indicators?.bollinger_lower?.toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Chart and Prediction */}
              <div className="chart-prediction-grid">
                {/* Price Chart */}
                <div className="card chart-card">
                  <h3>📈 Price Chart with Bollinger Bands</h3>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={getChartData()} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <defs>
                          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis dataKey="date" stroke="#6b6b7a" fontSize={12} />
                        <YAxis stroke="#6b6b7a" fontSize={12} domain={['auto', 'auto']} />
                        <Tooltip
                          contentStyle={{
                            background: '#1a1a25',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '8px'
                          }}
                        />
                        <Area type="monotone" dataKey="upper" stroke="none" fill="rgba(239,68,68,0.1)" />
                        <Area type="monotone" dataKey="lower" stroke="none" fill="#0a0a0f" />
                        <Line type="monotone" dataKey="upper" stroke="#ef4444" strokeDasharray="5 5" dot={false} strokeWidth={1} />
                        <Line type="monotone" dataKey="lower" stroke="#10b981" strokeDasharray="5 5" dot={false} strokeWidth={1} />
                        <Line type="monotone" dataKey="sma" stroke="#f59e0b" dot={false} strokeWidth={2} />
                        <Area type="monotone" dataKey="price" stroke="#6366f1" fill="url(#priceGradient)" strokeWidth={2} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* ML Prediction */}
                <div className="card prediction-card">
                  <div className="prediction-icon">
                    {data.prediction?.direction === 'bullish' ? '🚀' : data.prediction?.direction === 'bearish' ? '📉' : '➡️'}
                  </div>
                  <h3>AI Prediction</h3>
                  <div className={`prediction-title ${data.prediction?.direction}`}>
                    {data.prediction?.prediction}
                  </div>
                  <div className="confidence-meter">
                    <div className="confidence-label">
                      <span>Confidence</span>
                      <span>{data.prediction?.confidence}%</span>
                    </div>
                    <div className="confidence-bar">
                      <div
                        className={`confidence-fill ${data.prediction?.confidence > 70 ? 'high' : data.prediction?.confidence > 50 ? 'medium' : 'low'}`}
                        style={{ width: `${data.prediction?.confidence}%` }}
                      ></div>
                    </div>
                  </div>
                  <p className="prediction-reasoning">{data.prediction?.reasoning}</p>
                  <p className="model-accuracy">Model Training Accuracy: {data.prediction?.model_accuracy}%</p>
                </div>
              </div>

              {/* Fundamentals */}
              <div className="card fundamentals-card">
                <h3>💼 Fundamentals</h3>
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
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default App

