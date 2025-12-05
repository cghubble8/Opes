"""
Technical Indicators Module
Calculates various technical analysis indicators from price data
"""
import numpy as np
from typing import List, Dict, Any, Tuple


def calculate_sma(prices: List[float], period: int) -> List[float]:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return [None] * len(prices)
    
    sma = []
    for i in range(len(prices)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(np.mean(prices[i - period + 1:i + 1]))
    return sma


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return [None] * len(prices)
    
    multiplier = 2 / (period + 1)
    ema = [None] * (period - 1)
    
    # First EMA is SMA
    ema.append(np.mean(prices[:period]))
    
    for i in range(period, len(prices)):
        ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
    
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index (RSI).
    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss
    """
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


def calculate_macd(prices: List[float], 
                   fast_period: int = 12, 
                   slow_period: int = 26, 
                   signal_period: int = 9) -> Dict[str, List[float]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    MACD Line = 12-day EMA - 26-day EMA
    Signal Line = 9-day EMA of MACD Line
    Histogram = MACD Line - Signal Line
    """
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    
    macd_line = []
    for i in range(len(prices)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])
    
    # Calculate signal line (EMA of MACD)
    valid_macd = [x for x in macd_line if x is not None]
    if len(valid_macd) < signal_period:
        signal_line = [None] * len(prices)
        histogram = [None] * len(prices)
    else:
        signal_ema = calculate_ema(valid_macd, signal_period)
        
        # Align signal line with MACD line
        signal_line = [None] * (len(prices) - len(signal_ema)) + signal_ema
        
        histogram = []
        for i in range(len(prices)):
            if macd_line[i] is None or signal_line[i] is None:
                histogram.append(None)
            else:
                histogram.append(macd_line[i] - signal_line[i])
    
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram
    }


def calculate_bollinger_bands(prices: List[float], 
                              period: int = 20, 
                              std_dev: float = 2.0) -> Dict[str, List[float]]:
    """
    Calculate Bollinger Bands.
    Middle Band = 20-day SMA
    Upper Band = Middle Band + (2 * 20-day standard deviation)
    Lower Band = Middle Band - (2 * 20-day standard deviation)
    """
    sma = calculate_sma(prices, period)
    
    upper_band = []
    lower_band = []
    
    for i in range(len(prices)):
        if i < period - 1:
            upper_band.append(None)
            lower_band.append(None)
        else:
            std = np.std(prices[i - period + 1:i + 1])
            upper_band.append(sma[i] + (std_dev * std))
            lower_band.append(sma[i] - (std_dev * std))
    
    return {
        "middle_band": sma,
        "upper_band": upper_band,
        "lower_band": lower_band
    }


def calculate_obv(closes: List[float], volumes: List[int]) -> List[float]:
    """
    Calculate On-Balance Volume (OBV).
    OBV adds volume on up days and subtracts on down days.
    """
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


def calculate_all_indicators(price_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate all technical indicators from price data.
    
    Args:
        price_data: List of dicts with date, open, high, low, close, volume
    
    Returns:
        Dictionary with all calculated indicators
    """
    if not price_data or len(price_data) < 26:
        return {"error": "Insufficient price data for indicator calculation"}
    
    # Extract price arrays (reverse to get oldest first for calculations)
    closes = [p["close"] for p in reversed(price_data)]
    volumes = [p["volume"] for p in reversed(price_data)]
    
    # Calculate indicators
    sma_20 = calculate_sma(closes, 20)
    sma_50 = calculate_sma(closes, 50)
    ema_12 = calculate_ema(closes, 12)
    ema_26 = calculate_ema(closes, 26)
    rsi = calculate_rsi(closes, 14)
    macd = calculate_macd(closes)
    bollinger = calculate_bollinger_bands(closes)
    obv = calculate_obv(closes, volumes)
    
    # Get the most recent values
    latest_idx = len(closes) - 1
    
    def get_latest(arr):
        return arr[latest_idx] if arr[latest_idx] is not None else None
    
    # Determine signals
    current_price = closes[latest_idx]
    
    # RSI signal
    latest_rsi = get_latest(rsi)
    if latest_rsi is not None:
        if latest_rsi > 70:
            rsi_signal = "Overbought"
        elif latest_rsi < 30:
            rsi_signal = "Oversold"
        else:
            rsi_signal = "Neutral"
    else:
        rsi_signal = "N/A"
    
    # MACD signal
    latest_macd = get_latest(macd["macd_line"])
    latest_signal = get_latest(macd["signal_line"])
    if latest_macd is not None and latest_signal is not None:
        if latest_macd > latest_signal:
            macd_signal = "Bullish"
        else:
            macd_signal = "Bearish"
    else:
        macd_signal = "N/A"
    
    # Bollinger Band position
    latest_upper = get_latest(bollinger["upper_band"])
    latest_lower = get_latest(bollinger["lower_band"])
    if latest_upper is not None and latest_lower is not None:
        band_width = latest_upper - latest_lower
        position = (current_price - latest_lower) / band_width if band_width > 0 else 0.5
        if position > 0.8:
            bb_signal = "Near Upper Band"
        elif position < 0.2:
            bb_signal = "Near Lower Band"
        else:
            bb_signal = "Within Bands"
    else:
        bb_signal = "N/A"
    
    # Moving average trend
    latest_sma_20 = get_latest(sma_20)
    latest_sma_50 = get_latest(sma_50)
    if latest_sma_20 is not None and latest_sma_50 is not None:
        if current_price > latest_sma_20 > latest_sma_50:
            ma_trend = "Strong Uptrend"
        elif current_price > latest_sma_20:
            ma_trend = "Uptrend"
        elif current_price < latest_sma_20 < latest_sma_50:
            ma_trend = "Strong Downtrend"
        elif current_price < latest_sma_20:
            ma_trend = "Downtrend"
        else:
            ma_trend = "Neutral"
    else:
        ma_trend = "N/A"
    
    return {
        "current_price": current_price,
        "indicators": {
            "sma_20": round(latest_sma_20, 2) if latest_sma_20 else None,
            "sma_50": round(latest_sma_50, 2) if latest_sma_50 else None,
            "ema_12": round(get_latest(ema_12), 2) if get_latest(ema_12) else None,
            "ema_26": round(get_latest(ema_26), 2) if get_latest(ema_26) else None,
            "rsi": round(latest_rsi, 2) if latest_rsi else None,
            "macd": round(latest_macd, 4) if latest_macd else None,
            "macd_signal": round(latest_signal, 4) if latest_signal else None,
            "macd_histogram": round(get_latest(macd["histogram"]), 4) if get_latest(macd["histogram"]) else None,
            "bollinger_upper": round(latest_upper, 2) if latest_upper else None,
            "bollinger_middle": round(get_latest(bollinger["middle_band"]), 2) if get_latest(bollinger["middle_band"]) else None,
            "bollinger_lower": round(latest_lower, 2) if latest_lower else None,
            "obv": get_latest(obv)
        },
        "signals": {
            "rsi": rsi_signal,
            "macd": macd_signal,
            "bollinger": bb_signal,
            "trend": ma_trend
        },
        "chart_data": {
            "dates": [p["date"] for p in price_data][:60],  # Last 60 days
            "closes": [p["close"] for p in price_data][:60],
            "sma_20": list(reversed(sma_20))[:60],
            "bollinger_upper": list(reversed(bollinger["upper_band"]))[:60],
            "bollinger_lower": list(reversed(bollinger["lower_band"]))[:60],
        }
    }
