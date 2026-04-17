"""
Shared scoring functions used by both analyze.py and topstocks.py.
"""
import numpy as np

# Keyword lists for news sentiment scoring (finance-tuned)
BULLISH_KEYWORDS = {
    "beat", "beats", "record", "upgrade", "upgraded", "surge", "surges", "surged",
    "growth", "raised", "profit", "profits", "profitable", "strong", "outperform",
    "outperforms", "buy", "positive", "wins", "win", "revenue", "expansion",
    "accelerate", "accelerating", "breakout", "bullish", "rally", "rallies",
    "rallied", "soar", "soars", "soared", "gain", "gains", "gained", "boost",
    "boosted", "momentum", "opportunity", "optimistic", "recovery", "rebound",
}

BEARISH_KEYWORDS = {
    "miss", "misses", "missed", "downgrade", "downgraded", "lawsuit", "layoffs",
    "recall", "recalls", "loss", "losses", "decline", "declines", "declined",
    "cuts", "cut", "weak", "negative", "warning", "warnings", "debt", "investigation",
    "selloff", "sell-off", "bearish", "plunge", "plunges", "plunged", "drop",
    "drops", "dropped", "crash", "crashes", "risk", "risks", "concern", "concerns",
    "disappointing", "disappoints", "disappoint", "hurt", "hurts", "slump",
    "slumps", "slumped", "volatile", "volatility", "penalty", "fine", "fined",
}

# Trailing PE medians by sector (2024-2025 market conditions)
SECTOR_PE_MEDIANS = {
    "Technology":             28,
    "Communication Services": 22,
    "Consumer Cyclical":      24,
    "Consumer Discretionary": 24,
    "Consumer Defensive":     20,
    "Healthcare":             22,
    "Financial":              13,
    "Financial Services":     13,
    "Energy":                 12,
    "Utilities":              16,
    "Industrials":            20,
    "Basic Materials":        15,
    "Real Estate":            35,
}

def _normalize_sector(sector):
    """Normalize Yahoo Finance sector string inconsistencies to lookup keys."""
    if not sector:
        return None
    aliases = {"Financial Services": "Financial", "Consumer Discretionary": "Consumer Cyclical"}
    return aliases.get(sector.strip(), sector.strip())


def compute_fundamentals_score(fund, sector_medians=None):
    """Score company quality from fundamentals, 0-100. Higher is better.
    sector_medians: optional dict of {sector: median_pe} to override SECTOR_PE_MEDIANS.
    """
    if not fund or "error" in fund:
        return None

    score = 50.0
    medians = sector_medians or SECTOR_PE_MEDIANS

    pe = fund.get("pe_ratio")
    earnings_growth = fund.get("earnings_growth")  # e.g. 0.15 = 15% YoY growth

    if pe is not None:
        if earnings_growth and earnings_growth > 0:
            # PEG ratio: PE / (growth rate as a percentage)
            peg = pe / (earnings_growth * 100)
            if peg < 0.5:    score += 25  # Very cheap relative to growth
            elif peg < 1.0:  score += 15  # Good value
            elif peg < 1.5:  score += 5   # Fair
            elif peg < 2.0:  score -= 5   # Somewhat expensive
            else:            score -= 15  # Expensive relative to growth
        else:
            # Fallback: sector-relative PE when growth data unavailable
            if pe <= 0:
                score -= 10
            else:
                sector_median = medians.get(_normalize_sector(fund.get("sector")))
                if sector_median:
                    ratio = pe / sector_median
                    if ratio < 0.60:   score += 20
                    elif ratio < 0.85: score += 12
                    elif ratio < 1.15: score += 3
                    elif ratio < 1.50: score -= 5
                    else:              score -= 15
                    # Forward PE tilt: bonus if forward PE signals earnings acceleration
                    forward_pe = fund.get("forward_pe")
                    if forward_pe and forward_pe > 0 and forward_pe < pe * 0.85:
                        score += 5
                else:
                    # Unknown sector: fall back to absolute PE thresholds
                    if pe < 15:    score += 20
                    elif pe < 25:  score += 10
                    elif pe < 35:  score += 0
                    else:          score -= 15

    roe = fund.get("roe")
    if roe is not None:
        if roe > 0.25:   score += 20
        elif roe > 0.15: score += 12
        elif roe > 0.08: score += 5
        elif roe < 0:    score -= 15

    pm = fund.get("profit_margin")
    if pm is not None:
        if pm > 0.20:   score += 10
        elif pm > 0.10: score += 5
        elif pm < 0:    score -= 10

    if fund.get("eps") and fund["eps"] > 0:
        score += 5

    return max(0.0, min(100.0, score))


def compute_momentum_score(closes):
    """
    Short-term momentum score 0-100.
    closes: list of close prices, newest first.
    Includes an overextension penalty when price is outside the Bollinger upper band.
    """
    if not closes or len(closes) < 20:
        return 50.0

    current = closes[0]
    sma5  = np.mean(closes[:5])
    sma20 = np.mean(closes[:20])
    std20 = np.std(closes[:20])

    score = 50.0

    if current > sma20:
        score += min(20, (current - sma20) / sma20 * 100 * 2)
    else:
        score -= min(20, (sma20 - current) / sma20 * 100 * 2)

    score += 15 if sma5 > sma20 else -10

    # Overextension penalty: price above the Bollinger upper band (2 std)
    if std20 > 0:
        upper_band = sma20 + 2 * std20
        lower_band = sma20 - 2 * std20
        if current > upper_band:
            overext = (current - upper_band) / std20
            score -= min(15, overext * 5)
        elif current < lower_band:
            score += 5  # Contrarian: near lower band

    if len(closes) >= 2:
        daily_pct = (closes[0] - closes[1]) / closes[1] * 100
        if daily_pct > 1.5:     score += 10
        elif daily_pct > 0:     score += 5
        elif daily_pct < -1.5:  score -= 10
        elif daily_pct < 0:     score -= 5

    return max(0.0, min(100.0, score))


