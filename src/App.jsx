import { useState, useEffect } from 'react'
import { useUser, useAuth, Show, SignIn, UserButton } from '@clerk/react'
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
import IndicatorsGrid from './components/IndicatorsGrid'
import PriceChart from './components/PriceChart'
import PredictionCard from './components/PredictionCard'
import FundamentalsCard from './components/FundamentalsCard'
import SignalHistoryCard from './components/SignalHistoryCard'
import './App.css'

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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [currentView, setCurrentView] = useState('market')
  const [macroData, setMacroData] = useState(null)
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareData, setCompareData] = useState({})

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
            <span className="nav-label-desktop">Top 5 Buys</span>
            <span className="nav-label-mobile">Top 5</span>
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
                    Compare {compareOpen ? '▼' : '▲'}
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

              {/* Sector Context Warning */}
              {getSectorContextWarning(data, macroData) && (
                <div className="earnings-banner earnings-info">
                  Sector context — {getSectorContextWarning(data, macroData)}
                </div>
              )}

              <IndicatorsGrid indicators={data.indicators} signals={data.signals} />

              <div className="chart-prediction-grid">
                <PriceChart symbol={data.symbol} chartData={data.chart_data} />
                <PredictionCard prediction={data.prediction} news={data.news} />
              </div>

              <FundamentalsCard fundamentals={data.fundamentals} />

              <SignalHistoryCard signalHistory={data.signal_history} signalStats={data.signal_stats} />

            </div>
          )}
        </>
      )}
        {/* Compare Bottom Sheet */}
        {data && (
          <>
            {compareOpen && (
              <div
                className="compare-sheet-backdrop"
                onClick={() => setCompareOpen(false)}
              />
            )}
            <div className={`compare-sheet ${compareOpen ? 'compare-sheet-open' : ''}`}>
              <div className="compare-sheet-handle-bar">
                <div className="compare-sheet-handle" />
                <span className="compare-sheet-title">Compare Stocks</span>
                <button
                  className="compare-sheet-close"
                  onClick={() => setCompareOpen(false)}
                  aria-label="Close compare"
                >
                  ✕
                </button>
              </div>
              <div className="compare-sheet-body">
                <CompareView
                  primaryData={data}
                  compareData={compareData}
                  onAdd={handleAddCompare}
                  onRemove={handleRemoveCompare}
                  formatNumber={formatNumber}
                />
              </div>
            </div>
          </>
        )}
        </div>
      </Show>
    </>
  )
}

export default App

