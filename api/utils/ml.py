"""
api/utils/ml.py — Shared ML pipeline used by analyze.py and topstocks.py.

Both handlers use the same feature set, 5-fold walk-forward validation,
and RF + HistGradientBoosting voting ensemble. This is the single source of
truth for feature engineering and model training so changes are made in one place.
"""

import numpy as np
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    VotingClassifier,
)

# ── Label & prediction thresholds ────────────────────────────────────────────
LABEL_THRESHOLD    = 0.005  # >0.5% forward return → bullish label
FORWARD_WINDOW     = 5      # trading days ahead used to compute the label
NEUTRAL_BAND_LOW   = 0.45   # confidence below this = neutral direction
NEUTRAL_BAND_HIGH  = 0.55   # confidence above this = directional
CONF_STRONG        = 0.70   # threshold for "Strong" signal text
CONF_MODERATE      = 0.55   # threshold for "Moderate" signal text

# ── Walk-forward validation ───────────────────────────────────────────────────
FOLD_SPLITS = [
    (0.50, 0.60),
    (0.55, 0.65),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
]
MIN_TRAIN_SAMPLES    = 20   # minimum rows needed for a valid training fold
MIN_VAL_SAMPLES      = 5    # minimum rows needed for a valid validation fold
LOW_ACCURACY_MARGIN  = 5    # pp above majority-class baseline; below = uncertain

# ── RandomForest hyperparameters ──────────────────────────────────────────────
RF_ESTIMATORS_FINAL  = 200
RF_ESTIMATORS_VAL    = 50   # smaller tree count keeps validation folds fast
RF_MAX_DEPTH         = 7
RF_MIN_SAMPLES_SPLIT = 10   # higher = less overfitting on larger dataset
RF_RANDOM_STATE      = 42

# ── HistGradientBoosting hyperparameters ─────────────────────────────────────
HGB_MAX_ITER         = 200
HGB_MAX_DEPTH        = 6
HGB_LEARNING_RATE    = 0.05
HGB_MIN_SAMPLES_LEAF = 10

# ── Feature engineering lookback periods (trading days) ──────────────────────
LOOKBACK          = 5    # daily return/volume/HL lookback window
RSI_PERIOD        = 14
SMA_SHORT         = 10
SMA_LONG          = 20
BB_PERIOD         = 20   # Bollinger Band window (matches SMA_LONG)
BB_STD_MULT       = 2    # ±2σ bands
WEEK52_DAYS       = 252  # trading days per year; index offset = WEEK52_DAYS - 1
OBV_SLOPE_PERIOD  = 10   # OBV momentum window
ATR_SHORT_PERIOD  = 5
ATR_LONG_PERIOD   = 60   # ATR regime baseline
ATR_NORM_FACTOR   = 3    # caps ATR ratio at ~1.0 for expanded volatility
MOMENTUM_PERIOD   = 63   # quarter (Jegadeesh-Titman relative strength)
SPY_REGIME_PERIOD = 200  # SPY SMA window for market regime feature