def compute_news_sentiment_score(headlines):
    """Score a list of headlines bullish/bearish using keyword matching, returning 0-100.
    Returns None if no headlines provided.
    """
    if not headlines:
        return None
    total = 0.0
    for headline in headlines:
        words = set(headline.lower().split())
        bullish_hits = len(words & BULLISH_KEYWORDS)
        bearish_hits = len(words & BEARISH_KEYWORDS)
        # Clamp per-headline net to [-2, 2] to prevent single headlines dominating
        total += max(-2.0, min(2.0, bullish_hits - bearish_hits))
    avg = total / len(headlines)
    return max(0.0, min(100.0, 50.0 + avg * 25.0))


def compute_quality_score(ml_confidence, fund_score, momentum_score, news_score=None):
    """
    Composite quality score (0-100).
    With news: ML 33% + Fund 33% + Momentum 17% + News 17%.
    Without news: ML 40% + Fund 40% + Momentum 20% (or ML 65% + Momentum 35% if no fundamentals).
    """
    if news_score is not None and fund_score is not None:
        return round(
            ml_confidence * 0.33 + fund_score * 0.33 + momentum_score * 0.17 + news_score * 0.17,
            1,
        )
    if fund_score is None:
        return round(ml_confidence * 0.65 + momentum_score * 0.35, 1)
    return round(ml_confidence * 0.40 + fund_score * 0.40 + momentum_score * 0.20, 1)


def quality_score_to_label(score, direction):
    """Convert a quality_score to a human-readable buy/sell label."""
    if direction == "bullish":
        if score >= 70:  return "Strong Buy"
        if score >= 55:  return "Moderate Buy"
        return "Weak Buy"
    elif direction == "bearish":
        if score >= 70:  return "Strong Sell"
        if score >= 55:  return "Moderate Sell"
        return "Weak Sell"
    else:
        return "Neutral / Hold"


def build_key_factors(signals, fundamentals, indicators, direction):
    """
    Build human-readable explanations of WHY a rating was given.
    Returns {"bullish": [...], "bearish": [...], "reasoning": str}
    """
    bullish = []
    bearish = []

    # ── Technical signals ──
    rsi = indicators.get("rsi") if indicators else None
    if rsi is not None:
        if rsi < 35:
            bullish.append(f"RSI at {rsi:.0f} — oversold, potential bounce opportunity")
        elif rsi > 65:
            bearish.append(f"RSI at {rsi:.0f} — overbought, pullback risk")

    macd = indicators.get("macd") if indicators else None
    macd_signal = indicators.get("macd_signal") if indicators else None
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            bullish.append("MACD above signal line — positive momentum crossover")
        else:
            bearish.append("MACD below signal line — weakening momentum")

    trend = signals.get("trend", "") if signals else ""
    if trend in ("Strong Uptrend", "Uptrend"):
        bullish.append(f"Price in {trend.lower()} (above key moving averages)")
    elif trend in ("Downtrend", "Strong Downtrend"):
        bearish.append(f"Price in {trend.lower()} (below key moving averages)")

    bollinger = signals.get("bollinger", "") if signals else ""
    if bollinger == "Near Upper Band":
        bearish.append("Price near Bollinger upper band — may be overextended")
    elif bollinger == "Near Lower Band":
        bullish.append("Price near Bollinger lower band — potential mean-reversion setup")

    # ── Fundamental signals ──
    fund = fundamentals or {}
    pe = fund.get("pe_ratio")
    earnings_growth = fund.get("earnings_growth")
    roe = fund.get("roe")
    pm = fund.get("profit_margin")

    if pe is not None and pe > 0:
        if earnings_growth and earnings_growth > 0:
            peg = pe / (earnings_growth * 100)
            if peg < 1.0:
                bullish.append(f"PEG ratio of {peg:.2f} — undervalued relative to growth")
            elif peg > 2.0:
                bearish.append(f"PEG ratio of {peg:.2f} — expensive relative to earnings growth")
        elif pe < 15:
            bullish.append(f"Attractive valuation — P/E of {pe:.1f}")
        elif pe > 35:
            bearish.append(f"Elevated P/E of {pe:.1f} without strong earnings growth")

    if roe is not None:
        if roe > 0.20:
            bullish.append(f"Strong ROE of {roe*100:.0f}% — efficient capital deployment")
        elif roe < 0:
            bearish.append("Negative ROE — company not generating returns on equity")

    if pm is not None:
        if pm > 0.15:
            bullish.append(f"Healthy profit margin of {pm*100:.0f}%")
        elif pm < 0:
            bearish.append("Negative profit margins — profitability concern")

    # ── Build reasoning string ──
    parts = []
    if bullish:
        parts.append(bullish[0])
    if len(bullish) > 1:
        parts.append(bullish[1])
    if bearish:
        parts.append(f"note: {bearish[0].lower()}")

    if parts:
        reasoning = "; ".join(parts) + "."
        reasoning = reasoning[0].upper() + reasoning[1:]
    elif direction == "bullish":
        reasoning = "Positive momentum and technical signals support a bullish outlook."
    elif direction == "bearish":
        reasoning = "Technical and fundamental signals suggest caution."
    else:
        reasoning = "Mixed signals — insufficient conviction for a directional call."

    return {"bullish": bullish, "bearish": bearish, "reasoning": reasoning}
