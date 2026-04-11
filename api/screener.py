"""
api/screener.py — Stock Screener API Endpoint (GET /api/screener)

Applies the same ML model as topstocks.py across an expanded 36-stock universe
and returns all stocks matching the requested direction filter, sorted by
quality score descending.

Query parameters:
  direction  — 'bullish' | 'bearish' | 'any' (default: 'any')
               Invalid values are silently corrected to 'any'.

SECURITY MEASURES (mirrors topstocks.py):
  1. SECURE RESPONSE HEADERS — same hardened header set as the other handlers.
  2. CORS HARDENING — explicit origin allowlist via security.py.
  3. THREAD POOL CAPS — MAX_PRICE_WORKERS=8 and MAX_FUND_WORKERS=8 cap resource
     usage even though the watchlist has grown to 36 stocks.
  4. ERROR SANITIZATION — internal exceptions are not leaked to the client.
  5. INPUT VALIDATION — direction param is validated against an explicit allowset.
     Watchlist symbols are hardcoded server-side; no user input reaches YF calls.

PERFORMANCE NOTE:
  36 stocks with two I/O-bound thread phases typically takes 15-25 seconds.
  vercel.json sets maxDuration: 55 for this function. The final RandomForest
  uses n_estimators=50 (vs 100 in analyze.py) to reduce CPU across the larger
  universe without meaningfully impacting screener accuracy.

RATE LIMITING NOTE:
  Same recommendation as topstocks.py — add per-IP rate limiting with Upstash
  Redis (see api/utils/security.py RATE_LIMIT_NOTE). Recommended: 3 req/min/IP
  given higher cost than topstocks.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.scoring import (
    compute_fundamentals_score,
    compute_momentum_score,
    compute_quality_score,
    build_key_factors,
)
from utils.security import (
    sanitize_error,
    get_security_headers,
    get_cors_preflight_headers,
    MAX_PRICE_WORKERS,
    MAX_FUND_WORKERS,
    verify_clerk_jwt,
)

# ── API Configuration ─────────────────────────────────────────────────────────
YF_CHART_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ALLOWED_DIRECTIONS = {"any", "bullish", "bearish"}

# Expanded 36-stock watchlist — superset of topstocks.py WATCHLIST.
# topstocks.py is intentionally unchanged; this is an independent constant.
SCREENER_WATCHLIST = [
    # Original 18
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
    {"symbol": "JPM",   "sector": "Financial"},
    {"symbol": "WMT",   "sector": "Consumer Defensive"},
    {"symbol": "UNH",   "sector": "Healthcare"},
    {"symbol": "V",     "sector": "Financial"},
    {"symbol": "XOM",   "sector": "Energy"},
    {"symbol": "MA",    "sector": "Financial"},
    {"symbol": "COST",  "sector": "Consumer Cyclical"},
    # Additions — Healthcare
    {"symbol": "LLY",   "sector": "Healthcare"},
    {"symbol": "ABBV",  "sector": "Healthcare"},
    {"symbol": "JNJ",   "sector": "Healthcare"},
    {"symbol": "PFE",   "sector": "Healthcare"},
    # Additions — Industrials
    {"symbol": "CAT",   "sector": "Industrials"},
    {"symbol": "HON",   "sector": "Industrials"},
    {"symbol": "RTX",   "sector": "Industrials"},
    {"symbol": "DE",    "sector": "Industrials"},
    # Additions — Energy
    {"symbol": "CVX",   "sector": "Energy"},
    {"symbol": "COP",   "sector": "Energy"},
    # Additions — Financial
    {"symbol": "GS",    "sector": "Financial"},
    {"symbol": "BAC",   "sector": "Financial"},
    {"symbol": "PYPL",  "sector": "Financial"},
    # Additions — Consumer Defensive
    {"symbol": "PG",    "sector": "Consumer Defensive"},
    {"symbol": "KO",    "sector": "Consumer Defensive"},
    # Additions — Consumer Cyclical
    {"symbol": "MCD",   "sector": "Consumer Cyclical"},
    {"symbol": "HD",    "sector": "Consumer Cyclical"},
    # Additions — Communication Services
    {"symbol": "DIS",   "sector": "Communication Services"},
]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def safe_get(data, *keys, default=None):
    """Safely traverse a nested dict, returning default if any key is missing."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default


