"""
Stock Analysis API Endpoint - All-in-one for Vercel Serverless
Uses Yahoo Finance direct HTTP API (no heavy dependencies)
"""
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

# Yahoo Finance API endpoints
YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_QUOTE_SUMMARY = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============ HELPER FUNCTIONS ============
def safe_float(value):
    """Extract raw value from Yahoo Finance nested objects or plain values."""
    try:
        if value is None:
            return None
        # Handle nested objects with 'raw' key
        if isinstance(value, dict):
            return float(value.get("raw")) if value.get("raw") is not None else None
        return float(value) if value and str(value) != "None" else None
    except (ValueError, TypeError):
        return None

def safe_get(data, *keys, default=None):
    """Safely get nested dictionary values."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default

# ============ STOCK DATA FUNCTIONS ============
def get_daily_prices(symbol, range_period="3mo"):
    """Fetch daily OHLCV data using Yahoo Finance chart API."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": range_period, "interval": "1d", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        
        error = safe_get(data, "chart", "error")
        if error:
            return {"error": error.get("description", "Unknown error")}
        
        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return {"error": f"No data found for {symbol}"}
        
        result = result[0]
        timestamps = result.get("timestamp", [])
        quote = safe_get(result, "indicators", "quote", default=[{}])[0]
        
        if not timestamps:
            return {"error": f"No price data for {symbol}"}
        
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
        
        # Return newest first
        prices.reverse()
        return {"symbol": symbol, "prices": prices}
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}

def get_company_overview(symbol):
    """Fetch company fundamentals using Yahoo Finance quoteSummary API."""
    try:
        url = YF_QUOTE_SUMMARY.format(symbol=symbol)
        params = {"modules": "summaryProfile,defaultKeyStatistics,financialData,price,summaryDetail"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        
        result = safe_get(data, "quoteSummary", "result")
        if not result or len(result) == 0:
            return {"error": "Company data not found", "symbol": symbol, "name": symbol}
        
        result = result[0]
        profile = result.get("summaryProfile", {})
        stats = result.get("defaultKeyStatistics", {})
        financial = result.get("financialData", {})
        price_data = result.get("price", {})
        summary = result.get("summaryDetail", {})
        
        # Extract name
        name = safe_get(price_data, "shortName") or safe_get(price_data, "longName") or symbol
        
        return {
            "symbol": symbol,
            "name": name,
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "pe_ratio": safe_float(summary.get("trailingPE")) or safe_float(financial.get("trailingPE")) or safe_float(stats.get("trailingPE")),
            "forward_pe": safe_float(summary.get("forwardPE")) or safe_float(stats.get("forwardPE")),
            "eps": safe_float(summary.get("trailingEps")) or safe_float(financial.get("trailingEps")),
            "roe": safe_float(financial.get("returnOnEquity")),
            "market_cap": safe_float(price_data.get("marketCap")),
            "dividend_yield": safe_float(summary.get("dividendYield")) or safe_float(stats.get("yield")),
            "52_week_high": safe_float(summary.get("fiftyTwoWeekHigh")),
            "52_week_low": safe_float(summary.get("fiftyTwoWeekLow")),
            "beta": safe_float(summary.get("beta")) or safe_float(stats.get("beta")),
            "profit_margin": safe_float(financial.get("profitMargins")),
        }
    except Exception as e:
        return {"error": f"Failed to fetch company data: {str(e)}", "symbol": symbol, "name": symbol}

def get_quote(symbol):
    """Fetch current quote using Yahoo Finance chart API."""
    try:
        url = YF_CHART_URL.format(symbol=symbol)
        params = {"range": "1d", "interval": "1m", "includePrePost": "false"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        
        result = safe_get(data, "chart", "result")
        if not result or len(result) == 0:
            return {"error": "Quote not found"}
        
        meta = result[0].get("meta", {})
        
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        
        if price is None:
            return {"error": "Quote not found"}
        
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "symbol": symbol,
            "price": round(float(price), 2),
            "change": round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "volume": int(meta.get("regularMarketVolume", 0)),
            "latest_trading_day": datetime.utcfromtimestamp(meta.get("regularMarketTime", 0)).strftime("%Y-%m-%d") if meta.get("regularMarketTime") else None
        }
    except Exception as e:
        return {"error": f"Failed to fetch quote: {str(e)}"}

# ============ TECHNICAL INDICATORS ============
def calculate_sma(prices, period):
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
    if len(prices) < period:
        return [None] * len(prices)
    multiplier = 2 / (period + 1)
    ema = [None] * (period - 1)
    ema.append(np.mean(prices[:period]))
    for i in range(period, len(prices)):
        ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return [None] * len(prices)
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
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
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = []
    for i in range(len(prices)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])
    valid_macd = [x for x in macd_line if x is not None]
    if len(valid_macd) < signal:
        return {"macd_line": macd_line, "signal_line": [None]*len(prices), "histogram": [None]*len(prices)}
    signal_ema = calculate_ema(valid_macd, signal)
    signal_line = [None] * (len(prices) - len(signal_ema)) + signal_ema
    histogram = []
    for i in range(len(prices)):
        if macd_line[i] is None or signal_line[i] is None:
            histogram.append(None)
        else:
            histogram.append(macd_line[i] - signal_line[i])
    return {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram}

