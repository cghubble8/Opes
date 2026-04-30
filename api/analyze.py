"""
api/analyze.py — Stock Analysis API Endpoint (GET /api/analyze?symbol=X)

SECURITY MEASURES (see api/utils/security.py for full rationale):
  1. INPUT VALIDATION — symbol is validated against a strict regex whitelist
     (uppercase A-Z, 1–10 chars, optional single dot) before being used in
     any URL construction. Raw input is never interpolated into URLs.
     (CWE-20 / OWASP A03:2021 Injection)

  2. SECURE RESPONSE HEADERS — every response includes:
       X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
       Cache-Control: no-store, X-Robots-Tag.
     (OWASP Secure Headers Project)

  3. CORS HARDENING — wildcard '*' replaced with an explicit origin allowlist.
     (CWE-942 / OWASP A05:2021 Security Misconfiguration)

  4. ERROR SANITIZATION — internal Python exceptions are logged server-side;
     clients receive only a generic safe message (CWE-209).

  5. CONCURRENCY CAP — ThreadPoolExecutor is bounded at 5 workers for the
     five independent I/O calls this endpoint makes (prices, SPY prices,
     fundamentals, quote, news).

  6. YAHOO FINANCE TIMEOUTS — all outbound requests use a 15-second timeout
     to prevent the serverless function from hanging indefinitely.

RATE LIMITING NOTE:
  Stateless input validation is enforced here. Full per-IP token-bucket rate
  limiting requires an external store (e.g. Upstash Redis). See
  api/utils/security.py for the recommended implementation pattern.
  Recommended limit: 20 requests per minute per IP.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from utils.scoring import (
    compute_fundamentals_score,
    compute_momentum_score,
    compute_quality_score,
    compute_news_sentiment_score,
    quality_score_to_label,
    build_key_factors,
)
from utils.security import (
    validate_symbol,
    sanitize_error,
    get_security_headers,
    get_cors_preflight_headers,
    verify_clerk_jwt,
)

# ── API Configuration ─────────────────────────────────────────────────────────
# These are public Yahoo Finance endpoints — no API keys required or stored.
YF_CHART_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
YF_NEWS_URL    = "https://query2.finance.yahoo.com/v1/finance/search"

# Outbound request headers — required by Yahoo Finance to avoid 429 responses.
# This is a standard browser User-Agent; no credentials are included.
YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def safe_float(value):
    """Convert a value to float, returning None on any failure."""
    try:
        if value is None:
            return None
        if isinstance(value, dict):
            return float(value.get("raw")) if value.get("raw") is not None else None
        val = str(value).replace(",", "")
        return float(val) if val and val != "None" and val != "-" else None
    except (ValueError, TypeError):
        return None


def safe_get(data, *keys, default=None):
    """Safely traverse a nested dict, returning default if any key is missing."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default


# ── STOCK DATA FETCHING ───────────────────────────────────────────────────────

