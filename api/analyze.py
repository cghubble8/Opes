"""
Main Stock Analysis API Endpoint
Combines all indicators, fundamentals, and ML prediction
"""
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stock_data import get_daily_prices, get_company_overview, get_quote
from utils.technical import calculate_all_indicators
from utils.ml_model import train_and_predict


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        symbol = params.get('symbol', [''])[0].upper()
        
        if not symbol:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Missing 'symbol' parameter. Usage: /api/analyze?symbol=AAPL"
            }).encode())
            return
        
        try:
            # Fetch all data
            price_data = get_daily_prices(symbol)
            
            if "error" in price_data:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": price_data["error"],
                    "symbol": symbol
                }).encode())
                return
            
            # Get fundamentals
            fundamentals = get_company_overview(symbol)
            
            # Get current quote
            quote = get_quote(symbol)
            
            # Calculate technical indicators
            indicators = calculate_all_indicators(price_data["prices"])
            
            # Get ML prediction
            prediction = train_and_predict(price_data["prices"], fundamentals)
            
            # Combine all analysis
            response = {
                "symbol": symbol,
                "name": fundamentals.get("name", symbol),
                "sector": fundamentals.get("sector"),
                "quote": quote,
                "indicators": indicators.get("indicators", {}),
                "signals": indicators.get("signals", {}),
                "fundamentals": {
                    "pe_ratio": fundamentals.get("pe_ratio"),
                    "eps": fundamentals.get("eps"),
                    "roe": fundamentals.get("roe"),
                    "market_cap": fundamentals.get("market_cap"),
                    "dividend_yield": fundamentals.get("dividend_yield"),
                    "52_week_high": fundamentals.get("52_week_high"),
                    "52_week_low": fundamentals.get("52_week_low"),
                },
                "prediction": prediction,
                "chart_data": indicators.get("chart_data", {})
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Analysis failed: {str(e)}",
                "symbol": symbol
            }).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