def calculate_bollinger(prices, period=20, std_dev=2.0):
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
    if not price_data or len(price_data) < 26:
        return {"error": "Insufficient data"}
    closes = [p["close"] for p in reversed(price_data)]
    volumes = [p["volume"] for p in reversed(price_data)]
    
    sma_20 = calculate_sma(closes, 20)
    sma_50 = calculate_sma(closes, 50)
    ema_12 = calculate_ema(closes, 12)
    ema_26 = calculate_ema(closes, 26)
    rsi = calculate_rsi(closes, 14)
    macd = calculate_macd(closes)
    bollinger = calculate_bollinger(closes)
    obv = calculate_obv(closes, volumes)
    
    latest = len(closes) - 1
    get = lambda arr: arr[latest] if arr[latest] is not None else None
    
    current_price = closes[latest]
    latest_rsi = get(rsi)
    latest_macd = get(macd["macd_line"])
    latest_signal = get(macd["signal_line"])
    latest_upper = get(bollinger["upper"])
    latest_lower = get(bollinger["lower"])
    latest_sma_20 = get(sma_20)
    latest_sma_50 = get(sma_50)
    
    # Signals
    rsi_signal = "Overbought" if latest_rsi and latest_rsi > 70 else "Oversold" if latest_rsi and latest_rsi < 30 else "Neutral"
    macd_signal = "Bullish" if latest_macd and latest_signal and latest_macd > latest_signal else "Bearish" if latest_macd and latest_signal else "N/A"
    
    if latest_upper and latest_lower:
        bw = latest_upper - latest_lower
        pos = (current_price - latest_lower) / bw if bw > 0 else 0.5
        bb_signal = "Near Upper Band" if pos > 0.8 else "Near Lower Band" if pos < 0.2 else "Within Bands"
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
            "sma_20": round(latest_sma_20, 2) if latest_sma_20 else None,
            "sma_50": round(latest_sma_50, 2) if latest_sma_50 else None,
            "ema_12": round(get(ema_12), 2) if get(ema_12) else None,
            "ema_26": round(get(ema_26), 2) if get(ema_26) else None,
            "rsi": round(latest_rsi, 2) if latest_rsi else None,
            "macd": round(latest_macd, 4) if latest_macd else None,
            "macd_signal": round(latest_signal, 4) if latest_signal else None,
            "macd_histogram": round(get(macd["histogram"]), 4) if get(macd["histogram"]) else None,
            "bollinger_upper": round(latest_upper, 2) if latest_upper else None,
            "bollinger_middle": round(get(bollinger["middle"]), 2) if get(bollinger["middle"]) else None,
            "bollinger_lower": round(latest_lower, 2) if latest_lower else None,
            "obv": get(obv)
        },
        "signals": {"rsi": rsi_signal, "macd": macd_signal, "bollinger": bb_signal, "trend": trend},
        "chart_data": {
            "dates": [p["date"] for p in price_data][:60],
            "closes": [p["close"] for p in price_data][:60],
            "sma_20": list(reversed(sma_20))[:60],
            "bollinger_upper": list(reversed(bollinger["upper"]))[:60],
            "bollinger_lower": list(reversed(bollinger["lower"]))[:60],
        }
    }

