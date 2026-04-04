"""
Top Stocks API Endpoint - Fetches and ranks top buy-rated stocks
Uses Yahoo Finance chart API for prices + Alpha Vantage for fundamentals
Ranks by composite quality score: fundamentals (40%) + ML (40%) + momentum (20%)
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
from utils.scoring import compute_fundamentals_score, compute_momentum_score, compute_quality_score, build_key_factors

# API Configuration
YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Watchlist with sector info
WATCHLIST = [
    {"symbol": "NVDA", "sector": "Technology"},
    {"symbol": "META", "sector": "Technology"},
    {"symbol": "AMZN", "sector": "Consumer Cyclical"},
    {"symbol": "AAPL", "sector": "Technology"},
    {"symbol": "GOOGL", "sector": "Technology"},
    {"symbol": "MSFT", "sector": "Technology"},
    {"symbol": "TSLA", "sector": "Consumer Cyclical"},
    {"symbol": "AMD", "sector": "Technology"},
    {"symbol": "NFLX", "sector": "Communication Services"},
    {"symbol": "CRM", "sector": "Technology"},
    {"symbol": "AVGO", "sector": "Technology"},
    {"symbol": "JPM", "sector": "Financial"},
    {"symbol": "WMT", "sector": "Consumer Defensive"},
    {"symbol": "UNH", "sector": "Healthcare"},
    {"symbol": "V", "sector": "Financial"},
    {"symbol": "XOM", "sector": "Energy"},
    {"symbol": "MA", "sector": "Financial"},
    {"symbol": "COST", "sector": "Consumer Cyclical"},
]

# ============ HELPERS ============

def safe_get(data, *keys, default=None):
    """Safely get nested dictionary values."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default

def safe_float(value):
    """Convert value to float safely."""
    try:
        if value is None:
            return None
        val = str(value).replace(",", "")
        return float(val) if val and val not in ("None", "-", "N/A") else None
    except (ValueError, TypeError):
        return None

# ============ DATA FETCHING ============

