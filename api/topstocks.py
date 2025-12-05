"""
Top Stocks API Endpoint - Fetches and ranks top buy-rated stocks
Uses Yahoo Finance chart API for real-time prices (no auth required)
"""
from http.server import BaseHTTPRequestHandler
import json
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime

# Yahoo Finance chart API (no auth required)
YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Watchlist with sector info (since Yahoo quoteSummary needs auth)
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
]

def safe_get(data, *keys, default=None):
    """Safely get nested dictionary values."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
    return result if result is not None else default

def get_stock_data(symbol, sector):
    """Fetch stock data using Yahoo Finance chart API."""
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
        
        # Build price list
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
        
        # Get current price info from meta
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
    
    # Generate reasoning based on recent performance
    recent_change = (stock_data["prices"][0]["close"] - stock_data["prices"][4]["close"]) / stock_data["prices"][4]["close"] * 100
    
    reasons = []
    if direction == "bullish":
        reasons.append("Positive momentum detected")
        if recent_change > 2:
            reasons.append("strong recent gains")
    else:
        if recent_change < -2:
            reasons.append("Recent weakness observed")
    
    reasoning = ", ".join(reasons) if reasons else "Based on technical pattern analysis"
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
            
            for stock_info in WATCHLIST:
                stock_data = get_stock_data(stock_info["symbol"], stock_info["sector"])
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
            
            # If we don't have 5 bullish stocks, add some bearish ones
            if len(top_5) < 5:
                for stock_info in WATCHLIST:
                    if len(top_5) >= 5:
                        break
                    stock_data = get_stock_data(stock_info["symbol"], stock_info["sector"])
                    if stock_data and not any(r["symbol"] == stock_data["symbol"] for r in top_5):
                        prediction = predict_stock(stock_data)
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
                            "reasoning": prediction["reasoning"]
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
