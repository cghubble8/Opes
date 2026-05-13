"""
api/top_dividends.py — Top Dividend Stocks Screener (GET /api/topdividends)

Processing:
  1. Fetch fundamentals (with dividend fields) for all 36 watchlist stocks concurrently
  2. Filter: dividend_yield > 0.5%
  3. Compute compute_dividend_safety_score() for each payer
  4. Composite dividend ranking: yield score×0.4 + safety×0.4 + fundamentals×0.2
  5. Fetch price data + run ML for top candidates
  6. Return top 10 sorted by composite score

SECURITY NOTES:
  - No user input: WATCHLIST is a hardcoded server-side constant.
  - Thread pool capped at MAX_FUND_WORKERS=8 (DoS mitigation, same as topstocks.py).
  - JWT required before any processing.
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
    compute_dividend_safety_score,
    dividend_safety_label,
    quality_score_to_label,
)
from utils.security import (
    sanitize_error,
    get_security_headers,
    get_cors_preflight_headers,
    MAX_FUND_WORKERS,
    verify_clerk_jwt,
)
from utils.watchlist import WATCHLIST

YF_CHART_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_PRICE_WORKERS = 8

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
        if isinstance(value, dict):
            return float(value.get("raw")) if value.get("raw") is not None else None
        val = str(value).replace(",", "")
        return float(val) if val and val not in ("None", "-", "N/A") else None
    except (ValueError, TypeError):
        return None


# ── DATA FETCHING ─────────────────────────────────────────────────────────────

def _get_yf_crumb():
    """Fetch a Yahoo Finance session cookie and crumb token (shared across worker threads)."""
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


def get_div_fundamentals(symbol, crumb=None, cookies=None):
    """Fetch fundamentals including dividend-specific fields for one watchlist stock."""
    try:
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
        if not result:
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
            "dividend_rate":       safe_float(sd.get("dividendRate")),
            "payout_ratio":        safe_float(sd.get("payoutRatio")),
            "trailing_div_rate":   safe_float(sd.get("trailingAnnualDividendRate")),
            "shares_outstanding":  safe_float(ks.get("sharesOutstanding")),
            "earnings_growth":     safe_float(fd.get("earningsGrowth")),
            "free_cash_flow":      safe_float(fd.get("freeCashflow")),
            "operating_cash_flow": safe_float(fd.get("operatingCashflow")),
        }
    except Exception as e:
        print(f"[get_div_fundamentals:{symbol}] {type(e).__name__}: {e}")
        return {}


def get_stock_prices(symbol):
    """Fetch 1-year daily price data and current quote for ML prediction."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result:
            return None

        result = result[0]
        meta       = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote      = safe_get(result, "indicators", "quote", default=[{}])[0]

        closes  = quote.get("close", [])
        volumes = quote.get("volume", [])
        highs   = quote.get("high", [])
        lows    = quote.get("low", [])

        prices = []
        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                prices.append({
                    "date":   date_str,
                    "open":   float(quote.get("open", [0])[i]) if i < len(quote.get("open", [])) and quote.get("open", [])[i] else 0,
                    "high":   float(highs[i]) if i < len(highs) and highs[i] else 0,
                    "low":    float(lows[i])  if i < len(lows)  and lows[i]  else 0,
                    "close":  float(closes[i]),
                    "volume": int(volumes[i]) if i < len(volumes) and volumes[i] else 0,
                })
        prices.reverse()  # newest first

        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None:
            return None

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "price":          round(float(price), 2),
            "change":         round(float(change), 2),
            "change_percent": f"{change_pct:+.2f}",
            "prices":         prices,
        }
    except Exception as e:
        print(f"[get_stock_prices:{symbol}] {type(e).__name__}: {e}")
        return None


# ── ML PREDICTION ─────────────────────────────────────────────────────────────

def _predict_direction(prices):
    """Run a quick RandomForest prediction on 1-year price data."""
    if not prices or len(prices) < 50:
        return "neutral", 50

    price_list = list(reversed(prices))
    features, labels, _, _ = build_features_and_labels(price_list)
    if len(features) < 20:
        return "neutral", 50

    result = classify_direction(features, labels)
    return result.get("direction", "neutral"), result.get("confidence", 50)


