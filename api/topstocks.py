"""
api/topstocks.py — Top Stocks API Endpoint (GET /api/topstocks)

SECURITY MEASURES (see api/utils/security.py for full rationale):
  1. SECURE RESPONSE HEADERS — same hardened header set as analyze.py:
     X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
     Cache-Control: no-store, X-Robots-Tag.
     (OWASP Secure Headers Project)

  2. CORS HARDENING — wildcard '*' replaced with an explicit origin allowlist.
     (CWE-942 / OWASP A05:2021 Security Misconfiguration)

  3. THREAD POOL CAPS (DoS mitigation) — the original code used
     max_workers=len(WATCHLIST) (18 threads) twice per invocation, meaning a
     single request could spawn 36 threads and consume the full Vercel CPU
     budget. Both pools are now capped at MAX_PRICE_WORKERS=8 and
     MAX_FUND_WORKERS=8. With 18 stocks this is still fast (I/O-bound) but
     prevents resource exhaustion under repeated abuse.
     (OWASP A05 / NIST CSF PR.PT-4)

  4. ERROR SANITIZATION — internal exceptions logged server-side; clients
     receive only a safe generic message (CWE-209).

  5. NO INPUT VALIDATION REQUIRED here — this endpoint takes no user-supplied
     parameters. The WATCHLIST is a hardcoded server-side constant; symbols
     are never derived from request input.

RATE LIMITING NOTE:
  This endpoint performs heavy ML work across 18 stocks — each call is
  expensive. It is the primary DoS target. Add per-IP rate limiting with
  Upstash Redis (see api/utils/security.py RATE_LIMIT_NOTE).
  Recommended limit: 6 requests per minute per IP.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
import json
import requests
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.ml import build_features_and_labels, classify_direction
from utils.scoring import (
    compute_fundamentals_score,
    compute_momentum_score,
    compute_quality_score,
    compute_news_sentiment_score,
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
YF_NEWS_URL    = "https://query2.finance.yahoo.com/v1/finance/search"

# Standard browser User-Agent required by Yahoo Finance to avoid rate-limiting.
YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Shared 36-stock watchlist — single source of truth in api/utils/watchlist.py
from utils.watchlist import WATCHLIST

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
    """
    Fetch 3-year OHLCV price data and current quote from Yahoo Finance.
    Symbols come from the server-side WATCHLIST — no user input involved.
    3y window gives ~700 training samples for ML (vs ~230 with 1y).
    """
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "3y", "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return None

        result = result[0]
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

        prices.reverse()   # newest first

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
        # Log detail internally; return None so the stock is gracefully skipped.
        print(f"[get_stock_data:{symbol}] {type(e).__name__}: {e}")
        return None


def _get_yf_crumb():
    """
    Fetch a Yahoo Finance session cookie and crumb token.
    YF quoteSummary v10 requires a crumb param; without it the endpoint returns
    empty results. Returns (cookies_dict, crumb_str) — crumb is None on failure.
    A dict of cookies (not the session itself) is returned so each worker thread
    can construct its own requests.Session safely — Session is not thread-safe.
    """
    session = requests.Session()
    try:
        session.get("https://fc.yahoo.com", headers=YF_HEADERS, timeout=5, allow_redirects=True)
    except Exception:
        pass
    try:
        resp = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers=YF_HEADERS,
            timeout=10,
        )
        crumb   = resp.text.strip() if resp.status_code == 200 and resp.text else None
        cookies = dict(session.cookies)
        return cookies, crumb
    except Exception as e:
        print(f"[_get_yf_crumb] {type(e).__name__}: {e}")
        return {}, None


def get_fundamentals(symbol, crumb=None, cookies=None):
    """Fetch company fundamentals via Yahoo Finance quoteSummary."""
    try:
        # Each thread gets its own session seeded with the shared cookie jar and crumb.
        session = requests.Session()
        if cookies:
            session.cookies.update(cookies)
        url = YF_SUMMARY_URL.format(symbol=symbol)
        params = {"modules": "defaultKeyStatistics,financialData,summaryDetail,assetProfile"}
        if crumb:
            params["crumb"] = crumb
        response = session.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "quoteSummary", "result")
        if not result or len(result) == 0:
            return {}

        r  = result[0]
        ks = r.get("defaultKeyStatistics", {})
        fd = r.get("financialData", {})
        sd = r.get("summaryDetail", {})
        ap = r.get("assetProfile", {})

        return {
            "sector":              ap.get("sector"),
            "pe_ratio":            safe_float(ks.get("trailingPE")),
            "forward_pe":          safe_float(ks.get("forwardPE")),
            "eps":                 safe_float(ks.get("trailingEps")),
            "roe":                 safe_float(fd.get("returnOnEquity")),
            "profit_margin":       safe_float(fd.get("profitMargins")),
            "market_cap":          safe_float(sd.get("marketCap")),
            "beta":                safe_float(ks.get("beta")),
            "dividend_yield":      safe_float(sd.get("dividendYield")),
            "earnings_growth":     safe_float(fd.get("earningsGrowth")),
            "free_cash_flow":      safe_float(fd.get("freeCashflow")),
            "operating_cash_flow": safe_float(fd.get("operatingCashflow")),
        }
    except Exception as e:
        print(f"[get_fundamentals:{symbol}] {type(e).__name__}: {e}")
        return {}


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
        return [item["title"] for item in response.json().get("news", []) if item.get("title")]
    except Exception as e:
        print(f"[get_news:{symbol}] {type(e).__name__}: {e}")
        return []


# ── SCORING ───────────────────────────────────────────────────────────────────

def _compute_sector_medians(fund_results):
    """
    Compute per-sector median PE dynamically from live watchlist fundamentals.
    Avoids stale hardcoded sector PE values that drift over time.
    """
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

def predict_stock(stock_data, fundamentals=None, spy_closes=None):
    """
    Run ML prediction on one stock using shared feature engineering and RandomForest.
    Feature building and model training are shared via utils.ml.
    spy_closes: optional SPY close prices in chronological order for relative-strength feature.
    """
    prices = stock_data["prices"]
    if len(prices) < 50:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Need more data",
        }

    price_list = list(reversed(prices))   # chronological order
    features, labels, obv_series, _ = build_features_and_labels(price_list, spy_closes)

    if len(features) < 20:
        return {
            "prediction": "Insufficient Data", "confidence": 0,
            "direction": "neutral", "reasoning": "Not enough data",
        }

    result    = classify_direction(features, labels)
    direction = result["direction"]

    # Derive display signals from price_list (already in chronological order)
    closes_chron = [p["close"] for p in price_list]
    sma5_val  = float(np.mean(closes_chron[-5:]))  if len(closes_chron) >= 5  else None
    sma20_val = float(np.mean(closes_chron[-20:])) if len(closes_chron) >= 20 else None

    # RSI proxy for key-factor display
    gains, losses = [], []
    for j in range(1, min(15, len(price_list))):
        chg = price_list[-j]["close"] - price_list[-j-1]["close"]
        (gains if chg > 0 else losses).append(abs(chg))
    rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
    rsi_approx = 100 - 100 / (1 + rs)

    # Bollinger %B position for key-factor display
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

    # OBV divergence from the series returned by build_features_and_labels
    obv_divergence = "Neutral"
    if len(obv_series) >= 11:
        obv_slope   = (obv_series[-1] - obv_series[-11]) / (abs(obv_series[-11]) + 1)
        price_slope = (closes_chron[-1] - closes_chron[-11]) / closes_chron[-11] if closes_chron[-11] != 0 else 0
        if price_slope > 0 and obv_slope < -0.01:
            obv_divergence = "Bearish"
        elif price_slope < 0 and obv_slope > 0.01:
            obv_divergence = "Bullish"

    signals = {
        "rsi":            "Overbought" if rsi_approx > 65 else "Oversold" if rsi_approx < 35 else "Neutral",
        "macd":           "N/A",
        "trend":          "Uptrend" if (sma5_val and sma20_val and sma5_val > sma20_val) else "Downtrend",
        "bollinger":      bb_signal,
        "obv_divergence": obv_divergence,
    }
    key_factors = build_key_factors(signals, fundamentals, {"rsi": rsi_approx}, direction)

    return {
        **result,
        "reasoning":  key_factors["reasoning"],
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

        try:
            # ── Step 1: Fetch all price data concurrently ──────────────────
            # SPY is fetched alongside the watchlist for relative-strength features.
            # Thread pool is capped at MAX_PRICE_WORKERS + 1 to stay within resource bounds.
            price_results = {}
            spy_closes    = None
            with ThreadPoolExecutor(max_workers=MAX_PRICE_WORKERS + 1) as ex:
                future_to_info = {
                    ex.submit(get_stock_data, info["symbol"], info["sector"]): info
                    for info in WATCHLIST
                }
                spy_future = ex.submit(get_stock_data, "SPY", "Benchmark")
                for future in as_completed(future_to_info):
                    info = future_to_info[future]
                    try:
                        data = future.result()
                        if data:
                            price_results[info["symbol"]] = data
                    except Exception:
                        pass   # skip failed symbols silently
                try:
                    spy_data = spy_future.result()
                    if spy_data and "prices" in spy_data and spy_data["prices"]:
                        spy_closes = list(reversed([p["close"] for p in spy_data["prices"]]))
                except Exception:
                    pass

            # ── Step 2: Fetch all fundamentals concurrently ────────────────
            # Crumb is fetched once here and shared across all worker threads.
            # Each thread creates its own Session seeded with the shared cookies
            # (requests.Session is not thread-safe for concurrent use).
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

            # ── Step 3: Score all stocks (CPU-bound, no I/O) ───────────────
            dynamic_medians = _compute_sector_medians(fund_results)
            results = []

            for sym, stock_data in price_results.items():
                fund       = fund_results.get(sym, {})
                prediction = predict_stock(stock_data, fund, spy_closes=spy_closes)

                # Only include bullish predictions in the primary ranking
                if prediction["direction"] != "bullish":
                    continue

                fund_score = compute_fundamentals_score(fund, sector_medians=dynamic_medians)

                # Use 1y slice for momentum/ATR scoring — these are short-term signals
                prices_1y    = stock_data["prices"][:252]
                price_list_c = list(reversed(prices_1y))
                n_p = len(price_list_c)
                atr_ratio = None
                if n_p >= 60:
                    atr_v = []
                    for k in range(n_p):
                        if k == 0:
                            atr_v.append(price_list_c[k]["high"] - price_list_c[k]["low"])
                        else:
                            atr_v.append(max(
                                price_list_c[k]["high"] - price_list_c[k]["low"],
                                abs(price_list_c[k]["high"] - price_list_c[k-1]["close"]),
                                abs(price_list_c[k]["low"]  - price_list_c[k-1]["close"]),
                            ))
                    atr_ratio = float(np.mean(atr_v[-5:])) / (float(np.mean(atr_v[-60:])) + 1e-8)

                momentum_score = compute_momentum_score(
                    [p["close"] for p in prices_1y], atr_ratio=atr_ratio
                )
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

            # Sort by composite quality score descending; take top 5
            results.sort(key=lambda x: x["quality_score"], reverse=True)
            top_5 = results[:5]

            # Pad with best non-bullish stocks if fewer than 5 bullish found
            if len(top_5) < 5:
                already = {r["symbol"] for r in top_5}
                for sym, stock_data in price_results.items():
                    if len(top_5) >= 5:
                        break
                    if sym in already:
                        continue
                    fund       = fund_results.get(sym, {})
                    prediction = predict_stock(stock_data, fund, spy_closes=spy_closes)
                    fund_score = compute_fundamentals_score(fund, sector_medians=dynamic_medians)

                    prices_1y    = stock_data["prices"][:252]
                    price_list_c = list(reversed(prices_1y))
                    n_p = len(price_list_c)
                    atr_ratio = None
                    if n_p >= 60:
                        atr_v = []
                        for k in range(n_p):
                            if k == 0:
                                atr_v.append(price_list_c[k]["high"] - price_list_c[k]["low"])
                            else:
                                atr_v.append(max(
                                    price_list_c[k]["high"] - price_list_c[k]["low"],
                                    abs(price_list_c[k]["high"] - price_list_c[k-1]["close"]),
                                    abs(price_list_c[k]["low"]  - price_list_c[k-1]["close"]),
                                ))
                        atr_ratio = float(np.mean(atr_v[-5:])) / (float(np.mean(atr_v[-60:])) + 1e-8)

                    momentum_score = compute_momentum_score(
                        [p["close"] for p in prices_1y], atr_ratio=atr_ratio
                    )
                    quality_score  = compute_quality_score(
                        prediction["confidence"], fund_score, momentum_score
                    )
                    top_5.append({
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
                            "rate_limited":  fund.get("rate_limited", False),
                        } if fund else None,
                    })

            # ── Step 4: Fetch news for top 5 only (limits to 5 extra API calls) ──
            top_5_symbols = [s["symbol"] for s in top_5]
            news_results = {}
            with ThreadPoolExecutor(max_workers=5) as ex:
                future_to_sym = {ex.submit(get_news, sym): sym for sym in top_5_symbols}
                for future in as_completed(future_to_sym):
                    sym = future_to_sym[future]
                    try:
                        headlines = future.result()
                        news_results[sym] = {
                            "score":     round(compute_news_sentiment_score(headlines), 1)
                                         if headlines else None,
                            "headlines": headlines[:3],
                        }
                    except Exception:
                        news_results[sym] = None

            for stock in top_5:
                stock["news"] = news_results.get(stock["symbol"])

            self._respond(200, {"stocks": top_5}, sec_headers)

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
