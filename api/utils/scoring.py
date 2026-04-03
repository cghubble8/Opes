"""
Shared scoring functions used by both analyze.py and topstocks.py.
"""
import numpy as np


def compute_fundamentals_score(fund):
    """Score company quality from fundamentals, 0-100. Higher is better."""
    if not fund or "error" in fund:
        return None  # Unavailable — weight will be redistributed

    score = 50.0

    pe = fund.get("pe_ratio")
    if pe is not None:
        if pe <= 0:    score -= 10
        elif pe < 15:  score += 20
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
    """
    if not closes or len(closes) < 20:
        return 50.0

    current = closes[0]
    sma5  = np.mean(closes[:5])
    sma20 = np.mean(closes[:20])

    score = 50.0

    if current > sma20:
        score += min(20, (current - sma20) / sma20 * 100 * 2)
    else:
        score -= min(20, (sma20 - current) / sma20 * 100 * 2)

    score += 15 if sma5 > sma20 else -10

    if len(closes) >= 2:
        daily_pct = (closes[0] - closes[1]) / closes[1] * 100
        if daily_pct > 1.5:     score += 10
        elif daily_pct > 0:     score += 5
        elif daily_pct < -1.5:  score -= 10
        elif daily_pct < 0:     score -= 5

    return max(0.0, min(100.0, score))


def compute_quality_score(ml_confidence, fund_score, momentum_score):
    """
    Composite quality score:
      fundamentals 40% + ML confidence 40% + momentum 20%.
    If fundamentals are unavailable, redistributes to ML 65% + momentum 35%.
    """
    if fund_score is None:
        return round(ml_confidence * 0.65 + momentum_score * 0.35, 1)
    return round(ml_confidence * 0.40 + fund_score * 0.40 + momentum_score * 0.20, 1)


def quality_score_to_label(score, direction):
    """Convert a quality_score to a human-readable buy/sell label."""
    if direction == "bullish":
        if score >= 70:  return "Strong Buy"
        if score >= 55:  return "Moderate Buy"
        return "Weak Buy"
    else:
        if score >= 70:  return "Strong Sell"
        if score >= 55:  return "Moderate Sell"
        return "Weak Sell"
