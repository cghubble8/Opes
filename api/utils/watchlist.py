"""
Single source of truth for the stock watchlist used by topstocks.py and screener.py.
"""

WATCHLIST = [
    # ── Core mega-cap tech ──────────────────────────────────────────────────
    {"symbol": "NVDA",  "sector": "Technology"},
    {"symbol": "META",  "sector": "Technology"},
    {"symbol": "AMZN",  "sector": "Consumer Cyclical"},
    {"symbol": "AAPL",  "sector": "Technology"},
    {"symbol": "GOOGL", "sector": "Technology"},
    {"symbol": "MSFT",  "sector": "Technology"},
    {"symbol": "TSLA",  "sector": "Consumer Cyclical"},
    {"symbol": "AMD",   "sector": "Technology"},
    {"symbol": "NFLX",  "sector": "Communication Services"},
    {"symbol": "CRM",   "sector": "Technology"},
    {"symbol": "AVGO",  "sector": "Technology"},

    # ── Financials ──────────────────────────────────────────────────────────
    {"symbol": "JPM",   "sector": "Financial"},
    {"symbol": "V",     "sector": "Financial"},
    {"symbol": "MA",    "sector": "Financial"},
    {"symbol": "GS",    "sector": "Financial"},
    {"symbol": "BAC",   "sector": "Financial"},
    {"symbol": "PYPL",  "sector": "Financial"},

    # ── Healthcare ──────────────────────────────────────────────────────────
    {"symbol": "UNH",   "sector": "Healthcare"},
    {"symbol": "LLY",   "sector": "Healthcare"},
    {"symbol": "ABBV",  "sector": "Healthcare"},
    {"symbol": "JNJ",   "sector": "Healthcare"},
    {"symbol": "PFE",   "sector": "Healthcare"},

    # ── Industrials ─────────────────────────────────────────────────────────
    {"symbol": "CAT",   "sector": "Industrials"},
    {"symbol": "HON",   "sector": "Industrials"},
    {"symbol": "RTX",   "sector": "Industrials"},
    {"symbol": "DE",    "sector": "Industrials"},

    # ── Energy ──────────────────────────────────────────────────────────────
    {"symbol": "XOM",   "sector": "Energy"},
    {"symbol": "CVX",   "sector": "Energy"},
    {"symbol": "COP",   "sector": "Energy"},

    # ── Consumer Defensive ──────────────────────────────────────────────────
    {"symbol": "WMT",   "sector": "Consumer Defensive"},
    {"symbol": "PG",    "sector": "Consumer Defensive"},
    {"symbol": "KO",    "sector": "Consumer Defensive"},

    # ── Consumer Cyclical ───────────────────────────────────────────────────
    {"symbol": "COST",  "sector": "Consumer Cyclical"},
    {"symbol": "MCD",   "sector": "Consumer Cyclical"},
    {"symbol": "HD",    "sector": "Consumer Cyclical"},

    # ── Communication Services ──────────────────────────────────────────────
    {"symbol": "DIS",   "sector": "Communication Services"},
]