def safe_float(value):
    """Convert a value to float, returning None on any failure."""
    try:
        if value is None:
            return None
        val = str(value).replace(",", "")
        return float(val) if val and val not in ("None", "-", "N/A") else None
    except (ValueError, TypeError):
        return None


# ── DATA FETCHING ─────────────────────────────────────────────────────────────

def get_stock_data(symbol, sector):
    """Fetch 1-year OHLCV price data and current quote from Yahoo Finance."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return None

        result     = result[0]
        meta       = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote      = safe_get(result, "indicators", "quote", default=[{}])[0]

        if not timestamps:
            return None

        prices  = []
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

        price      = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")

        if price is None:
            return None

        change     = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol":         symbol,
            "name":           meta.get("shortName") or meta.get("longName") or symbol,
            "sector":         sector,
            "price":          round(float(price), 2),
            "change":         round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "prices":         prices,
        }
    except Exception as e:
        print(f"[screener/get_stock_data:{symbol}] {type(e).__name__}: {e}")
        return None


def _get_yf_crumb():
    """
    Fetch a Yahoo Finance session cookie and crumb token.
    Returns (cookies_dict, crumb_str) — crumb is None on failure.
    """
    session = requests.Session()
    try:
        session.get("https://fc.yahoo.com", headers=YF_HEADERS, timeout=5, allow_redirects=True)
    except Exception:
        pass
    try:
        resp  = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers=YF_HEADERS,
            timeout=10,
        )
        crumb   = resp.text.strip() if resp.status_code == 200 and resp.text else None
        cookies = dict(session.cookies)
        return cookies, crumb
    except Exception as e:
        print(f"[screener/_get_yf_crumb] {type(e).__name__}: {e}")
        return {}, None


def get_fundamentals(symbol, crumb=None, cookies=None):
    """Fetch company fundamentals via Yahoo Finance quoteSummary."""
    try:
        session = requests.Session()
        if cookies:
            session.cookies.update(cookies)
        url    = YF_SUMMARY_URL.format(symbol=symbol)
        params = {"modules": "defaultKeyStatistics,financialData,summaryDetail,assetProfile"}
        if crumb:
            params["crumb"] = crumb
        response = session.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data     = response.json()

        result = safe_get(data, "quoteSummary", "result")
        if not result or len(result) == 0:
            return {}

        r  = result[0]
        ks = r.get("defaultKeyStatistics", {})
        fd = r.get("financialData", {})
        sd = r.get("summaryDetail", {})
        ap = r.get("assetProfile", {})

        return {
            "sector":          ap.get("sector"),
            "pe_ratio":        safe_float(ks.get("trailingPE")),
            "forward_pe":      safe_float(ks.get("forwardPE")),
            "eps":             safe_float(ks.get("trailingEps")),
            "roe":             safe_float(fd.get("returnOnEquity")),
            "profit_margin":   safe_float(fd.get("profitMargins")),
            "market_cap":      safe_float(sd.get("marketCap")),
            "beta":            safe_float(ks.get("beta")),
            "dividend_yield":  safe_float(sd.get("dividendYield")),
            "earnings_growth": safe_float(fd.get("earningsGrowth")),
        }
    except Exception as e:
        print(f"[screener/get_fundamentals:{symbol}] {type(e).__name__}: {e}")
        return {}


# ── SCORING ───────────────────────────────────────────────────────────────────

def _compute_sector_medians(fund_results):
    """Compute per-sector median PE dynamically from live screener fundamentals."""
    from collections import defaultdict
    sector_pes = defaultdict(list)
    for fund in fund_results.values():
        sector = fund.get("sector")
        pe     = fund.get("pe_ratio")
        if sector and pe and pe > 0:
            sector_pes[sector].append(pe)
    return {
        sector: float(np.median(pes))
        for sector, pes in sector_pes.items()
        if pes
    }


# ── ML PREDICTION ─────────────────────────────────────────────────────────────

def predict_stock(stock_data, fundamentals=None):
    """
    Run ML prediction on one stock using a RandomForest trained on 1-year OHLCV
    data with 9 engineered features. Uses n_estimators=50 (vs 100 in analyze.py)
    to limit CPU cost across the larger 36-stock screener universe.
    """
    prices = stock_data["prices"]
    if len(prices) < 50:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Need more data",
        }

    price_list = list(reversed(prices))  # chronological order
    features, labels = [], []
    lookback = 5

    for i in range(lookback, len(price_list) - 5):
        row = []

        # 5-day lookback: daily return, volume change, high-low range
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                ret = (price_list[idx]["close"] - price_list[idx-1]["close"]) / price_list[idx-1]["close"]
                vol = (price_list[idx]["volume"] - price_list[idx-1]["volume"]) / max(price_list[idx-1]["volume"], 1)
                hl  = (price_list[idx]["high"]  - price_list[idx]["low"])      / price_list[idx]["close"]
                row.extend([ret, vol, hl])

        # Price position within 5-day range
        hi = max(p["high"] for p in price_list[i-lookback:i+1])
        lo = min(p["low"]  for p in price_list[i-lookback:i+1])
        row.append((price_list[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5)

        # Normalized RSI proxy (0-1)
        gains, losses = [], []
        for j in range(1, min(15, i + 1)):
            chg = price_list[i-j+1]["close"] - price_list[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100 / (1 + rs)) / 100)

        # SMA crossover signal
        if i >= 20:
            sma10 = np.mean([p["close"] for p in price_list[i-9:i+1]])
            sma20 = np.mean([p["close"] for p in price_list[i-19:i+1]])
            row.append(1 if sma10 > sma20 else 0)
        else:
            row.append(0.5)

        # Bollinger Band %B
        if i >= 20:
            window         = [p["close"] for p in price_list[i-19:i+1]]
            bb_sma, bb_std = np.mean(window), np.std(window)
            if bb_std > 0:
                bb_pct = (price_list[i]["close"] - (bb_sma - 2*bb_std)) / (4*bb_std)
                row.append(max(0.0, min(1.0, bb_pct)))
            else:
                row.append(0.5)
        else:
            row.append(0.5)

        # Distance from 52-week high
        window_52w = price_list[max(0, i-251):i+1]
        high_52w   = max(p["high"] for p in window_52w)
        row.append((high_52w - price_list[i]["close"]) / high_52w if high_52w > 0 else 0)

        # Rate-of-change deceleration
        if i >= 20:
            ret_5d  = (price_list[i]["close"] - price_list[i-5]["close"])  / price_list[i-5]["close"]
            ret_20d = (price_list[i]["close"] - price_list[i-20]["close"]) / price_list[i-20]["close"]
            row.append(ret_5d - ret_20d / 4)
        else:
            row.append(0)

        features.append(row)
        fut_ret = (price_list[i+5]["close"] - price_list[i]["close"]) / price_list[i]["close"]
        labels.append(1 if fut_ret > 0.005 else 0)

    if len(features) < 20:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Not enough data",
        }

    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred           = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {
            "prediction": "Neutral", "confidence": 50,
            "direction": "neutral", "reasoning": "Mixed market signals",
        }

    # 3-fold walk-forward validation
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

    # Final model — n_estimators=50 to limit CPU across 36 stocks
    model = RandomForestClassifier(
        n_estimators=50, max_depth=5, min_samples_split=5,
        random_state=42, class_weight="balanced",
    )
    model.fit(X_train, y_train)

    pred  = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf  = max(proba)

    # Neutral band: confidence too low to call direction
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

    # Derive signals for key factor display
    price_list_chron = list(reversed(prices))
    closes_chron     = [p["close"] for p in price_list_chron]
    sma5_val  = float(np.mean(closes_chron[-5:]))  if len(closes_chron) >= 5  else None
    sma20_val = float(np.mean(closes_chron[-20:])) if len(closes_chron) >= 20 else None

    gains, losses = [], []
    for j in range(1, min(15, len(price_list_chron))):
        chg = price_list_chron[-j]["close"] - price_list_chron[-j-1]["close"]
        (gains if chg > 0 else losses).append(abs(chg))
    rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
    rsi_approx = 100 - 100 / (1 + rs)

    bb_signal = "Within Bands"
    if sma20_val is not None:
        std20 = float(np.std(closes_chron[-20:]))
        if std20 > 0:
            upper = sma20_val + 2 * std20
            lower = sma20_val - 2 * std20
            if closes_chron[-1] > upper:
                bb_signal = "Near Upper Band"
            elif closes_chron[-1] < lower:
                bb_signal = "Near Lower Band"

    signals = {
        "rsi":       "Overbought" if rsi_approx > 65 else "Oversold" if rsi_approx < 35 else "Neutral",
        "macd":      "N/A",
        "trend":     "Uptrend" if (sma5_val and sma20_val and sma5_val > sma20_val) else "Downtrend",
        "bollinger": bb_signal,
    }
    key_factors = build_key_factors(signals, fundamentals, {"rsi": rsi_approx}, direction)

    return {
        "prediction":  text,
        "confidence":  round(conf * 100, 1),
        "direction":   direction,
        "reasoning":   key_factors["reasoning"],
        "key_factors": {
            "bullish": key_factors["bullish"],
            "bearish": key_factors["bearish"],
        },
    }


# ── API HANDLER ───────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_origin = self.headers.get("Origin")
        sec_headers    = get_security_headers(request_origin)

        # ── JWT AUTHENTICATION ──────────────────────────────────────────────
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return
        try:
            verify_clerk_jwt(auth_header[7:])
        except ValueError:
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return

        # ── QUERY PARAM PARSING ─────────────────────────────────────────────
        parsed  = urlparse(self.path)
        params  = parse_qs(parsed.query)
        raw_dir = params.get("direction", ["any"])[0].lower().strip()
        if raw_dir not in ALLOWED_DIRECTIONS:
            raw_dir = "any"

        try:
            # ── Step 1: Fetch all price data concurrently ──────────────────
            price_results = {}
            with ThreadPoolExecutor(max_workers=MAX_PRICE_WORKERS) as ex:
                future_to_info = {
                    ex.submit(get_stock_data, info["symbol"], info["sector"]): info
                    for info in SCREENER_WATCHLIST
                }
                for future in as_completed(future_to_info):
                    info = future_to_info[future]
                    try:
                        data = future.result()
                        if data:
                            price_results[info["symbol"]] = data
                    except Exception:
                        pass

            # ── Step 2: Fetch all fundamentals concurrently ────────────────
            yf_cookies, yf_crumb = _get_yf_crumb()

            symbols_with_data = list(price_results.keys())
            fund_results = {}
            with ThreadPoolExecutor(max_workers=MAX_FUND_WORKERS) as ex:
                future_to_sym = {
                    ex.submit(get_fundamentals, sym, yf_crumb, yf_cookies): sym
                    for sym in symbols_with_data
                }
                for future in as_completed(future_to_sym):
                    sym = future_to_sym[future]
                    try:
                        fund_results[sym] = future.result()
                    except Exception:
                        fund_results[sym] = {}

            # ── Step 3: Score all stocks and apply direction filter ─────────
            dynamic_medians = _compute_sector_medians(fund_results)
            results = []

            for sym, stock_data in price_results.items():
                fund       = fund_results.get(sym, {})
                prediction = predict_stock(stock_data, fund)

                # Skip stocks that don't match the requested direction filter
                if raw_dir == "bullish" and prediction["direction"] != "bullish":
                    continue
                if raw_dir == "bearish" and prediction["direction"] != "bearish":
                    continue
                # "any" passes through all directions including neutral

                fund_score     = compute_fundamentals_score(fund, sector_medians=dynamic_medians)
                momentum_score = compute_momentum_score([p["close"] for p in stock_data["prices"]])
                quality_score  = compute_quality_score(
                    prediction["confidence"], fund_score, momentum_score
                )

                results.append({
                    "symbol":         stock_data["symbol"],
                    "name":           stock_data["name"],
                    "sector":         stock_data["sector"],
                    "price":          stock_data["price"],
                    "change":         stock_data["change"],
                    "change_percent": stock_data["change_percent"],
                    "prediction":     prediction["prediction"],
                    "confidence":     prediction["confidence"],
                    "direction":      prediction["direction"],
                    "reasoning":      prediction["reasoning"],
                    "key_factors":    prediction.get("key_factors", {"bullish": [], "bearish": []}),
                    "quality_score":  quality_score,
                    "fundamentals": {
                        "pe_ratio":      fund.get("pe_ratio"),
                        "eps":           fund.get("eps"),
                        "roe":           fund.get("roe"),
                        "profit_margin": fund.get("profit_margin"),
                        "market_cap":    fund.get("market_cap"),
                    } if fund else None,
                })

            results.sort(key=lambda x: x["quality_score"], reverse=True)

            self._respond(200, {
                "stocks":    results,
                "total":     len(results),
                "direction": raw_dir,
            }, sec_headers)

        except Exception as e:
            msg = sanitize_error(500, exc=e)
            self._respond(500, {"error": msg}, sec_headers)

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