def get_stock_data(symbol, sector):
    """Fetch 3-month price + quote data from Yahoo Finance chart API."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1y", "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return None

        result = result[0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote = safe_get(result, "indicators", "quote", default=[{}])[0]

        if not timestamps:
            return None

        prices = []
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        for i, ts in enumerate(timestamps):
            if i < len(closes) and closes[i] is not None:
                date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                prices.append({
                    "date": date_str,
                    "open": float(opens[i]) if i < len(opens) and opens[i] else 0,
                    "high": float(highs[i]) if i < len(highs) and highs[i] else 0,
                    "low": float(lows[i]) if i < len(lows) and lows[i] else 0,
                    "close": float(closes[i]),
                    "volume": int(volumes[i]) if i < len(volumes) and volumes[i] else 0
                })

        prices.reverse()  # Newest first

        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")

        if price is None:
            return None

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol": symbol,
            "name": meta.get("shortName") or meta.get("longName") or symbol,
            "sector": sector,
            "price": round(float(price), 2),
            "change": round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "prices": prices,
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def get_fundamentals(symbol):
    """Fetch company fundamentals via Yahoo Finance quoteSummary (no auth required)."""
    try:
        url = YF_SUMMARY_URL.format(symbol=symbol)
        params = {"modules": "defaultKeyStatistics,financialData,summaryDetail"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()

        result = safe_get(data, "quoteSummary", "result")
        if not result or len(result) == 0:
            return {}

        r = result[0]
        ks = r.get("defaultKeyStatistics", {})
        fd = r.get("financialData", {})
        sd = r.get("summaryDetail", {})

        return {
            "pe_ratio": safe_float(ks.get("trailingPE")),
            "forward_pe": safe_float(ks.get("forwardPE")),
            "eps": safe_float(ks.get("trailingEps")),
            "roe": safe_float(fd.get("returnOnEquity")),
            "profit_margin": safe_float(fd.get("profitMargins")),
            "market_cap": safe_float(sd.get("marketCap")),
            "beta": safe_float(ks.get("beta")),
            "dividend_yield": safe_float(sd.get("dividendYield")),
            "earnings_growth": safe_float(fd.get("earningsGrowth")),
        }
    except Exception as e:
        print(f"Fundamentals error for {symbol}: {e}")
        return {}


# ============ SCORING ============


# ============ ML PREDICTION ============

def predict_stock(stock_data, fundamentals=None):
    """Run ML prediction on stock data using Random Forest."""
    prices = stock_data["prices"]
    if len(prices) < 50:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Need more data"}

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
                hl  = (price_list[idx]["high"] - price_list[idx]["low"]) / price_list[idx]["close"]
                row.extend([ret, vol, hl])

        # Price position within 5-day range
        hi  = max(p["high"] for p in price_list[i-lookback:i+1])
        lo  = min(p["low"]  for p in price_list[i-lookback:i+1])
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
            window = [p["close"] for p in price_list[i-19:i+1]]
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

        # Rate-of-change deceleration: 5d return vs 20d run rate
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

    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {"prediction": "Neutral", "confidence": 50, "direction": "neutral", "reasoning": "Mixed market signals"}

    model = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_split=5, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)

    pred  = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf  = max(proba)

    # Neutral band: model too uncertain to call direction
    if 0.45 <= conf <= 0.55:
        direction = "neutral"
        text = "Neutral / Hold"
    elif pred == 1:
        direction = "bullish"
        text = "Strong Buy Signal" if conf > 0.7 else "Moderate Buy Signal" if conf > 0.55 else "Weak Buy Signal"
    else:
        direction = "bearish"
        text = "Strong Sell Signal" if conf > 0.7 else "Moderate Sell Signal" if conf > 0.55 else "Weak Sell Signal"

    # Derive signals from already-computed ML feature values for key factor explanations
    price_list = list(reversed(prices))
    closes_chron = [p["close"] for p in price_list]
    sma5_val  = float(np.mean(closes_chron[-5:]))  if len(closes_chron) >= 5  else None
    sma20_val = float(np.mean(closes_chron[-20:])) if len(closes_chron) >= 20 else None

    # RSI proxy (same calculation used for ML features)
    gains, losses = [], []
    for j in range(1, min(15, len(price_list))):
        chg = price_list[-j]["close"] - price_list[-j-1]["close"]
        (gains if chg > 0 else losses).append(abs(chg))
    rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
    rsi_approx = 100 - 100 / (1 + rs)

    # Bollinger %B
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
        "rsi": "Overbought" if rsi_approx > 65 else "Oversold" if rsi_approx < 35 else "Neutral",
        "macd": "N/A",
        "trend": "Uptrend" if (sma5_val and sma20_val and sma5_val > sma20_val) else "Downtrend",
        "bollinger": bb_signal,
    }
    key_factors = build_key_factors(signals, fundamentals, {"rsi": rsi_approx}, direction)

    return {
        "prediction": text,
        "confidence": round(conf * 100, 1),
        "direction": direction,
        "reasoning": key_factors["reasoning"],
        "key_factors": {"bullish": key_factors["bullish"], "bearish": key_factors["bearish"]},
    }


# ============ API HANDLER ============


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # ── Step 1: Fetch all price data in parallel (uncapped threads) ──
            price_results = {}  # symbol -> stock_data
            with ThreadPoolExecutor(max_workers=len(WATCHLIST)) as ex:
                future_to_sym = {
                    ex.submit(get_stock_data, info["symbol"], info["sector"]): info
                    for info in WATCHLIST
                }
                for future in as_completed(future_to_sym):
                    info = future_to_sym[future]
                    try:
                        data = future.result()
                        if data:
                            price_results[info["symbol"]] = data
                    except Exception:
                        pass

            # ── Step 2: Fetch all fundamentals in parallel ──
            symbols_with_data = list(price_results.keys())
            fund_results = {}  # symbol -> fundamentals dict
            with ThreadPoolExecutor(max_workers=len(symbols_with_data)) as ex:
                future_to_sym = {
                    ex.submit(get_fundamentals, sym): sym
                    for sym in symbols_with_data
                }
                for future in as_completed(future_to_sym):
                    sym = future_to_sym[future]
                    try:
                        fund_results[sym] = future.result()
                    except Exception:
                        fund_results[sym] = {}

            # ── Step 3: Score every stock (CPU-bound, no I/O) ──
            results = []
            for sym, stock_data in price_results.items():
                fund = fund_results.get(sym, {})
                prediction = predict_stock(stock_data, fund)

                if prediction["direction"] != "bullish":
                    continue

                fund_score = compute_fundamentals_score(fund)
                momentum_score = compute_momentum_score([p["close"] for p in stock_data["prices"]])
                quality_score = compute_quality_score(
                    prediction["confidence"], fund_score, momentum_score
                )

                results.append({
                    "symbol": stock_data["symbol"],
                    "name": stock_data["name"],
                    "sector": stock_data["sector"],
                    "price": stock_data["price"],
                    "change": stock_data["change"],
                    "change_percent": stock_data["change_percent"],
                    "prediction": prediction["prediction"],
                    "confidence": prediction["confidence"],
                    "direction": prediction["direction"],
                    "reasoning": prediction["reasoning"],
                    "key_factors": prediction.get("key_factors", {"bullish": [], "bearish": []}),
                    "quality_score": quality_score,
                    "fundamentals": {
                        "pe_ratio": fund.get("pe_ratio"),
                        "eps": fund.get("eps"),
                        "roe": fund.get("roe"),
                        "profit_margin": fund.get("profit_margin"),
                        "market_cap": fund.get("market_cap"),
                    } if fund else None,
                })

            # Sort by quality score, take top 5
            results.sort(key=lambda x: x["quality_score"], reverse=True)
            top_5 = results[:5]

            # Pad with best non-bullish if fewer than 5
            if len(top_5) < 5:
                already = {r["symbol"] for r in top_5}
                for sym, stock_data in price_results.items():
                    if len(top_5) >= 5:
                        break
                    if sym in already:
                        continue
                    fund = fund_results.get(sym, {})
                    prediction = predict_stock(stock_data, fund)
                    fund_score = compute_fundamentals_score(fund)
                    momentum_score = compute_momentum_score(stock_data)
                    quality_score = compute_quality_score(
                        prediction["confidence"], fund_score, momentum_score
                    )
                    top_5.append({
                        "symbol": stock_data["symbol"],
                        "name": stock_data["name"],
                        "sector": stock_data["sector"],
                        "price": stock_data["price"],
                        "change": stock_data["change"],
                        "change_percent": stock_data["change_percent"],
                        "prediction": prediction["prediction"],
                        "confidence": prediction["confidence"],
                        "direction": prediction["direction"],
                        "reasoning": prediction["reasoning"],
                        "key_factors": prediction.get("key_factors", {"bullish": [], "bearish": []}),
                        "quality_score": quality_score,
                        "fundamentals": {
                            "pe_ratio": fund.get("pe_ratio"),
                            "eps": fund.get("eps"),
                            "roe": fund.get("roe"),
                            "profit_margin": fund.get("profit_margin"),
                            "market_cap": fund.get("market_cap"),
                            "rate_limited": fund.get("rate_limited", False),
                        } if fund else None,
                    })

            self._respond(200, {"stocks": top_5})
        except Exception as e:
            self._respond(500, {"error": f"Failed to analyze stocks: {str(e)}"})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