def get_daily_prices(symbol, range_period="1y"):
    """
    Fetch daily OHLCV data from Yahoo Finance chart API.
    symbol has already been validated before this function is called.
    """
    try:
        # Symbol is safe to interpolate — validated against [A-Z]{1,10}(\.[A-Z]{1,2})?
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": range_period, "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        data = response.json()

        error = safe_get(data, "chart", "error")
        if error:
            return {"error": error.get("description", "Unknown error")}

        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return {"error": f"No data found for {symbol}"}

        result = result[0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote = safe_get(result, "indicators", "quote", default=[{}])[0]

        if not timestamps:
            return {"error": f"No price data for {symbol}"}

        prices = []
        opens   = quote.get("open", [])
        highs   = quote.get("high", [])
        lows    = quote.get("low", [])
        closes  = quote.get("close", [])
        volumes = quote.get("volume", [])

        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                prices.append({
                    "date":   date_str,
                    "open":   float(opens[i])   if i < len(opens)   and opens[i]   else 0,
                    "high":   float(highs[i])   if i < len(highs)   and highs[i]   else 0,
                    "low":    float(lows[i])    if i < len(lows)    and lows[i]    else 0,
                    "close":  float(closes[i]),
                    "volume": int(volumes[i])   if i < len(volumes) and volumes[i] else 0,
                })

        prices.reverse()  # newest first

        return {
            "symbol": symbol,
            "prices": prices,
            "meta": {
                "name":     meta.get("shortName") or meta.get("longName") or symbol,
                "exchange": meta.get("exchangeName"),
                "currency": meta.get("currency"),
            },
        }
    except Exception as e:
        # Log internally; do not propagate raw exception text to the client.
        print(f"[get_daily_prices] {type(e).__name__}: {e}")
        return {"error": "Failed to fetch price data."}


def get_quote(symbol):
    """Fetch the current market quote from Yahoo Finance chart API (1-minute interval)."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1d", "interval": "1m", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return {"error": "Quote not found"}

        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")

        if price is None:
            return {"error": "Quote not found"}

        change     = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol":           symbol,
            "price":            round(float(price), 2),
            "change":           round(float(change), 2),
            "change_percent":   f"{change_pct:.2f}",
            "volume":           int(meta.get("regularMarketVolume", 0)),
            "latest_trading_day": (
                datetime.utcfromtimestamp(meta["regularMarketTime"]).strftime("%Y-%m-%d")
                if meta.get("regularMarketTime") else None
            ),
        }
    except Exception as e:
        print(f"[get_quote] {type(e).__name__}: {e}")
        return {"error": "Failed to fetch quote."}


def _get_yf_crumb():
    """
    Fetch a Yahoo Finance session cookie and crumb token.
    YF quoteSummary v10 requires a crumb param; without it the endpoint returns
    empty results and all fundamental fields come back None.
    Returns (session, crumb_str) — crumb is None on failure; callers degrade gracefully.
    """
    session = requests.Session()
    try:
        # Prime the session with a Yahoo Finance cookie (fc.yahoo.com sets the consent cookie)
        session.get("https://fc.yahoo.com", headers=YF_HEADERS, timeout=5, allow_redirects=True)
    except Exception:
        pass  # endpoint sometimes times out; continue with whatever cookies landed
    try:
        resp = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers=YF_HEADERS,
            timeout=10,
        )
        crumb = resp.text.strip() if resp.status_code == 200 and resp.text else None
        return session, crumb
    except Exception as e:
        print(f"[_get_yf_crumb] {type(e).__name__}: {e}")
        return session, None


def get_news(symbol):
    """Fetch up to 10 recent news headlines for a symbol from Yahoo Finance search."""
    try:
        params = {
            "q": symbol,
            "newsCount": "10",
            "enableFuzzyQuery": "false",
            "enableCb": "false",
        }
        response = requests.get(YF_NEWS_URL, params=params, headers=YF_HEADERS, timeout=10)
        data = response.json()
        news_items = data.get("news", [])
        return [item["title"] for item in news_items if item.get("title")]
    except Exception as e:
        print(f"[get_news:{symbol}] {type(e).__name__}: {e}")
        return []


def get_company_overview(symbol):
    """Fetch company fundamentals and upcoming earnings via Yahoo Finance quoteSummary."""
    try:
        session, crumb = _get_yf_crumb()
        url = YF_SUMMARY_URL.format(symbol=symbol)
        params = {
            "modules": "defaultKeyStatistics,financialData,summaryDetail,assetProfile,calendarEvents"
        }
        if crumb:
            params["crumb"] = crumb
        response = session.get(url, params=params, headers=YF_HEADERS, timeout=15)
        data = response.json()

        result = safe_get(data, "quoteSummary", "result")
        if not result or len(result) == 0:
            return {"error": "Company data not found", "symbol": symbol, "name": symbol}

        r  = result[0]
        ks = r.get("defaultKeyStatistics", {})
        fd = r.get("financialData", {})
        sd = r.get("summaryDetail", {})
        ap = r.get("assetProfile", {})
        ce = r.get("calendarEvents", {})

        # Extract next earnings date and compute days until
        earnings = None
        earnings_dates = safe_get(ce, "earnings", "earningsDate", default=[])
        if earnings_dates:
            try:
                next_date_fmt = earnings_dates[0].get("fmt")
                if next_date_fmt:
                    from datetime import date
                    days_until = (
                        datetime.strptime(next_date_fmt, "%Y-%m-%d").date() - date.today()
                    ).days
                    if days_until >= 0:
                        earnings = {"date": next_date_fmt, "days_until": days_until}
            except Exception:
                pass

        return {
            "symbol":              symbol,
            "name":                symbol,
            "sector":              ap.get("sector"),
            "industry":            ap.get("industry"),
            "pe_ratio":            safe_float(ks.get("trailingPE")),
            "forward_pe":          safe_float(ks.get("forwardPE")),
            "eps":                 safe_float(ks.get("trailingEps")),
            "roe":                 safe_float(fd.get("returnOnEquity")),
            "market_cap":          safe_float(sd.get("marketCap")),
            "dividend_yield":      safe_float(sd.get("dividendYield")),
            "52_week_high":        safe_float(sd.get("fiftyTwoWeekHigh")),
            "52_week_low":         safe_float(sd.get("fiftyTwoWeekLow")),
            "beta":                safe_float(ks.get("beta")),
            "profit_margin":       safe_float(fd.get("profitMargins")),
            "earnings_growth":     safe_float(fd.get("earningsGrowth")),
            "free_cash_flow":      safe_float(fd.get("freeCashflow")),
            "operating_cash_flow": safe_float(fd.get("operatingCashflow")),
            "earnings":            earnings,
        }
    except Exception as e:
        print(f"[get_company_overview] {type(e).__name__}: {e}")
        return {"error": "Failed to fetch company data.", "symbol": symbol, "name": symbol}


# ── TECHNICAL INDICATORS ──────────────────────────────────────────────────────

def calculate_sma(prices, period):
    """Simple Moving Average over a rolling window."""
    if len(prices) < period:
        return [None] * len(prices)
    sma = []
    for i in range(len(prices)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(np.mean(prices[i - period + 1:i + 1]))
    return sma


def calculate_ema(prices, period):
    """Exponential Moving Average with a standard multiplier of 2/(period+1)."""
    if len(prices) < period:
        return [None] * len(prices)
    multiplier = 2 / (period + 1)
    ema = [None] * (period - 1)
    ema.append(np.mean(prices[:period]))
    for i in range(period, len(prices)):
        ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
    return ema


def calculate_rsi(prices, period=14):
    """RSI (14) using Wilder's smoothed moving average method."""
    if len(prices) < period + 1:
        return [None] * len(prices)
    deltas = np.diff(prices)
    gains  = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    rsi = [None] * period
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(prices)):
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
        if i < len(prices) - 1:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return rsi


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """MACD line, signal line, and histogram."""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = [
        (ema_fast[i] - ema_slow[i])
        if ema_fast[i] is not None and ema_slow[i] is not None
        else None
        for i in range(len(prices))
    ]
    valid_macd = [x for x in macd_line if x is not None]
    if len(valid_macd) < signal:
        return {
            "macd_line": macd_line,
            "signal_line": [None] * len(prices),
            "histogram": [None] * len(prices),
        }
    signal_ema  = calculate_ema(valid_macd, signal)
    signal_line = [None] * (len(prices) - len(signal_ema)) + signal_ema
    histogram = [
        (macd_line[i] - signal_line[i])
        if macd_line[i] is not None and signal_line[i] is not None
        else None
        for i in range(len(prices))
    ]
    return {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram}


