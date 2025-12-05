"""
Machine Learning Model for Stock Prediction
Uses Random Forest to predict price direction based on technical indicators
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from typing import Dict, List, Any, Tuple


def prepare_features(price_data: List[Dict[str, Any]], lookback: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare features for ML model from price data.
    Features include price changes, volume changes, and technical patterns.
    
    Args:
        price_data: List of price dictionaries (newest first)
        lookback: Number of days to use for feature engineering
    
    Returns:
        Tuple of (features, labels) arrays
    """
    if len(price_data) < lookback + 6:
        return None, None
    
    # Reverse to get chronological order
    prices = list(reversed(price_data))
    
    features = []
    labels = []
    
    for i in range(lookback, len(prices) - 5):
        # Extract features from lookback period
        feature_row = []
        
        # Price momentum features
        for j in range(lookback):
            idx = i - j
            if idx > 0:
                # Daily return
                daily_return = (prices[idx]["close"] - prices[idx-1]["close"]) / prices[idx-1]["close"]
                feature_row.append(daily_return)
                
                # Volume change
                if prices[idx-1]["volume"] > 0:
                    vol_change = (prices[idx]["volume"] - prices[idx-1]["volume"]) / prices[idx-1]["volume"]
                else:
                    vol_change = 0
                feature_row.append(vol_change)
                
                # High-low range
                hl_range = (prices[idx]["high"] - prices[idx]["low"]) / prices[idx]["close"]
                feature_row.append(hl_range)
        
        # Add current price position relative to recent range
        recent_high = max(p["high"] for p in prices[i-lookback:i+1])
        recent_low = min(p["low"] for p in prices[i-lookback:i+1])
        if recent_high != recent_low:
            price_position = (prices[i]["close"] - recent_low) / (recent_high - recent_low)
        else:
            price_position = 0.5
        feature_row.append(price_position)
        
        # Calculate simple RSI proxy
        gains = []
        losses = []
        for j in range(1, min(15, i + 1)):
            change = prices[i-j+1]["close"] - prices[i-j]["close"]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0.001
        rs = avg_gain / avg_loss
        rsi_proxy = 100 - (100 / (1 + rs))
        feature_row.append(rsi_proxy / 100)  # Normalize to 0-1
        
        # Moving average crossover signal
        if i >= 20:
            sma_10 = np.mean([p["close"] for p in prices[i-9:i+1]])
            sma_20 = np.mean([p["close"] for p in prices[i-19:i+1]])
            ma_signal = 1 if sma_10 > sma_20 else 0
            feature_row.append(ma_signal)
        else:
            feature_row.append(0.5)
        
        features.append(feature_row)
        
        # Label: 1 if price goes up in next 5 days, 0 otherwise
        future_return = (prices[i + 5]["close"] - prices[i]["close"]) / prices[i]["close"]
        labels.append(1 if future_return > 0 else 0)
    
    return np.array(features), np.array(labels)


def train_and_predict(price_data: List[Dict[str, Any]], 
                      fundamentals: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Train a Random Forest model and make prediction for current state.
    
    Args:
        price_data: Historical price data (newest first)
        fundamentals: Company fundamental data (P/E, EPS, ROE)
    
    Returns:
        Prediction with confidence and reasoning
    """
    if len(price_data) < 50:
        return {
            "prediction": "Insufficient Data",
            "confidence": 0,
            "direction": "neutral",
            "reasoning": "Need at least 50 days of price data for analysis"
        }
    
    # Prepare training data
    features, labels = prepare_features(price_data)
    
    if features is None or len(features) < 20:
        return {
            "prediction": "Insufficient Data",
            "confidence": 0,
            "direction": "neutral", 
            "reasoning": "Not enough data points for training"
        }
    
    # Split into train/test (use most recent for prediction)
    X_train = features[:-1]
    y_train = labels[:-1]
    X_predict = features[-1:].copy()  # Latest data point
    
    # Calculate class weights to handle imbalance
    n_positive = np.sum(y_train)
    n_negative = len(y_train) - n_positive
    
    if n_positive == 0 or n_negative == 0:
        return {
            "prediction": "Insufficient Variety",
            "confidence": 0,
            "direction": "neutral",
            "reasoning": "Historical data lacks variety in price movements"
        }
    
    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_split=5,
        random_state=42,
        class_weight='balanced'
    )
    
    model.fit(X_train, y_train)
    
    # Make prediction
    prediction_proba = model.predict_proba(X_predict)[0]
    prediction = model.predict(X_predict)[0]
    
    # Get confidence (probability of predicted class)
    confidence = max(prediction_proba)
    
    # Determine direction and strength
    if prediction == 1:
        direction = "bullish"
        if confidence > 0.7:
            prediction_text = "Strong Buy Signal"
        elif confidence > 0.55:
            prediction_text = "Moderate Buy Signal"
        else:
            prediction_text = "Weak Buy Signal"
    else:
        direction = "bearish"
        if confidence > 0.7:
            prediction_text = "Strong Sell Signal"
        elif confidence > 0.55:
            prediction_text = "Moderate Sell Signal"
        else:
            prediction_text = "Weak Sell Signal"
    
    # Generate reasoning based on feature importance
    feature_names = ["Returns", "Volume", "Volatility", "Price Position", "RSI", "MA Crossover"]
    importances = model.feature_importances_
    
    # Get top factors (aggregate by category since we have multiple lookback features)
    category_importance = {}
    idx = 0
    for _ in range(5):  # lookback period
        for name in ["Returns", "Volume", "Volatility"]:
            if idx < len(importances):
                category_importance[name] = category_importance.get(name, 0) + importances[idx]
                idx += 1
    
    if idx < len(importances):
        category_importance["Price Position"] = importances[idx]
        idx += 1
    if idx < len(importances):
        category_importance["RSI"] = importances[idx]
        idx += 1
    if idx < len(importances):
        category_importance["MA Trend"] = importances[idx]
    
    top_factors = sorted(category_importance.items(), key=lambda x: x[1], reverse=True)[:3]
    factor_text = ", ".join([f[0] for f in top_factors])
    
    # Include fundamentals in reasoning if available
    fundamental_note = ""
    if fundamentals:
        pe = fundamentals.get("pe_ratio")
        roe = fundamentals.get("roe")
        if pe and roe:
            if pe < 15 and roe and roe > 0.15:
                fundamental_note = " Fundamentals appear strong (low P/E, high ROE)."
            elif pe > 30:
                fundamental_note = " Note: High P/E ratio may indicate overvaluation."
    
    reasoning = f"Based on {factor_text} patterns from recent trading history.{fundamental_note}"
    
    return {
        "prediction": prediction_text,
        "confidence": round(confidence * 100, 1),
        "direction": direction,
        "reasoning": reasoning,
        "model_accuracy": round(model.score(X_train, y_train) * 100, 1)
    }
