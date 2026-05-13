"""
api/dividends.py — Dividend Profile API Endpoint (GET /api/dividends?symbol=X)

Returns a full dividend profile for a single symbol:
  - yield, rate, payout ratio, ex-date, next payment date
  - 5-year dividend payment history
  - computed stats: payment frequency, 3yr growth rate, consecutive growth years
  - dividend safety score (0-100) via shared compute_dividend_safety_score()
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from utils.scoring import compute_dividend_safety_score, dividend_safety_label
from utils.security import (
    validate_symbol,
    sanitize_error,
    get_security_headers,
    get_cors_preflight_headers,
    verify_clerk_jwt,
)

YF_CHART_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

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


def safe_get(data, *keys, default=None):
    """Safely traverse a nested dict, returning default if any key is missing."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default


# ── DATA FETCHING ─────────────────────────────────────────────────────────────

def _get_yf_crumb():
    """Fetch a Yahoo Finance session cookie and crumb token."""
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
        crumb = resp.text.strip() if resp.status_code == 200 and resp.text else None
        return session, crumb
    except Exception as e:
        print(f"[_get_yf_crumb] {type(e).__name__}: {e}")
        return requests.Session(), None


def get_company_overview(symbol):
    """Fetch fundamentals including all dividend fields via Yahoo Finance quoteSummary."""
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
        if not result:
            return {"error": "Company data not found", "symbol": symbol, "name": symbol}

        r  = result[0]
        ks = r.get("defaultKeyStatistics", {})
        fd = r.get("financialData", {})
        sd = r.get("summaryDetail", {})
        ap = r.get("assetProfile", {})
        ce = r.get("calendarEvents", {})

        meta_name = sd.get("longName") or ap.get("longBusinessSummary", "")[:30] or symbol

        return {
            "symbol":              symbol,
            "name":                meta_name,
            "sector":              ap.get("sector"),
            "pe_ratio":            safe_float(ks.get("trailingPE")),
            "earnings_growth":     safe_float(fd.get("earningsGrowth")),
            "operating_cash_flow": safe_float(fd.get("operatingCashflow")),
            "free_cash_flow":      safe_float(fd.get("freeCashflow")),
            "market_cap":          safe_float(sd.get("marketCap")),
            "beta":                safe_float(ks.get("beta")),
            "dividend_yield":      safe_float(sd.get("dividendYield")),
            "dividend_rate":       safe_float(sd.get("dividendRate")),
            "payout_ratio":        safe_float(sd.get("payoutRatio")),
            "ex_dividend_date":    (sd.get("exDividendDate") or {}).get("fmt") if isinstance(sd.get("exDividendDate"), dict) else None,
            "trailing_div_rate":   safe_float(sd.get("trailingAnnualDividendRate")),
            "next_dividend_date":  (ce.get("dividendDate") or {}).get("fmt") if ce and isinstance(ce.get("dividendDate"), dict) else None,
            "shares_outstanding":  safe_float(ks.get("sharesOutstanding")),
        }
    except Exception as e:
        print(f"[get_company_overview:{symbol}] {type(e).__name__}: {e}")
        return {"error": "Failed to fetch company data.", "symbol": symbol, "name": symbol}