# ============ ML PREDICTION ============
def train_and_predict(price_data, fundamentals=None):
    if len(price_data) < 50:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Need 50+ days of data"}
    
    prices = list(reversed(price_data))
    features, labels = [], []
    lookback = 5
    
    for i in range(lookback, len(prices) - 5):
        row = []
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                ret = (prices[idx]["close"] - prices[idx-1]["close"]) / prices[idx-1]["close"]
                vol = (prices[idx]["volume"] - prices[idx-1]["volume"]) / max(prices[idx-1]["volume"], 1)
                hl = (prices[idx]["high"] - prices[idx]["low"]) / prices[idx]["close"]
                row.extend([ret, vol, hl])
        
        hi = max(p["high"] for p in prices[i-lookback:i+1])
        lo = min(p["low"] for p in prices[i-lookback:i+1])
        pos = (prices[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5
        row.append(pos)
        
        gains, losses = [], []
        for j in range(1, min(15, i + 1)):
            chg = prices[i-j+1]["close"] - prices[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100/(1+rs)) / 100)
        
        if i >= 20:
            sma10 = np.mean([p["close"] for p in prices[i-9:i+1]])
            sma20 = np.mean([p["close"] for p in prices[i-19:i+1]])
            row.append(1 if sma10 > sma20 else 0)
        else:
            row.append(0.5)
        
        features.append(row)
        fut_ret = (prices[i+5]["close"] - prices[i]["close"]) / prices[i]["close"]
        labels.append(1 if fut_ret > 0 else 0)
    
    if len(features) < 20:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Not enough training data"}
    
    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred = np.array(features[-1:])
    
    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {"prediction": "Insufficient Variety", "confidence": 0, "direction": "neutral", "reasoning": "Data lacks variety"}
    
    model = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_split=5, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)
    
    pred = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf = max(proba)
    
    if pred == 1:
        direction = "bullish"
        text = "Strong Buy Signal" if conf > 0.7 else "Moderate Buy Signal" if conf > 0.55 else "Weak Buy Signal"
    else:
        direction = "bearish"
        text = "Strong Sell Signal" if conf > 0.7 else "Moderate Sell Signal" if conf > 0.55 else "Weak Sell Signal"
    
    note = ""
    if fundamentals:
        pe, roe = fundamentals.get("pe_ratio"), fundamentals.get("roe")
        if pe and roe and pe < 20 and roe > 0.10:
            note = " Fundamentals appear strong."
        elif pe and pe > 35:
            note = " High P/E may indicate overvaluation."
    
    return {
        "prediction": text,
        "confidence": round(conf * 100, 1),
        "direction": direction,
        "reasoning": f"Based on momentum, volume, and trend patterns.{note}",
        "model_accuracy": round(model.score(X_train, y_train) * 100, 1)
    }

# ============ API HANDLER ============
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get('symbol', [''])[0].upper()
        
        if not symbol:
            self._respond(400, {"error": "Missing symbol parameter"})
            return
        
        try:
            prices = get_daily_prices(symbol)
            if "error" in prices:
                self._respond(400, {"error": prices["error"], "symbol": symbol})
                return
            
            fundamentals = get_company_overview(symbol)
            quote = get_quote(symbol)
            indicators = calculate_all_indicators(prices["prices"])
            prediction = train_and_predict(prices["prices"], fundamentals)
            
            self._respond(200, {
                "symbol": symbol,
                "name": fundamentals.get("name", symbol),
                "sector": fundamentals.get("sector"),
                "quote": quote,
                "indicators": indicators.get("indicators", {}),
                "signals": indicators.get("signals", {}),
                "fundamentals": {
                    "pe_ratio": fundamentals.get("pe_ratio"),
                    "forward_pe": fundamentals.get("forward_pe"),
                    "eps": fundamentals.get("eps"),
                    "roe": fundamentals.get("roe"),
                    "market_cap": fundamentals.get("market_cap"),
                    "dividend_yield": fundamentals.get("dividend_yield"),
                    "52_week_high": fundamentals.get("52_week_high"),
                    "52_week_low": fundamentals.get("52_week_low"),
                    "beta": fundamentals.get("beta"),
                    "profit_margin": fundamentals.get("profit_margin"),
                },
                "prediction": prediction,
                "chart_data": indicators.get("chart_data", {})
            })
        except Exception as e:
            self._respond(500, {"error": f"Analysis failed: {str(e)}", "symbol": symbol})
    
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