def build_features_and_labels(price_list_chron, spy_closes=None):
    """
    Build a 25-feature matrix and binary labels from chronological OHLCV data.
    Label: 1 if FORWARD_WINDOW-day forward return > LABEL_THRESHOLD, else 0.

    Feature groups:
      - F1–F15 : LOOKBACK-day daily return, volume change, HL range (15 features)
      - F16    : Price position within LOOKBACK-day range
      - F17    : RSI proxy (normalized 0–1)
      - F18    : SMA short/long crossover signal
      - F19    : Bollinger Band %B
      - F20    : Distance from 52-week high
      - F21    : Rate-of-change deceleration
      - F22    : OBV slope divergence (tanh-scaled)
      - F23    : ATR volatility regime
      - F24    : SPY relative strength (Jegadeesh-Titman, tanh-scaled)
      - F25    : Market regime (SPY above 200-day SMA)

    Fundamentals are intentionally excluded from this feature set to avoid
    look-ahead bias — current PE/ROE/etc. cannot represent historical values
    accurately. They are used only in the rule-based scoring layer.

    Returns (features, labels, obv_series, atr_series).
    """
    features, labels = [], []

    # Precompute ATR series to avoid O(n²) recalculation in the feature loop
    atr_series = []
    for k in range(len(price_list_chron)):
        if k == 0:
            atr_series.append(price_list_chron[k]["high"] - price_list_chron[k]["low"])
        else:
            atr_series.append(max(
                price_list_chron[k]["high"] - price_list_chron[k]["low"],
                abs(price_list_chron[k]["high"] - price_list_chron[k-1]["close"]),
                abs(price_list_chron[k]["low"]  - price_list_chron[k-1]["close"]),
            ))

    # Precompute OBV series (Granville volume accumulation)
    obv_series = [price_list_chron[0]["volume"]]
    for k in range(1, len(price_list_chron)):
        if price_list_chron[k]["close"] > price_list_chron[k-1]["close"]:
            obv_series.append(obv_series[-1] + price_list_chron[k]["volume"])
        elif price_list_chron[k]["close"] < price_list_chron[k-1]["close"]:
            obv_series.append(obv_series[-1] - price_list_chron[k]["volume"])
        else:
            obv_series.append(obv_series[-1])

    for i in range(LOOKBACK, len(price_list_chron) - FORWARD_WINDOW):
        row = []

        # F1–F15: LOOKBACK-day daily return, volume change, high-low range
        for j in range(LOOKBACK):
            idx = i - j
            if idx > 0:
                ret = (price_list_chron[idx]["close"] - price_list_chron[idx-1]["close"]) / price_list_chron[idx-1]["close"]
                vol = (price_list_chron[idx]["volume"] - price_list_chron[idx-1]["volume"]) / max(price_list_chron[idx-1]["volume"], 1)
                hl  = (price_list_chron[idx]["high"]  - price_list_chron[idx]["low"])      / price_list_chron[idx]["close"]
                row.extend([ret, vol, hl])

        # F16: price position within LOOKBACK-day range (0=at low, 1=at high)
        hi = max(p["high"] for p in price_list_chron[i-LOOKBACK:i+1])
        lo = min(p["low"]  for p in price_list_chron[i-LOOKBACK:i+1])
        row.append((price_list_chron[i]["close"] - lo) / (hi - lo) if hi != lo else 0.5)

        # F17: normalized RSI proxy (0–1)
        gains, losses = [], []
        for j in range(1, RSI_PERIOD + 1):
            if i - j < 0:
                break
            chg = price_list_chron[i-j+1]["close"] - price_list_chron[i-j]["close"]
            (gains if chg > 0 else losses).append(abs(chg))
        rs = (np.mean(gains) if gains else 0) / (np.mean(losses) if losses else 0.001)
        row.append((100 - 100 / (1 + rs)) / 100)

        # F18: SMA crossover signal (1=bullish cross, 0=bearish)
        if i >= SMA_LONG:
            sma_s = np.mean([p["close"] for p in price_list_chron[i-SMA_SHORT+1:i+1]])
            sma_l = np.mean([p["close"] for p in price_list_chron[i-SMA_LONG+1:i+1]])
            row.append(1 if sma_s > sma_l else 0)
        else:
            row.append(0.5)

        # F19: Bollinger Band %B — where price sits within the bands (0=lower, 1=upper)
        if i >= BB_PERIOD:
            window         = [p["close"] for p in price_list_chron[i-BB_PERIOD+1:i+1]]
            bb_sma, bb_std = np.mean(window), np.std(window)
            if bb_std > 0:
                bb_pct = (price_list_chron[i]["close"] - (bb_sma - BB_STD_MULT * bb_std)) / (2 * BB_STD_MULT * bb_std)
                row.append(max(0.0, min(1.0, bb_pct)))
            else:
                row.append(0.5)
        else:
            row.append(0.5)

        # F20: distance from 52-week high (0=at high, higher=further below)
        window_52w = price_list_chron[max(0, i-(WEEK52_DAYS-1)):i+1]
        high_52w   = max(p["high"] for p in window_52w)
        row.append((high_52w - price_list_chron[i]["close"]) / high_52w if high_52w > 0 else 0)

        # F21: rate-of-change deceleration — LOOKBACK-day vs SMA_LONG-day return
        if i >= SMA_LONG:
            ret_5d  = (price_list_chron[i]["close"] - price_list_chron[i-LOOKBACK]["close"])  / price_list_chron[i-LOOKBACK]["close"]
            ret_20d = (price_list_chron[i]["close"] - price_list_chron[i-SMA_LONG]["close"]) / price_list_chron[i-SMA_LONG]["close"]
            row.append(ret_5d - ret_20d * LOOKBACK / SMA_LONG)
        else:
            row.append(0)

        # F22: OBV slope divergence — volume confirming or contradicting price trend
        if i >= OBV_SLOPE_PERIOD:
            obv_slope   = (obv_series[i] - obv_series[i-OBV_SLOPE_PERIOD]) / (abs(obv_series[i-OBV_SLOPE_PERIOD]) + 1)
            price_slope = (price_list_chron[i]["close"] - price_list_chron[i-OBV_SLOPE_PERIOD]["close"]) / price_list_chron[i-OBV_SLOPE_PERIOD]["close"]
            row.append(float(np.tanh(obv_slope - price_slope * 100)))
        else:
            row.append(0.0)

        # F23: ATR volatility regime — short/long ATR ratio normalized to [0, 1]
        if i >= ATR_LONG_PERIOD:
            atr_short = float(np.mean(atr_series[i-ATR_SHORT_PERIOD+1:i+1]))
            atr_long  = float(np.mean(atr_series[i-ATR_LONG_PERIOD+1:i+1]))
            row.append(min(1.0, atr_short / (atr_long + 1e-8) / ATR_NORM_FACTOR))
        else:
            row.append(0.5)

        # F24: SPY relative strength — MOMENTUM_PERIOD excess return vs market (Jegadeesh-Titman)
        if spy_closes is not None and i >= MOMENTUM_PERIOD and i < len(spy_closes) and (i - MOMENTUM_PERIOD) >= 0:
            stock_ret = (price_list_chron[i]["close"] - price_list_chron[i-MOMENTUM_PERIOD]["close"]) / price_list_chron[i-MOMENTUM_PERIOD]["close"]
            spy_ret   = (spy_closes[i] - spy_closes[i-MOMENTUM_PERIOD]) / spy_closes[i-MOMENTUM_PERIOD] if spy_closes[i-MOMENTUM_PERIOD] > 0 else 0
            row.append(float(np.tanh((stock_ret - spy_ret) * 5)))
        else:
            row.append(0.0)

        # F25: market regime — SPY above its 200-day SMA (1=bull, 0=bear)
        if spy_closes is not None and i >= SPY_REGIME_PERIOD and i < len(spy_closes):
            spy_sma200 = float(np.mean(spy_closes[i-SPY_REGIME_PERIOD:i]))
            row.append(1.0 if spy_closes[i] > spy_sma200 else 0.0)
        else:
            row.append(0.5)

        features.append(row)
        fut_ret = (price_list_chron[i+FORWARD_WINDOW]["close"] - price_list_chron[i]["close"]) / price_list_chron[i]["close"]
        labels.append(1 if fut_ret > LABEL_THRESHOLD else 0)

    return features, labels, obv_series, atr_series


