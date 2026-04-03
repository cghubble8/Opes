# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Frontend development
npm run dev        # Start Vite dev server (hot reload)
npm run build      # Production build to /dist
npm run lint       # ESLint check
npm run preview    # Preview production build locally

# No test suite configured
```

Python dependencies: `pip install -r requirements.txt`

Environment variable required: `ALPHA_VANTAGE_KEY` (Alpha Vantage free tier API key)

## Architecture

**FinAssist-V2** is a stock analysis app — React 19 SPA frontend + Python serverless backend deployed on Vercel.

### Frontend (`src/`)

Three views managed by `App.jsx`:
- **Analyze** — User enters a stock symbol; app fetches deep analysis (technical indicators, ML prediction, fundamentals)
- **TopStocks** — Displays top 5 ranked buy-rated stocks from a hardcoded 18-stock watchlist
- **Portfolio** — Mock holdings with sparklines; no backend, pure local data from `src/services/portfolio.js`

Services (`src/services/`):
- `api.js` — Calls `/api/analyze`, caches results in localStorage (daily expiry, cache version 2, stale-cache fallback)
- `topStocks.js` — Calls `/api/topstocks`, same daily localStorage cache pattern
- `portfolio.js` — Pure mock data, no API calls

### Backend (`api/`)

Two Vercel Python serverless handlers:

**`analyze.py` — `GET /api/analyze?symbol=X`**
- Fetches in parallel (3 threads): Yahoo Finance 3mo prices, current quote, Alpha Vantage fundamentals
- Computes: SMA (20/50), EMA (12/26), RSI (14), MACD (12/26/9), Bollinger Bands (20), OBV
- Trains a RandomForestClassifier (100 estimators, depth 5) on 5-day lookback features per request
- Composite quality score: fundamentals 40% + ML confidence 40% + momentum 20%

**`topstocks.py` — `GET /api/topstocks`**
- Processes hardcoded `WATCHLIST` (18 large-cap stocks: NVDA, META, AMZN, AAPL, GOOGL, etc.)
- Concurrent price fetch (uncapped threads), fundamentals fetch capped at 5 workers to respect Alpha Vantage's 5 req/min free tier limit
- Uses the same 4-pillar scoring as `analyze.py`; returns top 5 bullish stocks, padded with non-bullish if fewer than 5

**`api/utils/`**
- `technical.py` — All indicator math (SMA, EMA, RSI, MACD, Bollinger, OBV)
- `stock_data.py` — Yahoo Finance HTTP client
- `ml_model.py` — RandomForest training logic

### Data Sources

| Source | Auth | Usage |
|--------|------|-------|
| Yahoo Finance Chart API | None required | Prices, quotes, chart data |
| Alpha Vantage | `ALPHA_VANTAGE_KEY` env var | PE ratio, ROE, EPS, sector, company overview |

### Deployment

`vercel.json` routes `/api/**/*.py` to Vercel's Python runtime; static frontend is served from `/dist`. The ML model is retrained on every backend request (no persistence).

### Auth

Login is demo-only — `Login.jsx` accepts any email/password and stores a local user object. There is no backend auth, no token validation, and no real security layer.

### Instructions 

Comments should be short and to the point. 
Do not use '----------------example-----------' or '==========example=========' for comments.