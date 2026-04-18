"""
api/macro.py — Macro/Market Overview Endpoint (GET /api/macro)

Fetches SPY, QQQ, VIX, and 11 SPDR sector ETFs, runs the same
RandomForest + 4-pillar quality scoring pipeline used in topstocks.py,
and returns structured market context for the dashboard and persistent banner.

No user-supplied parameters — all tickers are hardcoded server-side constants.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler
import json
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.scoring import (
    compute_momentum_score,
    compute_quality_score,
    quality_score_to_label,
    build_key_factors,
)
from utils.security import (
    sanitize_error,
    get_security_headers,
    get_cors_preflight_headers,
    MAX_PRICE_WORKERS,
    verify_clerk_jwt,
)

# ── Ticker Configuration ───────────────────────────────────────────────────────

YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

VIX_SYMBOL  = "%5EVIX"  # URL-encoded ^VIX for Yahoo Finance
VIX_DISPLAY = "^VIX"

INDICES = ["SPY", "QQQ"]
INDEX_NAMES = {
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
}

SECTOR_SYMBOLS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLRE", "XLB", "XLU", "XLC"]
SECTOR_NAMES = {
    "XLK":  "Technology",
    "XLF":  "Financial Services",
    "XLE":  "Energy",
    "XLV":  "Healthcare",
    "XLI":  "Industrials",
    "XLY":  "Consumer Cyclical",
    "XLP":  "Consumer Defensive",
    "XLRE": "Real Estate",
    "XLB":  "Basic Materials",
    "XLU":  "Utilities",
    "XLC":  "Communication Services",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_get(data, *keys, default=None):
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default


# ── Data Fetching ──────────────────────────────────────────────────────────────

def get_ticker_data(symbol):
    """Fetch 1-year OHLCV and current quote from Yahoo Finance for an index or ETF."""
    try:
        url    = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
        resp   = requests.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data   = resp.json()

        result = safe_get(data, "chart", "result")
        if not result:
            return None
        result = result[0]

        meta       = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote      = safe_get(result, "indicators", "quote", default=[{}])[0]

        if not timestamps:
            return None

        opens   = quote.get("open",   [])
        highs   = quote.get("high",   [])
        lows    = quote.get("low",    [])
        closes  = quote.get("close",  [])
        volumes = quote.get("volume", [])

        prices = []
        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                prices.append({
                    "date":   datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
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
            "price":          round(float(price), 2),
            "change":         round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "prices":         prices,
        }
    except Exception as e:
        print(f"[get_ticker_data:{symbol}] {type(e).__name__}: {e}")
        return None


def get_vix():
    """Fetch current VIX value. VIX has no volume/fundamentals so no ML is run."""
    try:
        url    = YF_CHART_URL.format(symbol=VIX_SYMBOL)
        params = {"range": "1d", "interval": "1m", "includePrePost": "false"}
        resp   = requests.get(url, params=params, headers=YF_HEADERS, timeout=10)
        data   = resp.json()

        result = safe_get(data, "chart", "result")
        if not result:
            return None
        price = result[0].get("meta", {}).get("regularMarketPrice")
        if price is None:
            return None

        return {
            "symbol": VIX_DISPLAY,
            "price":  round(float(price), 2),
            "label":  interpret_vix(price),
            "is_vix": True,
        }
    except Exception as e:
        print(f"[get_vix] {type(e).__name__}: {e}")
        return None


def interpret_vix(value):
    """Map VIX value to a human-readable volatility regime."""
    if value is None:
        return "Unknown"
    if value < 15:
        return "Low"
    if value < 20:
        return "Moderate"
    if value < 30:
        return "Elevated"
    return "Extreme Fear"


# ── Indicators ─────────────────────────────────────────────────────────────────

def compute_rsi(prices, period=14):
    """Compute RSI from prices list (newest first) using the last `period+1` closes."""
    if len(prices) < period + 1:
        return None
    recent = list(reversed(prices[:period + 1]))
    closes = [p["close"] for p in recent]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 1)


def compute_sector_perfs(prices):
    """Compute 1-month (~21 trading days) and 3-month (~63 days) return from prices (newest first)."""
    current = prices[0]["close"] if prices else None
    if not current:
        return {"perf_1m": None, "perf_3m": None}
    perf_1m = round((current - prices[21]["close"]) / prices[21]["close"] * 100, 1) if len(prices) >= 22 else None
    perf_3m = round((current - prices[62]["close"]) / prices[62]["close"] * 100, 1) if len(prices) >= 63 else None
    return {"perf_1m": perf_1m, "perf_3m": perf_3m}


# ── ML Prediction ──────────────────────────────────────────────────────────────

def predict_ticker(stock_data):
    """
    RandomForest prediction on one index/ETF using the same 9-feature pipeline as topstocks.py.
    n_estimators=50 per fold to keep CPU cost low across 13 tickers in one request.
    """
    prices = stock_data["prices"]
    if len(prices) < 50:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Need more data"}

    price_list = list(reversed(prices))  # chronological
    features, labels = [], []
    lookback = 5

    for i in range(lookback, len(price_list) - 5):
        row = []
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                ret = (price_list[idx]["close"] - price_list[idx-1]["close"]) / price_list[idx-1]["close"]
                vol = (price_list[idx]["volume"] - price_list[idx-1]["volume"]) / max(price_list[idx-1]["volume"], 1)
                hl  = (price_list[idx]["high"] - price_list[idx]["low"]) / price_list[idx]["close"]
                row.extend([ret, vol, hl])

        hi = max(p["high"] for p in price_list[i-lookback:i+1])
        lo = min(p["low"]  for p in price_list[i-lookback:i+1])
        row.append((price_list[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5)

        gains, losses = [], []
        for j in range(1, min(15, i + 1)):
            chg = price_list[i-j+1]["close"] - price_list[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100 / (1 + rs)) / 100)

        if i >= 20:
            sma10 = np.mean([p["close"] for p in price_list[i-9:i+1]])
            sma20 = np.mean([p["close"] for p in price_list[i-19:i+1]])
            row.append(1 if sma10 > sma20 else 0)
        else:
            row.append(0.5)

        if i >= 20:
            window = [p["close"] for p in price_list[i-19:i+1]]
            bb_sma, bb_std = np.mean(window), np.std(window)
            if bb_std > 0:
                bb_pct = (price_list[i]["close"] - (bb_sma - 2*bb_std)) / (4*bb_std)
                row.append(max(0.0, min(1.0, bb_pct)))
            else:
                row.append(0.5)
        else:
            row.append(0.5)

        window_52w = price_list[max(0, i-251):i+1]
        high_52w   = max(p["high"] for p in window_52w)
        row.append((high_52w - price_list[i]["close"]) / high_52w if high_52w > 0 else 0)

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
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Not enough data"}

    X_train = np.array(features[:-1])
    y_train = np.array(labels[:-1])
    X_pred  = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {"prediction": "Neutral", "confidence": 50, "direction": "neutral", "reasoning": "Mixed market signals"}

    # 3-fold walk-forward validation
    n = len(features)
    fold_accs = []
    for pct_train, pct_end in [(0.60, 0.70), (0.70, 0.80), (0.80, 0.90)]:
        t_end = int(n * pct_train)
        v_end = min(int(n * pct_end), n - 1)
        if t_end < 20 or (v_end - t_end) < 5:
            continue
        X_tv = np.array(features[:t_end])
        y_tv = np.array(labels[:t_end])
        X_v  = np.array(features[t_end:v_end])
        y_v  = np.array(labels[t_end:v_end])
        if len(np.unique(y_v)) < 2 or np.sum(y_tv) == 0 or np.sum(y_tv) == len(y_tv):
            continue
        val_model = RandomForestClassifier(
            n_estimators=50, max_depth=5, min_samples_split=5, random_state=42, class_weight="balanced"
        )
        val_model.fit(X_tv, y_tv)
        fold_accs.append(val_model.score(X_v, y_v))

    model = RandomForestClassifier(
        n_estimators=100, max_depth=5, min_samples_split=5, random_state=42, class_weight="balanced"
    )
    model.fit(X_train, y_train)

    pred  = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf  = max(proba)

    if 0.45 <= conf <= 0.55:
        direction, text = "neutral", "Neutral / Hold"
    elif pred == 1:
        direction = "bullish"
        text = "Strong Buy Signal" if conf > 0.7 else "Moderate Buy Signal" if conf > 0.55 else "Weak Buy Signal"
    else:
        direction = "bearish"
        text = "Strong Sell Signal" if conf > 0.7 else "Moderate Sell Signal" if conf > 0.55 else "Weak Sell Signal"

    closes_chron = [p["close"] for p in price_list]
    sma5  = float(np.mean(closes_chron[-5:]))  if len(closes_chron) >= 5  else None
    sma20 = float(np.mean(closes_chron[-20:])) if len(closes_chron) >= 20 else None

    gains2, losses2 = [], []
    for j in range(1, min(15, len(price_list))):
        chg = price_list[-j]["close"] - price_list[-j-1]["close"]
        (gains2 if chg > 0 else losses2).append(abs(chg))
    rs2 = (np.mean(gains2) if gains2 else 0) / (np.mean(losses2) if losses2 else 0.001)
    rsi_approx = 100 - 100 / (1 + rs2)

    bb_signal = "Within Bands"
    if sma20 is not None:
        std20 = float(np.std(closes_chron[-20:]))
        if std20 > 0:
            upper = sma20 + 2 * std20
            lower = sma20 - 2 * std20
            if closes_chron[-1] > upper:
                bb_signal = "Near Upper Band"
            elif closes_chron[-1] < lower:
                bb_signal = "Near Lower Band"

    signals = {
        "rsi":      "Overbought" if rsi_approx > 65 else "Oversold" if rsi_approx < 35 else "Neutral",
        "macd":     "N/A",
        "trend":    "Uptrend" if (sma5 and sma20 and sma5 > sma20) else "Downtrend",
        "bollinger": bb_signal,
    }
    key_factors = build_key_factors(signals, {}, {"rsi": rsi_approx}, direction)

    return {
        "prediction": text,
        "confidence": round(conf * 100, 1),
        "direction":  direction,
        "reasoning":  key_factors["reasoning"],
    }


# ── API Handler ────────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request_origin = self.headers.get("Origin")
        sec_headers    = get_security_headers(request_origin)

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
            all_ml_symbols = INDICES + SECTOR_SYMBOLS  # 13 tickers

            # ── Wave 1: Fetch all price data + VIX concurrently ───────────────
            price_results = {}
            vix_data      = None
            with ThreadPoolExecutor(max_workers=MAX_PRICE_WORKERS) as ex:
                futures = {ex.submit(get_ticker_data, sym): sym for sym in all_ml_symbols}
                vix_fut = ex.submit(get_vix)

                for future in as_completed(list(futures.keys()) + [vix_fut]):
                    if future is vix_fut:
                        try:
                            vix_data = future.result()
                        except Exception:
                            pass
                    else:
                        sym = futures[future]
                        try:
                            result = future.result()
                            if result:
                                price_results[sym] = result
                        except Exception:
                            pass

            # ── Wave 2: Score all non-VIX tickers (CPU-bound) ─────────────────
            # ETFs have no meaningful fundamentals; scoring uses ML 65% + Momentum 35%.
            indices_out = {}
            sectors_out = {}

            for sym in INDICES:
                stock_data = price_results.get(sym)
                if not stock_data:
                    continue
                closes    = [p["close"] for p in stock_data["prices"]]
                pred      = predict_ticker(stock_data)
                mom_score = compute_momentum_score(closes)
                q_score   = round(compute_quality_score(pred["confidence"], None, mom_score), 1)
                rsi       = compute_rsi(stock_data["prices"])

                # Derive trend from SMA crossover
                sma5  = sum(closes[:5])  / 5  if len(closes) >= 5  else None
                sma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else None
                trend = "Uptrend" if (sma5 and sma20 and sma5 > sma20) else "Downtrend"

                indices_out[sym] = {
                    "symbol":         sym,
                    "name":           INDEX_NAMES.get(sym, sym),
                    "price":          stock_data["price"],
                    "change":         stock_data["change"],
                    "change_percent": stock_data["change_percent"],
                    "direction":      pred["direction"],
                    "prediction":     pred["prediction"],
                    "confidence":     pred["confidence"],
                    "quality_score":  q_score,
                    "rating":         quality_score_to_label(q_score, pred["direction"]),
                    "indicators":     {"rsi": rsi},
                    "signals": {
                        "rsi":   "Overbought" if rsi and rsi > 70 else "Oversold" if rsi and rsi < 30 else "Neutral",
                        "trend": trend,
                    },
                }

            if vix_data:
                indices_out[VIX_DISPLAY] = vix_data

            for sym in SECTOR_SYMBOLS:
                stock_data = price_results.get(sym)
                if not stock_data:
                    continue
                closes    = [p["close"] for p in stock_data["prices"]]
                pred      = predict_ticker(stock_data)
                mom_score = compute_momentum_score(closes)
                q_score   = round(compute_quality_score(pred["confidence"], None, mom_score), 1)
                rsi       = compute_rsi(stock_data["prices"])
                perfs     = compute_sector_perfs(stock_data["prices"])

                sma5  = sum(closes[:5])  / 5  if len(closes) >= 5  else None
                sma20 = sum(closes[:20]) / 20 if len(closes) >= 20 else None
                trend = "Uptrend" if (sma5 and sma20 and sma5 > sma20) else "Downtrend"

                sectors_out[sym] = {
                    "symbol":         sym,
                    "sector_name":    SECTOR_NAMES[sym],
                    "price":          stock_data["price"],
                    "change":         stock_data["change"],
                    "change_percent": stock_data["change_percent"],
                    "direction":      pred["direction"],
                    "prediction":     pred["prediction"],
                    "confidence":     pred["confidence"],
                    "quality_score":  q_score,
                    "rating":         quality_score_to_label(q_score, pred["direction"]),
                    "perf_1m":        perfs["perf_1m"],
                    "perf_3m":        perfs["perf_3m"],
                    "indicators":     {"rsi": rsi},
                    "signals": {
                        "rsi":   "Overbought" if rsi and rsi > 70 else "Oversold" if rsi and rsi < 30 else "Neutral",
                        "trend": trend,
                    },
                }

            # Dominant sector = highest quality_score among sectors
            dominant = None
            if sectors_out:
                best_sym = max(sectors_out, key=lambda s: sectors_out[s]["quality_score"])
                best = sectors_out[best_sym]
                dominant = {
                    "symbol":      best_sym,
                    "sector_name": best["sector_name"],
                    "direction":   best["direction"],
                    "quality_score": best["quality_score"],
                }

            self._respond(200, {
                "generated_at":   datetime.utcnow().strftime("%Y-%m-%d"),
                "indices":        indices_out,
                "sectors":        sectors_out,
                "dominant_sector": dominant,
            }, sec_headers)

        except Exception as e:
            self._respond(500, {"error": sanitize_error(500, exc=e)}, sec_headers)

    def _respond(self, status, data, sec_headers):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in sec_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        request_origin = self.headers.get("Origin")
        headers = get_cors_preflight_headers(request_origin)
        self.send_response(200)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