def classify_direction(features, labels):
    """
    Run 5-fold expanding walk-forward validation then train a final
    RF + HistGradientBoosting soft-voting ensemble.

    Returns a prediction result dict with prediction, confidence, direction,
    model_accuracy, validation_accuracy, and low_accuracy.
    low_accuracy is True when val_accuracy falls within LOW_ACCURACY_MARGIN pp of
    the majority-class baseline — callers should surface a caveat to the user.
    """
    X_train, y_train = np.array(features[:-1]), np.array(labels[:-1])
    X_pred           = np.array(features[-1:])

    if np.sum(y_train) == 0 or np.sum(y_train) == len(y_train):
        return {
            "prediction": "Insufficient Variety", "confidence": 0,
            "direction": "neutral", "model_accuracy": None,
            "validation_accuracy": None, "low_accuracy": False,
        }

    # ── 5-fold walk-forward validation (RF only to keep folds fast) ───────────
    val_accuracy = None
    n = len(features)
    fold_accs = []
    for pct_train, pct_end in FOLD_SPLITS:
        t_end = int(n * pct_train)
        v_end = min(int(n * pct_end), n - 1)
        if t_end < MIN_TRAIN_SAMPLES or (v_end - t_end) < MIN_VAL_SAMPLES:
            continue
        X_tr_v = np.array(features[:t_end])
        y_tr_v = np.array(labels[:t_end])
        X_val  = np.array(features[t_end:v_end])
        y_val  = np.array(labels[t_end:v_end])
        if len(np.unique(y_val)) < 2 or np.sum(y_tr_v) == 0 or np.sum(y_tr_v) == len(y_tr_v):
            continue
        val_model = RandomForestClassifier(
            n_estimators=RF_ESTIMATORS_VAL, max_depth=RF_MAX_DEPTH,
            min_samples_split=RF_MIN_SAMPLES_SPLIT,
            random_state=RF_RANDOM_STATE, class_weight="balanced",
        )
        val_model.fit(X_tr_v, y_tr_v)
        fold_accs.append(val_model.score(X_val, y_val))
    if fold_accs:
        val_accuracy = round(float(np.mean(fold_accs)) * 100, 1)

    # ── Final model: soft-voting ensemble RF + HistGBM ────────────────────────
    rf = RandomForestClassifier(
        n_estimators=RF_ESTIMATORS_FINAL,
        max_depth=RF_MAX_DEPTH,
        min_samples_split=RF_MIN_SAMPLES_SPLIT,
        random_state=RF_RANDOM_STATE,
        class_weight="balanced",
    )
    hgb = HistGradientBoostingClassifier(
        max_iter=HGB_MAX_ITER,
        max_depth=HGB_MAX_DEPTH,
        learning_rate=HGB_LEARNING_RATE,
        min_samples_leaf=HGB_MIN_SAMPLES_LEAF,
        random_state=RF_RANDOM_STATE,
        class_weight="balanced",
    )
    model = VotingClassifier(
        estimators=[("rf", rf), ("hgb", hgb)],
        voting="soft",
    )
    model.fit(X_train, y_train)

    pred  = model.predict(X_pred)[0]
    proba = model.predict_proba(X_pred)[0]
    conf  = max(proba)

    if NEUTRAL_BAND_LOW <= conf <= NEUTRAL_BAND_HIGH:
        direction = "neutral"
        text = "Neutral / Hold"
    elif pred == 1:
        direction = "bullish"
        text = (
            "Strong Buy Signal"        if conf > CONF_STRONG
            else "Moderate Buy Signal" if conf > CONF_MODERATE
            else "Weak Buy Signal"
        )
    else:
        direction = "bearish"
        text = (
            "Strong Sell Signal"        if conf > CONF_STRONG
            else "Moderate Sell Signal" if conf > CONF_MODERATE
            else "Weak Sell Signal"
        )

    baseline     = max(np.mean(labels[:-1]), 1 - np.mean(labels[:-1])) * 100
    low_accuracy = val_accuracy is not None and val_accuracy < baseline + LOW_ACCURACY_MARGIN

    # Training accuracy uses only RF for speed (ensemble .score() is slow)
    rf.fit(X_train, y_train)
    train_acc = round(rf.score(X_train, y_train) * 100, 1)

    return {
        "prediction":          text,
        "confidence":          round(conf * 100, 1),
        "direction":           direction,
        "model_accuracy":      train_acc,
        "validation_accuracy": val_accuracy,
        "low_accuracy":        low_accuracy,
    }