def calculate_bollinger(prices, period=20, std_dev=2.0):
    """Bollinger Bands: middle SMA and upper/lower bands at ±2 std deviations."""
    sma = calculate_sma(prices, period)
    upper, lower = [], []
    for i in range(len(prices)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
        else:
            std = np.std(prices[i - period + 1:i + 1])
            upper.append(sma[i] + (std_dev * std))
            lower.append(sma[i] - (std_dev * std))
    return {"middle": sma, "upper": upper, "lower": lower}


def calculate_obv(closes, volumes):
    """On-Balance Volume: accumulates volume in the direction of price movement."""
    if len(closes) != len(volumes) or len(closes) < 2:
        return [None] * len(closes)
    obv = [volumes[0]]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv


def calculate_all_indicators(price_data):
    """Compute all technical indicators from OHLCV price data."""
    if not price_data or len(price_data) < 26:
        return {"error": "Insufficient data"}

    closes  = [p["close"]  for p in reversed(price_data)]
    volumes = [p["volume"] for p in reversed(price_data)]

    sma_20   = calculate_sma(closes, 20)
    sma_50   = calculate_sma(closes, 50)
    ema_12   = calculate_ema(closes, 12)
    ema_26   = calculate_ema(closes, 26)
    rsi      = calculate_rsi(closes, 14)
    macd     = calculate_macd(closes)
    bollinger= calculate_bollinger(closes)
    obv      = calculate_obv(closes, volumes)

    # OBV slope vs price slope over last 10 bars — detects accumulation/distribution divergence
    obv_divergence = "Neutral"
    if len(obv) >= 11 and all(v is not None for v in obv[-11:]):
        obv_slope   = (obv[-1] - obv[-11]) / (abs(obv[-11]) + 1)
        price_slope = (closes[-1] - closes[-11]) / closes[-11] if closes[-11] != 0 else 0
        if price_slope > 0 and obv_slope < -0.01:
            obv_divergence = "Bearish"
        elif price_slope < 0 and obv_slope > 0.01:
            obv_divergence = "Bullish"

    latest = len(closes) - 1
    get    = lambda arr: arr[latest] if arr[latest] is not None else None

    current_price   = closes[latest]
    latest_rsi      = get(rsi)
    latest_macd     = get(macd["macd_line"])
    latest_signal   = get(macd["signal_line"])
    latest_upper    = get(bollinger["upper"])
    latest_lower    = get(bollinger["lower"])
    latest_sma_20   = get(sma_20)
    latest_sma_50   = get(sma_50)

    rsi_signal  = (
        "Overbought" if latest_rsi and latest_rsi > 70
        else "Oversold" if latest_rsi and latest_rsi < 30
        else "Neutral"
    )
    macd_signal = (
        "Bullish" if latest_macd and latest_signal and latest_macd > latest_signal
        else "Bearish" if latest_macd and latest_signal
        else "N/A"
    )

    if latest_upper and latest_lower:
        bw  = latest_upper - latest_lower
        pos = (current_price - latest_lower) / bw if bw > 0 else 0.5
        bb_signal = (
            "Near Upper Band" if pos > 0.8
            else "Near Lower Band" if pos < 0.2
            else "Within Bands"
        )
    else:
        bb_signal = "N/A"

    if latest_sma_20 and latest_sma_50:
        if current_price > latest_sma_20 > latest_sma_50:
            trend = "Strong Uptrend"
        elif current_price > latest_sma_20:
            trend = "Uptrend"
        elif current_price < latest_sma_20 < latest_sma_50:
            trend = "Strong Downtrend"
        elif current_price < latest_sma_20:
            trend = "Downtrend"
        else:
            trend = "Neutral"
    else:
        trend = "N/A"

    return {
        "indicators": {
            "sma_20":           round(latest_sma_20,        2) if latest_sma_20       else None,
            "sma_50":           round(latest_sma_50,        2) if latest_sma_50       else None,
            "ema_12":           round(get(ema_12),          2) if get(ema_12)         else None,
            "ema_26":           round(get(ema_26),          2) if get(ema_26)         else None,
            "rsi":              round(latest_rsi,           2) if latest_rsi          else None,
            "macd":             round(latest_macd,       4) if latest_macd         else None,
            "macd_signal":      round(latest_signal,     4) if latest_signal       else None,
            "macd_histogram":   round(get(macd["histogram"]), 4) if get(macd["histogram"]) else None,
            "bollinger_upper":  round(latest_upper,        2) if latest_upper        else None,
            "bollinger_middle": round(get(bollinger["middle"]), 2) if get(bollinger["middle"]) else None,
            "bollinger_lower":  round(latest_lower,        2) if latest_lower        else None,
            "obv":              get(obv),
        },
        "signals": {
            "rsi": rsi_signal, "macd": macd_signal,
            "bollinger": bb_signal, "trend": trend,
            "obv_divergence": obv_divergence,
        },
        "chart_data": {
            "dates":            [p["date"]  for p in price_data][:60],
            "closes":           [p["close"] for p in price_data][:60],
            "sma_20":           list(reversed(sma_20))[:60],
            "bollinger_upper":  list(reversed(bollinger["upper"]))[:60],
            "bollinger_lower":  list(reversed(bollinger["lower"]))[:60],
        },
    }


# ── ML PREDICTION ─────────────────────────────────────────────────────────────

def train_and_predict(price_data, fundamentals=None, spy_closes=None):
    """
    Train a RandomForestClassifier on 1-year of OHLCV data and predict
    the 5-day forward return direction for the most recent data point.
    Walk-forward 3-fold validation is used to estimate out-of-sample accuracy.
    spy_closes: optional list of SPY close prices in chronological order (same length as price_data).
    """
    if len(price_data) < 50:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Need 50+ days of data",
        }

    prices   = list(reversed(price_data))   # chronological order
    features, labels = [], []
    lookback = 5

    # Precompute ATR series to avoid O(n²) recalculation in the feature loop
    atr_series = []
    for k in range(len(prices)):
        if k == 0:
            atr_series.append(prices[k]["high"] - prices[k]["low"])
        else:
            atr_series.append(max(
                prices[k]["high"] - prices[k]["low"],
                abs(prices[k]["high"] - prices[k-1]["close"]),
                abs(prices[k]["low"]  - prices[k-1]["close"]),
            ))

    # Precompute OBV series
    obv_series = [prices[0]["volume"]]
    for k in range(1, len(prices)):
        if prices[k]["close"] > prices[k-1]["close"]:
            obv_series.append(obv_series[-1] + prices[k]["volume"])
        elif prices[k]["close"] < prices[k-1]["close"]:
            obv_series.append(obv_series[-1] - prices[k]["volume"])
        else:
            obv_series.append(obv_series[-1])

    for i in range(lookback, len(prices) - 5):
        row = []

        # 5-day lookback: daily return, volume change, high-low range
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                ret = (prices[idx]["close"] - prices[idx-1]["close"]) / prices[idx-1]["close"]
                vol = (prices[idx]["volume"] - prices[idx-1]["volume"]) / max(prices[idx-1]["volume"], 1)
                hl  = (prices[idx]["high"]  - prices[idx]["low"])      / prices[idx]["close"]
                row.extend([ret, vol, hl])

        # Price position within 5-day range (0=at low, 1=at high)
        hi = max(p["high"] for p in prices[i-lookback:i+1])
        lo = min(p["low"]  for p in prices[i-lookback:i+1])
        row.append((prices[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5)

        # Normalized RSI proxy (0-1)
        gains, losses = [], []
        for j in range(1, min(15, i + 1)):
            chg = prices[i-j+1]["close"] - prices[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100 / (1 + rs)) / 100)

        # SMA crossover signal (1=bullish cross, 0=bearish)
        if i >= 20:
            sma10 = np.mean([p["close"] for p in prices[i-9:i+1]])
            sma20 = np.mean([p["close"] for p in prices[i-19:i+1]])
            row.append(1 if sma10 > sma20 else 0)
        else:
            row.append(0.5)

        # Bollinger Band %B — where price sits within the bands (0=lower, 1=upper)
        if i >= 20:
            window           = [p["close"] for p in prices[i-19:i+1]]
            bb_sma, bb_std   = np.mean(window), np.std(window)
            if bb_std > 0:
                bb_pct = (prices[i]["close"] - (bb_sma - 2*bb_std)) / (4*bb_std)
                row.append(max(0.0, min(1.0, bb_pct)))
            else:
                row.append(0.5)
        else:
            row.append(0.5)

        # Distance from 52-week high (0=at high, higher=further below)
        window_52w = prices[max(0, i-251):i+1]
        high_52w   = max(p["high"] for p in window_52w)
        row.append((high_52w - prices[i]["close"]) / high_52w if high_52w > 0 else 0)

        # Rate-of-change deceleration: 5-day return vs 20-day annualised run rate
        if i >= 20:
            ret_5d  = (prices[i]["close"] - prices[i-5]["close"])  / prices[i-5]["close"]
            ret_20d = (prices[i]["close"] - prices[i-20]["close"]) / prices[i-20]["close"]
            row.append(ret_5d - ret_20d / 4)
        else:
            row.append(0)

        # OBV slope divergence: volume confirming or contradicting price trend (Granville signal)
        if i >= 10:
            obv_slope   = (obv_series[i] - obv_series[i-10]) / (abs(obv_series[i-10]) + 1)
            price_slope = (prices[i]["close"] - prices[i-10]["close"]) / prices[i-10]["close"]
            row.append(float(np.tanh(obv_slope - price_slope * 100)))
        else:
            row.append(0.0)

        # ATR volatility regime: 5-day ATR / 60-day ATR normalized to [0, 1]
        # Low = contracting volatility (range-bound); high = expanding (trending/risky)
        if i >= 60:
            atr_5d  = float(np.mean(atr_series[i-4:i+1]))
            atr_60d = float(np.mean(atr_series[i-59:i+1]))
            row.append(min(1.0, atr_5d / (atr_60d + 1e-8) / 3))
        else:
            row.append(0.5)

        # SPY relative strength: 63-day stock excess return vs market (Jegadeesh-Titman)
        if spy_closes is not None and i >= 63 and i < len(spy_closes) and (i - 63) >= 0:
            stock_ret = (prices[i]["close"] - prices[i-63]["close"]) / prices[i-63]["close"]
            spy_ret   = (spy_closes[i] - spy_closes[i-63]) / spy_closes[i-63] if spy_closes[i-63] > 0 else 0
            row.append(float(np.tanh((stock_ret - spy_ret) * 5)))
        else:
            row.append(0.0)

        features.append(row)
        fut_ret = (prices[i+5]["close"] - prices[i]["close"]) / prices[i]["close"]
        labels.append(1 if fut_ret > 0.005 else 0)   # >0.5% gain = bullish label

    if len(features) < 20:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Not enough training data",
        }

    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred           = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {
            "prediction": "Insufficient Variety", "confidence": 0,
            "direction": "neutral", "reasoning": "Data lacks variety",
        }

    # 3-fold expanding walk-forward validation — more robust than a single split.
    # Folds: train [0:60%] test [60:70%], [0:70%] test [70:80%], [0:80%] test [80:90%]
    val_accuracy = None
    n = len(features)
    fold_accs = []
    for pct_train, pct_end in [(0.60, 0.70), (0.70, 0.80), (0.80, 0.90)]:
        t_end = int(n * pct_train)
        v_end = min(int(n * pct_end), n - 1)
        if t_end < 20 or (v_end - t_end) < 5:
            continue
        X_tr_v = np.array(features[:t_end])
        y_tr_v = np.array(labels[:t_end])
        X_val  = np.array(features[t_end:v_end])
        y_val  = np.array(labels[t_end:v_end])
        if len(np.unique(y_val)) < 2 or np.sum(y_tr_v) == 0 or np.sum(y_tr_v) == len(y_tr_v):
            continue
        val_model = RandomForestClassifier(
            n_estimators=50, max_depth=5, min_samples_split=5,
            random_state=42, class_weight="balanced",
        )
        val_model.fit(X_tr_v, y_tr_v)
        fold_accs.append(val_model.score(X_val, y_val))
    if fold_accs:
        val_accuracy = round(float(np.mean(fold_accs)) * 100, 1)

    model = RandomForestClassifier(
        n_estimators=100, max_depth=5, min_samples_split=5,
        random_state=42, class_weight="balanced",
    )
    model.fit(X_train, y_train)

    pred  = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf  = max(proba)

    # Neutral band: model confidence too low to commit to a direction
    if 0.45 <= conf <= 0.55:
        direction = "neutral"
        text = "Neutral / Hold"
    elif pred == 1:
        direction = "bullish"
        text = (
            "Strong Buy Signal"   if conf > 0.7
            else "Moderate Buy Signal" if conf > 0.55
            else "Weak Buy Signal"
        )
    else:
        direction = "bearish"
        text = (
            "Strong Sell Signal"   if conf > 0.7
            else "Moderate Sell Signal" if conf > 0.55
            else "Weak Sell Signal"
        )

    note = ""
    if fundamentals:
        pe, roe = fundamentals.get("pe_ratio"), fundamentals.get("roe")
        if pe and roe and pe < 20 and roe > 0.10:
            note = " Fundamentals appear strong."
        elif pe and pe > 35 and not fundamentals.get("earnings_growth"):
            note = " High P/E may indicate overvaluation."

    baseline = max(np.mean(labels[:-1]), 1 - np.mean(labels[:-1])) * 100
    if val_accuracy is not None and val_accuracy < baseline + 5:
        note += " Signal quality is uncertain — model shows limited historical accuracy."

    return {
        "prediction":         text,
        "confidence":         round(conf * 100, 1),
        "direction":          direction,
        "reasoning":          f"Based on momentum, mean-reversion, and trend patterns.{note}",
        "model_accuracy":     round(model.score(X_train, y_train) * 100, 1),
        "validation_accuracy": val_accuracy,
    }


