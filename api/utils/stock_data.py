"""
Stock Data Service - yfinance API Wrapper
Fetches historical price data and company fundamentals
"""
import numpy as np
from typing import Dict, List, Any, Optional

# Use yfinance for stock data
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


def safe_float(value) -> Optional[float]:
    """Safely convert value to float, handling None and NaN."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return float(value) if value and value != "None" else None
    except (ValueError, TypeError):
        return None


def get_daily_prices(symbol: str, period: str = "3mo") -> Dict[str, Any]:
    """
    Fetch daily OHLCV data for a stock symbol using yfinance.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        period: Time period ('1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
    
    Returns:
        Dictionary with symbol and list of price data
    """
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            return {"error": f"No data found for {symbol}"}
        
        prices = []
        for date, row in hist.iterrows():
            prices.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            })
        
        # Return newest first
        prices.reverse()
        return {"symbol": symbol, "prices": prices}
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}


def get_company_overview(symbol: str) -> Dict[str, Any]:
    """
    Fetch company fundamentals including P/E, EPS, ROE using yfinance.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Dictionary with fundamental metrics
    """
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        if not info or info.get("regularMarketPrice") is None:
            return {"error": "Company data not found"}
        
        return {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "pe_ratio": safe_float(info.get("trailingPE")),
            "eps": safe_float(info.get("trailingEps")),
            "roe": safe_float(info.get("returnOnEquity")),
            "market_cap": safe_float(info.get("marketCap")),
            "dividend_yield": safe_float(info.get("dividendYield")),
            "52_week_high": safe_float(info.get("fiftyTwoWeekHigh")),
            "52_week_low": safe_float(info.get("fiftyTwoWeekLow")),
            "50_day_ma": safe_float(info.get("fiftyDayAverage")),
            "200_day_ma": safe_float(info.get("twoHundredDayAverage")),
        }
    except Exception as e:
        return {"error": f"Failed to fetch company data: {str(e)}"}


def get_quote(symbol: str) -> Dict[str, Any]:
    """
    Fetch current quote for a stock using yfinance.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Current price and change information
    """
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        
        if price is None:
            return {"error": "Quote not found"}
        
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "symbol": symbol,
            "price": float(price),
            "change": round(float(change), 2),
            "change_percent": f"{change_pct:.2f}",
            "volume": int(info.get("regularMarketVolume") or info.get("volume") or 0),
            "latest_trading_day": None
        }
    except Exception as e:
        return {"error": f"Failed to fetch quote: {str(e)}"}