def get_dividend_history(symbol):
    """Fetch 5-year dividend payment history from Yahoo Finance chart API (events=dividends)."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {
            "range": "5y",
            "interval": "1mo",
            "events": "dividends",
            "includePrePost": "false",
        }
        response = requests.get(url, params=params, headers=YF_HEADERS, timeout=15)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result:
            return []

        events = result[0].get("events", {})
        dividends_raw = events.get("dividends", {})

        history = []
        for ts_str, entry in dividends_raw.items():
            ts = entry.get("date") or int(ts_str)
            amount = entry.get("amount")
            if amount is not None and amount > 0:
                date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                history.append({"date": date_str, "amount": round(float(amount), 4)})

        history.sort(key=lambda x: x["date"])
        return history
    except Exception as e:
        print(f"[get_dividend_history:{symbol}] {type(e).__name__}: {e}")
        return []


# ── HISTORY STATS ─────────────────────────────────────────────────────────────

def _compute_history_stats(history):
    """Derive payment_frequency, growth_rate_3yr, and consecutive_growth_years from history."""
    if len(history) < 2:
        return {"payment_frequency": None, "growth_rate_3yr": None, "consecutive_growth_years": 0}

    # Payment frequency from median gap between payments
    dates = [datetime.strptime(h["date"], "%Y-%m-%d") for h in history]
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    median_days = sorted(intervals)[len(intervals) // 2]
    if median_days < 45:
        frequency = "monthly"
    elif median_days < 120:
        frequency = "quarterly"
    elif median_days < 270:
        frequency = "semi-annual"
    else:
        frequency = "annual"

    # 3yr growth rate: compare most-recent payment to one from ~3 years ago
    now = datetime.utcnow()
    recent_payments = [
        h for h in history
        if (now - datetime.strptime(h["date"], "%Y-%m-%d")).days < 400
    ]
    past_3yr_payments = [
        h for h in history
        if 1000 < (now - datetime.strptime(h["date"], "%Y-%m-%d")).days < 1400
    ]
    growth_rate_3yr = None
    if recent_payments and past_3yr_payments:
        recent_amt = recent_payments[-1]["amount"]
        past_amt = past_3yr_payments[0]["amount"]
        if past_amt and past_amt > 0:
            growth_rate_3yr = round((recent_amt - past_amt) / past_amt * 100, 2)

    # Consecutive years of growth: compare annual totals year-over-year
    year_totals = defaultdict(float)
    for h in history:
        yr = datetime.strptime(h["date"], "%Y-%m-%d").year
        year_totals[yr] += h["amount"]

    years = sorted(year_totals.keys(), reverse=True)
    consecutive_growth = 0
    for i in range(len(years) - 1):
        if year_totals[years[i]] > year_totals[years[i + 1]]:
            consecutive_growth += 1
        else:
            break

    return {
        "payment_frequency":        frequency,
        "growth_rate_3yr":          growth_rate_3yr,
        "consecutive_growth_years": consecutive_growth,
    }


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

        parsed    = urlparse(self.path)
        params    = parse_qs(parsed.query)
        raw_symbol = params.get("symbol", [""])[0]

        try:
            symbol = validate_symbol(raw_symbol)
        except ValueError as e:
            self._respond(400, {"error": str(e)}, sec_headers)
            return

        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_fund = ex.submit(get_company_overview, symbol)
                f_hist = ex.submit(get_dividend_history, symbol)
                fund    = f_fund.result()
                history = f_hist.result()

            if "error" in fund and not fund.get("dividend_yield"):
                self._respond(200, {
                    "symbol": symbol, "name": fund.get("name", symbol),
                    "pays_dividend": False, "dividend_yield": None,
                    "dividend_rate": None, "payout_ratio": None,
                    "ex_dividend_date": None, "next_dividend_date": None,
                    "trailing_div_rate": None, "payment_frequency": None,
                    "consecutive_growth_years": None, "growth_rate_3yr": None,
                    "safety_score": None, "safety_label": None, "history": [],
                }, sec_headers)
                return

            div_yield = fund.get("dividend_yield") or 0
            pays_dividend = div_yield > 0

            if not pays_dividend:
                self._respond(200, {
                    "symbol": symbol, "name": fund.get("name", symbol),
                    "pays_dividend": False, "dividend_yield": None,
                    "dividend_rate": None, "payout_ratio": None,
                    "ex_dividend_date": None, "next_dividend_date": None,
                    "trailing_div_rate": None, "payment_frequency": None,
                    "consecutive_growth_years": None, "growth_rate_3yr": None,
                    "safety_score": None, "safety_label": None, "history": [],
                }, sec_headers)
                return

            stats = _compute_history_stats(history)
            fund_with_growth = {**fund, "growth_rate_3yr": stats["growth_rate_3yr"]}
            safety_score = compute_dividend_safety_score(fund_with_growth)
            safety_lbl   = dividend_safety_label(safety_score)

            self._respond(200, {
                "symbol":                   symbol,
                "name":                     fund.get("name", symbol),
                "pays_dividend":            True,
                "dividend_yield":           round(div_yield * 100, 2),
                "dividend_rate":            fund.get("dividend_rate"),
                "payout_ratio":             fund.get("payout_ratio"),
                "ex_dividend_date":         fund.get("ex_dividend_date"),
                "next_dividend_date":       fund.get("next_dividend_date"),
                "trailing_div_rate":        fund.get("trailing_div_rate"),
                "payment_frequency":        stats["payment_frequency"],
                "consecutive_growth_years": stats["consecutive_growth_years"],
                "growth_rate_3yr":          stats["growth_rate_3yr"],
                "safety_score":             safety_score,
                "safety_label":             safety_lbl,
                "history":                  history,
            }, sec_headers)

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
