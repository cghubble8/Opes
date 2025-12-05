"""
Stock Data Service - Alpha Vantage API Wrapper
Fetches historical price data and company fundamentals
"""
import requests
from typing import Dict, List, Any, Optional

API_KEY = "5IOBAC4K17O4IB39"
BASE_URL = "https://www.alphavantage.co/query"


def get_daily_prices(symbol: str, outputsize: str = "compact") -> Dict[str, Any]:
    """
    Fetch daily OHLCV data for a stock symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        outputsize: 'compact' (100 days) or 'full' (20+ years)
    
    Returns:
        Dictionary with date keys and OHLCV values
    """
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
        "apikey": API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if "Time Series (Daily)" not in data:
        error_msg = data.get("Note", data.get("Error Message", "Unknown error"))
        return {"error": error_msg}
    
    time_series = data["Time Series (Daily)"]
    
    # Convert to a cleaner format
    prices = []
    for date, values in sorted(time_series.items(), reverse=True):
        prices.append({
            "date": date,
            "open": float(values["1. open"]),
            "high": float(values["2. high"]),
            "low": float(values["3. low"]),
            "close": float(values["4. close"]),
            "volume": int(values["5. volume"])
        })
    
    return {"symbol": symbol, "prices": prices}


def get_company_overview(symbol: str) -> Dict[str, Any]:
    """
    Fetch company fundamentals including P/E, EPS, ROE.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Dictionary with fundamental metrics
    """
    params = {
        "function": "OVERVIEW",
        "symbol": symbol,
        "apikey": API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if not data or "Symbol" not in data:
        return {"error": "Company data not found"}
    
    # Extract relevant fundamental metrics
    def safe_float(value: str) -> Optional[float]:
        try:
            return float(value) if value and value != "None" else None
        except (ValueError, TypeError):
            return None
    
    fundamentals = {
        "symbol": data.get("Symbol"),
        "name": data.get("Name"),
        "sector": data.get("Sector"),
        "industry": data.get("Industry"),
        "pe_ratio": safe_float(data.get("PERatio")),
        "eps": safe_float(data.get("EPS")),
        "roe": safe_float(data.get("ReturnOnEquityTTM")),
        "market_cap": safe_float(data.get("MarketCapitalization")),
        "dividend_yield": safe_float(data.get("DividendYield")),
        "52_week_high": safe_float(data.get("52WeekHigh")),
        "52_week_low": safe_float(data.get("52WeekLow")),
        "50_day_ma": safe_float(data.get("50DayMovingAverage")),
        "200_day_ma": safe_float(data.get("200DayMovingAverage")),
    }
    
    return fundamentals


def get_quote(symbol: str) -> Dict[str, Any]:
    """
    Fetch current quote for a stock.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Current price and change information
    """
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": API_KEY
    }
    
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    
    if "Global Quote" not in data or not data["Global Quote"]:
        return {"error": "Quote not found"}
    
    quote = data["Global Quote"]
    
    return {
        "symbol": quote.get("01. symbol"),
        "price": float(quote.get("05. price", 0)),
        "change": float(quote.get("09. change", 0)),
        "change_percent": quote.get("10. change percent", "0%").replace("%", ""),
        "volume": int(quote.get("06. volume", 0)),
        "latest_trading_day": quote.get("07. latest trading day")
    }
