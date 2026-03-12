"""
Top Stocks API Endpoint - Fetches and ranks top buy-rated stocks
Uses Yahoo Finance chart API for prices + Alpha Vantage for fundamentals
Ranks by composite quality score: fundamentals (40%) + ML (40%) + momentum (20%)
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

# API Configuration
YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "5IOBAC4K17O4IB39")

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
        params = {"range": "3mo", "interval": "1d", "includePrePost": "false"}
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
    """
    Fetch company fundamentals via Alpha Vantage OVERVIEW endpoint.
    Returns partial data with rate_limited=True if the API limit is hit.
    """
    try:
        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_KEY,
        }
        response = requests.get(ALPHA_VANTAGE_URL, params=params, timeout=10)
        data = response.json()

        # Rate limited or quota exceeded
        if "Note" in data or "Information" in data:
            return {"rate_limited": True}

        if not data or "Symbol" not in data:
            return {}

        return {
            "pe_ratio": safe_float(data.get("PERatio")),
            "forward_pe": safe_float(data.get("ForwardPE")),
            "eps": safe_float(data.get("EPS")),
            "roe": safe_float(data.get("ReturnOnEquityTTM")),
            "profit_margin": safe_float(data.get("ProfitMargin")),
            "market_cap": safe_float(data.get("MarketCapitalization")),
            "beta": safe_float(data.get("Beta")),
            "dividend_yield": safe_float(data.get("DividendYield")),
        }
    except Exception as e:
        print(f"Fundamentals error for {symbol}: {e}")
        return {}


# ============ SCORING ============

def compute_fundamentals_score(fund):
    """
    Score company quality from fundamentals, 0-100.
    Higher is better.
    """
    if not fund or fund.get("rate_limited"):
        return None  # Unknown — will be excluded from fundamentals weighting

    score = 50.0  # Start at neutral

    pe = fund.get("pe_ratio")
    if pe is not None:
        if pe <= 0:
            score -= 10  # Negative earnings
        elif pe < 15:
            score += 20  # Cheap
        elif pe < 25:
            score += 10  # Reasonable
        elif pe < 35:
            score += 0   # Pricey but not extreme
        else:
            score -= 15  # Expensive

    roe = fund.get("roe")
    if roe is not None:
        if roe > 0.25:
            score += 20  # Exceptional ROE
        elif roe > 0.15:
            score += 12  # Good ROE
        elif roe > 0.08:
            score += 5   # Decent ROE
        elif roe < 0:
            score -= 15  # Negative ROE

    pm = fund.get("profit_margin")
    if pm is not None:
        if pm > 0.20:
            score += 10
        elif pm > 0.10:
            score += 5
        elif pm < 0:
            score -= 10

    eps = fund.get("eps")
    if eps is not None and eps > 0:
        score += 5  # Positive EPS bonus

    return max(0.0, min(100.0, score))


def compute_momentum_score(stock_data):
    """
    Short-term momentum score 0-100 based on price action.
    Uses recent change and 5-day vs 20-day SMA position.
    """
    prices = stock_data.get("prices", [])
    if len(prices) < 20:
        return 50.0  # Unknown

    closes = [p["close"] for p in prices]
    current = closes[0]

    sma5 = np.mean(closes[:5])
    sma20 = np.mean(closes[:20])

    score = 50.0

    # Price vs SMA20
    if current > sma20:
        pct_above = (current - sma20) / sma20 * 100
        score += min(20, pct_above * 2)
    else:
        pct_below = (sma20 - current) / sma20 * 100
        score -= min(20, pct_below * 2)

    # SMA5 vs SMA20 crossover
    if sma5 > sma20:
        score += 15
    else:
        score -= 10

    # Recent daily change
    try:
        daily_change = float(stock_data["change_percent"])
        if daily_change > 1.5:
            score += 10
        elif daily_change > 0:
            score += 5
        elif daily_change < -1.5:
            score -= 10
        elif daily_change < 0:
            score -= 5
    except (ValueError, TypeError):
        pass

    return max(0.0, min(100.0, score))


def compute_quality_score(ml_confidence, fund_score, momentum_score):
    """
    Composite quality score:
      - ML confidence:    40%
      - Fundamentals:     40% (or redistributed to ML+momentum if unavailable)
      - Momentum:         20%
    """
    if fund_score is None:
        # Fundamentals unavailable — redistribute their weight
        ml_weight = 0.65
        mom_weight = 0.35
        return round(ml_confidence * ml_weight + momentum_score * mom_weight, 1)
    else:
        return round(
            ml_confidence * 0.40 +
            fund_score * 0.40 +
            momentum_score * 0.20,
            1
        )


# ============ ML PREDICTION ============

def predict_stock(stock_data, fundamentals=None):
    """Run ML prediction on stock data using Random Forest."""
    prices = stock_data["prices"]
    if len(prices) < 50:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Need more data"}

    price_list = list(reversed(prices))
    features, labels = [], []
    lookback = 5

    for i in range(lookback, len(price_list) - 5):
        row = []
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                ret = (price_list[idx]["close"] - price_list[idx-1]["close"]) / price_list[idx-1]["close"]
                vol = (price_list[idx]["volume"] - price_list[idx-1]["volume"]) / max(price_list[idx-1]["volume"], 1)
                hl = (price_list[idx]["high"] - price_list[idx]["low"]) / price_list[idx]["close"]
                row.extend([ret, vol, hl])

        hi = max(p["high"] for p in price_list[i-lookback:i+1])
        lo = min(p["low"] for p in price_list[i-lookback:i+1])
        pos = (price_list[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5
        row.append(pos)

        gains, losses = [], []
        for j in range(1, min(15, i + 1)):
            chg = price_list[i-j+1]["close"] - price_list[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100/(1+rs)) / 100)

        if i >= 20:
            sma10 = np.mean([p["close"] for p in price_list[i-9:i+1]])
            sma20 = np.mean([p["close"] for p in price_list[i-19:i+1]])
            row.append(1 if sma10 > sma20 else 0)
        else:
            row.append(0.5)

        features.append(row)
        fut_ret = (price_list[i+5]["close"] - price_list[i]["close"]) / price_list[i]["close"]
        labels.append(1 if fut_ret > 0 else 0)

    if len(features) < 20:
        return {"prediction": "Insufficient Data", "confidence": 0, "direction": "neutral", "reasoning": "Not enough data"}

    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {"prediction": "Neutral", "confidence": 50, "direction": "neutral", "reasoning": "Mixed market signals"}

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

    # Build reasoning
    recent_change = (stock_data["prices"][0]["close"] - stock_data["prices"][4]["close"]) / stock_data["prices"][4]["close"] * 100
    reasons = []
    if direction == "bullish":
        reasons.append("Positive momentum detected")
        if recent_change > 2:
            reasons.append("strong recent gains")
    else:
        if recent_change < -2:
            reasons.append("Recent weakness observed")

    # Add fundamentals note
    if fundamentals and not fundamentals.get("rate_limited"):
        pe, roe = fundamentals.get("pe_ratio"), fundamentals.get("roe")
        if pe and roe and pe < 20 and roe > 0.10:
            reasons.append("fundamentals appear strong")
        elif pe and pe > 35:
            reasons.append("note: high P/E ratio")

    reasoning = ", ".join(reasons) if reasons else "Based on technical pattern analysis"
    reasoning = reasoning[0].upper() + reasoning[1:] + "."

    return {
        "prediction": text,
        "confidence": round(conf * 100, 1),
        "direction": direction,
        "reasoning": reasoning,
    }


# ============ API HANDLER ============

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            results = []

            for stock_info in WATCHLIST:
                symbol = stock_info["symbol"]
                sector = stock_info["sector"]

                # 1. Price data from Yahoo Finance
                stock_data = get_stock_data(symbol, sector)
                if not stock_data:
                    continue

                # 2. Fundamentals from Alpha Vantage
                fund = get_fundamentals(symbol)

                # 3. ML prediction
                prediction = predict_stock(stock_data, fund)

                # Only rank bullish signals
                if prediction["direction"] != "bullish":
                    continue

                # 4. Composite quality score
                fund_score = compute_fundamentals_score(fund)
                momentum_score = compute_momentum_score(stock_data)
                quality_score = compute_quality_score(
                    prediction["confidence"],
                    fund_score,
                    momentum_score,
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

            # Sort by composite quality score (descending), take top 5
            results.sort(key=lambda x: x["quality_score"], reverse=True)
            top_5 = results[:5]

            # If fewer than 5 bullish stocks, pad with best bearish
            if len(top_5) < 5:
                for stock_info in WATCHLIST:
                    if len(top_5) >= 5:
                        break
                    if any(r["symbol"] == stock_info["symbol"] for r in top_5):
                        continue
                    stock_data = get_stock_data(stock_info["symbol"], stock_info["sector"])
                    if not stock_data:
                        continue
                    fund = get_fundamentals(stock_info["symbol"])
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
