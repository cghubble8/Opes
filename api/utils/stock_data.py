"""
Stock Data Service - Yahoo Finance Direct HTTP API
Fetches historical price data and company fundamentals
"""
import requests
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

# Yahoo Finance API endpoints
YF_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YF_QUOTE_SUMMARY = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    try:
        if value is None:
            return None
        return float(value) if value and value != "None" else None
    except (ValueError, TypeError):
        return None


def get_daily_prices(symbol: str, period: str = "3mo") -> Dict[str, Any]:
    """Fetch daily OHLCV data using Yahoo Finance chart API."""
    try:
        url = YF_QUOTE_URL.format(symbol=symbol)
        params = {"range": period, "interval": "1d"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        
        if "chart" not in data or not data["chart"]["result"]:
            return {"error": f"No data found for {symbol}"}
        
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        
        if not timestamps:
            return {"error": f"No price data for {symbol}"}
        
        prices = []
        for i, ts in enumerate(timestamps):
            close = quote.get("close", [])[i]
            if close is not None:
                prices.append({
                    "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                    "open": float(quote.get("open", [])[i] or 0),
                    "high": float(quote.get("high", [])[i] or 0),
                    "low": float(quote.get("low", [])[i] or 0),
                    "close": float(close),
                    "volume": int(quote.get("volume", [])[i] or 0)
                })
        
        prices.reverse()
        return {"symbol": symbol, "prices": prices}
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}


def get_company_overview(symbol: str) -> Dict[str, Any]:
    """Fetch company fundamentals using Yahoo Finance quoteSummary API."""
    try:
        url = YF_QUOTE_SUMMARY.format(symbol=symbol)
        params = {"modules": "summaryProfile,defaultKeyStatistics,financialData,price"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        
        if "quoteSummary" not in data or not data["quoteSummary"]["result"]:
            return {"error": "Company data not found"}
        
        result = data["quoteSummary"]["result"][0]
        profile = result.get("summaryProfile", {})
        stats = result.get("defaultKeyStatistics", {})
        financial = result.get("financialData", {})
        price_data = result.get("price", {})
        
        return {
            "symbol": symbol,
            "name": price_data.get("shortName") or price_data.get("longName") or symbol,
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "pe_ratio": safe_float(stats.get("trailingPE", {}).get("raw")),
            "eps": safe_float(financial.get("trailingEps", {}).get("raw")),
            "roe": safe_float(financial.get("returnOnEquity", {}).get("raw")),
            "market_cap": safe_float(price_data.get("marketCap", {}).get("raw")),
            "dividend_yield": safe_float(stats.get("yield", {}).get("raw")),
            "52_week_high": safe_float(stats.get("fiftyTwoWeekHigh", {}).get("raw")),
            "52_week_low": safe_float(stats.get("fiftyTwoWeekLow", {}).get("raw")),
        }
    except Exception as e:
        return {"error": f"Failed to fetch company data: {str(e)}"}


def get_quote(symbol: str) -> Dict[str, Any]:
    """Fetch current quote using Yahoo Finance chart API."""
    try:
        url = YF_QUOTE_URL.format(symbol=symbol)
        params = {"range": "1d", "interval": "1m"}
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        
        if "chart" not in data or not data["chart"]["result"]:
            return {"error": "Quote not found"}
        
        meta = data["chart"]["result"][0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        
        if price is None:
            return {"error": "Quote not found"}
        
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "symbol": symbol,
            "price": float(price),
            "change": round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "volume": int(meta.get("regularMarketVolume", 0)),
        }
    except Exception as e:
        return {"error": f"Failed to fetch quote: {str(e)}"}
