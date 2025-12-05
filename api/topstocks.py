"""
Top Stocks API Endpoint - Fetches and ranks top buy-rated stocks
Uses Yahoo Finance direct HTTP API (no heavy dependencies)
"""
from http.server import BaseHTTPRequestHandler
import json
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

# Yahoo Finance API endpoints
YF_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_QUOTE_SUMMARY = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Watchlist of popular stocks to analyze
WATCHLIST = ["NVDA", "META", "AMZN", "AAPL", "GOOGL", "MSFT", "TSLA", "AMD", "NFLX", "CRM"]

def safe_float(value):
    try:
        if value is None:
            return None
        return float(value) if value and value != "None" else None
    except (ValueError, TypeError):
        return None

def get_stock_data(symbol):
    """Fetch all required data for a stock using direct Yahoo Finance API."""
    try:
        # Get price history
        url = YF_QUOTE_URL.format(symbol=symbol)
        params = {"range": "3mo", "interval": "1d"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        
        if "chart" not in data or not data["chart"]["result"]:
            return None
        
        result = data["chart"]["result"][0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        
        if not timestamps:
            return None
        
        # Build price list
        prices = []
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])
        
        for i, ts in enumerate(timestamps):
            if closes[i] is not None:
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                prices.append({
                    "date": date_str,
                    "open": float(opens[i]) if opens[i] else 0,
                    "high": float(highs[i]) if highs[i] else 0,
                    "low": float(lows[i]) if lows[i] else 0,
                    "close": float(closes[i]),
                    "volume": int(volumes[i]) if volumes[i] else 0
                })
        
        prices.reverse()  # Newest first
        
        # Get current price info
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        # Get company name and sector
        name = meta.get("shortName") or meta.get("longName") or symbol
        
        # Try to get sector from quoteSummary
        sector = "Technology"  # Default
        try:
            summary_url = YF_QUOTE_SUMMARY.format(symbol=symbol)
            summary_params = {"modules": "summaryProfile,financialData"}
            summary_response = requests.get(summary_url, params=summary_params, headers=HEADERS, timeout=5)
            summary_data = summary_response.json()
            if "quoteSummary" in summary_data and summary_data["quoteSummary"]["result"]:
                profile = summary_data["quoteSummary"]["result"][0].get("summaryProfile", {})
                financial = summary_data["quoteSummary"]["result"][0].get("financialData", {})
                sector = profile.get("sector") or sector
                pe_ratio = safe_float(financial.get("trailingPE", {}).get("raw"))
                roe = safe_float(financial.get("returnOnEquity", {}).get("raw"))
            else:
                pe_ratio = None
                roe = None
        except:
            pe_ratio = None
            roe = None
        
        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "price": float(price),
            "change": round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "prices": prices,
            "fundamentals": {
                "pe_ratio": pe_ratio,
                "roe": roe,
            }
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def predict_stock(stock_data):
    """Run ML prediction on stock data."""
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
        return {"prediction": "Neutral", "confidence": 50, "direction": "neutral", "reasoning": "Mixed signals"}
    
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
    
    # Generate reasoning
    fundamentals = stock_data.get("fundamentals", {})
    pe = fundamentals.get("pe_ratio")
    roe = fundamentals.get("roe")
    
    reasons = []
    if direction == "bullish":
        reasons.append("Positive momentum detected")
    if pe and pe < 25:
        reasons.append("reasonable valuation")
    if roe and roe > 0.15:
        reasons.append("strong returns")
    
    reasoning = ", ".join(reasons) if reasons else "Based on technical analysis"
    reasoning = reasoning[0].upper() + reasoning[1:] + "."
    
    return {
        "prediction": text,
        "confidence": round(conf * 100, 1),
        "direction": direction,
        "reasoning": reasoning
    }

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            results = []
            
            for symbol in WATCHLIST:
                stock_data = get_stock_data(symbol)
                if stock_data:
                    prediction = predict_stock(stock_data)
                    
                    # Only include bullish predictions
                    if prediction["direction"] == "bullish":
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
                            "reasoning": prediction["reasoning"]
                        })
            
            # Sort by confidence and take top 5
            results.sort(key=lambda x: x["confidence"], reverse=True)
            top_5 = results[:5]
            
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