# ── API HANDLER ───────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Extract the Origin header for CORS validation
        request_origin = self.headers.get("Origin")
        sec_headers    = get_security_headers(request_origin)

        # ── JWT AUTHENTICATION ──────────────────────────────────────────────
        # Verify Clerk JWT token from Authorization header before processing
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return
        try:
            verify_clerk_jwt(auth_header[7:])  # strip "Bearer " prefix
        except ValueError:
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # ── INPUT VALIDATION ────────────────────────────────────────────────
        # Validate the symbol before any downstream use. validate_symbol()
        # enforces a strict character whitelist and length cap (CWE-20).
        raw_symbol = params.get("symbol", [""])[0]
        try:
            symbol = validate_symbol(raw_symbol)
        except ValueError as e:
            self._respond(400, {"error": str(e)}, sec_headers)
            return

        try:
            # 5 concurrent I/O calls: prices, SPY prices, fundamentals, quote, news
            with ThreadPoolExecutor(max_workers=5) as ex:
                f_prices = ex.submit(get_daily_prices, symbol)
                f_spy    = ex.submit(get_daily_prices, "SPY")
                f_fund   = ex.submit(get_company_overview, symbol)
                f_quote  = ex.submit(get_quote, symbol)
                f_news   = ex.submit(get_news, symbol)
                prices       = f_prices.result()
                spy_data     = f_spy.result()
                fundamentals = f_fund.result()
                quote        = f_quote.result()
                headlines    = f_news.result()

            if "error" in prices:
                self._respond(400, {"error": prices["error"], "symbol": symbol}, sec_headers)
                return

            # SPY closes in chronological order for relative-strength ML feature
            spy_closes = None
            if "prices" in spy_data and spy_data["prices"]:
                spy_closes = list(reversed([p["close"] for p in spy_data["prices"]]))

            # Current ATR ratio for volatility-regime momentum penalty
            price_list_chron = list(reversed(prices["prices"]))
            n_prices = len(price_list_chron)
            current_atr_ratio = None
            if n_prices >= 60:
                atr_vals = []
                for k in range(n_prices):
                    if k == 0:
                        atr_vals.append(price_list_chron[k]["high"] - price_list_chron[k]["low"])
                    else:
                        atr_vals.append(max(
                            price_list_chron[k]["high"] - price_list_chron[k]["low"],
                            abs(price_list_chron[k]["high"] - price_list_chron[k-1]["close"]),
                            abs(price_list_chron[k]["low"]  - price_list_chron[k-1]["close"]),
                        ))
                current_atr_ratio = float(np.mean(atr_vals[-5:])) / (float(np.mean(atr_vals[-60:])) + 1e-8)

            # CPU-bound ML and indicator work runs after I/O completes
            indicators     = calculate_all_indicators(prices["prices"])
            prediction     = train_and_predict(prices["prices"], fundamentals, spy_closes=spy_closes)

            fund_score     = compute_fundamentals_score(fundamentals)
            closes         = [p["close"] for p in prices["prices"]]
            momentum_score = compute_momentum_score(closes, atr_ratio=current_atr_ratio)
            news_score     = compute_news_sentiment_score(headlines)
            quality_score  = compute_quality_score(
                prediction["confidence"], fund_score, momentum_score, news_score
            )
            rating_label   = quality_score_to_label(quality_score, prediction["direction"])

            key_factors = build_key_factors(
                signals=indicators.get("signals", {}),
                fundamentals=fundamentals,
                indicators=indicators.get("indicators", {}),
                direction=prediction["direction"],
            )

            name = (
                fundamentals.get("name")
                or prices.get("meta", {}).get("name")
                or symbol
            )

            # Build news sentiment label
            def _news_label(score):
                if score is None:
                    return None
                if score >= 70:   return "Bullish"
                if score >= 57:   return "Moderately Bullish"
                if score >= 43:   return "Neutral"
                if score >= 30:   return "Moderately Bearish"
                return "Bearish"

            self._respond(200, {
                "symbol": symbol,
                "name":   name,
                "sector": fundamentals.get("sector"),
                "quote":  quote,
                "indicators": indicators.get("indicators", {}),
                "signals":    indicators.get("signals", {}),
                "fundamentals": {
                    "pe_ratio":       fundamentals.get("pe_ratio"),
                    "forward_pe":     fundamentals.get("forward_pe"),
                    "eps":            fundamentals.get("eps"),
                    "roe":            fundamentals.get("roe"),
                    "market_cap":     fundamentals.get("market_cap"),
                    "dividend_yield": fundamentals.get("dividend_yield"),
                    "52_week_high":   fundamentals.get("52_week_high"),
                    "52_week_low":    fundamentals.get("52_week_low"),
                    "beta":           fundamentals.get("beta"),
                    "profit_margin":  fundamentals.get("profit_margin"),
                    "earnings_growth":fundamentals.get("earnings_growth"),
                },
                "prediction": {
                    **prediction,
                    "reasoning":   key_factors["reasoning"],
                    "key_factors": {
                        "bullish": key_factors["bullish"],
                        "bearish": key_factors["bearish"],
                    },
                    "rating":               rating_label,
                    "quality_score":        quality_score,
                    "fund_score":           round(fund_score, 1) if fund_score is not None else None,
                    "momentum_score":       round(momentum_score, 1),
                    "news_score":           round(news_score, 1) if news_score is not None else None,
                    "validation_accuracy":  prediction.get("validation_accuracy"),
                },
                "news": {
                    "score":     round(news_score, 1) if news_score is not None else None,
                    "label":     _news_label(news_score),
                    "headlines": headlines[:3],
                } if headlines else None,
                "earnings": fundamentals.get("earnings"),
                "chart_data": indicators.get("chart_data", {}),
            }, sec_headers)

        except Exception as e:
            # Sanitize exception — client gets a generic message, logs get detail.
            msg = sanitize_error(500, exc=e)
            self._respond(500, {"error": msg, "symbol": symbol}, sec_headers)

    def _respond(self, status: int, data: dict, sec_headers: dict):
        """Send a JSON response with all security headers attached."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in sec_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight — only grant approval to allowed origins."""
        request_origin = self.headers.get("Origin")
        headers = get_cors_preflight_headers(request_origin)
        self.send_response(200)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