# ── API HANDLER ───────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_origin = self.headers.get("Origin")
        sec_headers = get_security_headers(request_origin)

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return
        try:
            verify_clerk_jwt(auth_header[7:])
        except ValueError:
            self._respond(401, {"error": sanitize_error(401)}, sec_headers)
            return

        try:
            # ── Step 1: Fetch fundamentals for all watchlist stocks ────────────
            yf_cookies, yf_crumb = _get_yf_crumb()
            fund_results = {}
            with ThreadPoolExecutor(max_workers=MAX_FUND_WORKERS) as ex:
                future_to_sym = {
                    ex.submit(get_div_fundamentals, info["symbol"], yf_crumb, yf_cookies): info
                    for info in WATCHLIST
                }
                for future in as_completed(future_to_sym):
                    info = future_to_sym[future]
                    sym  = info["symbol"]
                    try:
                        fund = future.result()
                        fund["_watchlist_sector"] = info["sector"]
                        fund_results[sym] = fund
                    except Exception:
                        fund_results[sym] = {}

            # ── Step 2: Filter to meaningful dividend payers ───────────────────
            dividend_payers = []
            for sym, fund in fund_results.items():
                div_yield = fund.get("dividend_yield") or 0
                if div_yield > 0.005:  # > 0.5%
                    dividend_payers.append(sym)

            if not dividend_payers:
                self._respond(200, {"stocks": []}, sec_headers)
                return

            # ── Step 3: Score all dividend payers ─────────────────────────────
            scored = []
            for sym in dividend_payers:
                fund = fund_results[sym]
                div_yield_pct = (fund.get("dividend_yield") or 0) * 100

                safety_score = compute_dividend_safety_score(fund) or 0
                fund_score   = compute_fundamentals_score(fund) or 50

                # Yield score: linear 0-100 capped at 6% yield
                yield_score = min(100.0, (div_yield_pct / 6.0) * 100)

                composite = round(yield_score * 0.4 + safety_score * 0.4 + fund_score * 0.2, 1)

                scored.append({
                    "symbol":        sym,
                    "fund":          fund,
                    "div_yield_pct": div_yield_pct,
                    "safety_score":  safety_score,
                    "fund_score":    fund_score,
                    "yield_score":   yield_score,
                    "composite":     composite,
                })

            scored.sort(key=lambda x: x["composite"], reverse=True)
            top_candidates = scored[:15]  # fetch prices for top 15 to run ML

            # ── Step 4: Fetch price data + run ML for top candidates ───────────
            price_results = {}
            with ThreadPoolExecutor(max_workers=MAX_PRICE_WORKERS) as ex:
                future_to_sym = {
                    ex.submit(get_stock_prices, c["symbol"]): c["symbol"]
                    for c in top_candidates
                }
                for future in as_completed(future_to_sym):
                    sym = future_to_sym[future]
                    try:
                        price_results[sym] = future.result()
                    except Exception:
                        price_results[sym] = None

            # ── Step 5: Build final response for top 10 ───────────────────────
            results = []
            for c in top_candidates:
                if len(results) >= 10:
                    break
                sym   = c["symbol"]
                fund  = c["fund"]
                price_data = price_results.get(sym)

                direction, confidence = "neutral", 50
                if price_data and price_data.get("prices"):
                    direction, confidence = _predict_direction(price_data["prices"])

                rating = quality_score_to_label(c["composite"], direction)

                # Prefer watchlist sector (pre-validated) over API sector
                sector = fund.get("_watchlist_sector") or fund.get("sector") or "Unknown"

                results.append({
                    "symbol":                   sym,
                    "name":                     fund.get("name", sym),
                    "sector":                   sector,
                    "price":                    price_data["price"] if price_data else None,
                    "change_percent":           price_data["change_percent"] if price_data else None,
                    "dividend_yield":           round(c["div_yield_pct"], 2),
                    "dividend_rate":            fund.get("dividend_rate"),
                    "payout_ratio":             fund.get("payout_ratio"),
                    "safety_score":             c["safety_score"],
                    "safety_label":             dividend_safety_label(c["safety_score"]),
                    "consecutive_growth_years": None,  # requires per-stock history fetch
                    "direction":                direction,
                    "confidence":               confidence,
                    "rating":                   rating,
                    "quality_score":            c["composite"],
                })

            self._respond(200, {"stocks": results}, sec_headers)

        except Exception as e:
            self._respond(500, {"error": sanitize_error(500, exc=e)}, sec_headers)

    def _respond(self, status, data, sec_headers):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in sec_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        request_origin = self.headers.get("Origin")
        headers = get_cors_preflight_headers(request_origin)
        self.send_response(200)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
