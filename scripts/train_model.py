import argparse
import pandas as pd
import numpy as np
import os
import sys

# Ensure project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.data_engine import DataEngine
from logic.ml_brain import MLBrain
from tools.features import apply_all_features
from sklearn.model_selection import TimeSeriesSplit

def parse_args():
    parser = argparse.ArgumentParser(description="Train MLBrain Model with Feature Selection")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Symbol to train on (e.g., BTCUSDT)")
    parser.add_argument("--epochs", type=int, default=200, help="Equivalent to n_estimators in Random Forest")
    parser.add_argument("--window-size", type=int, default=168, help="Rolling window for indicators")
    parser.add_argument("--limit", type=int, default=3000, help="Number of klines to fetch")
    return parser.parse_args()

def main():
    args = parse_args()

    print(f"[*] Starting Training Session for {args.symbol}")

    # 1. Fetch Data
    engine = DataEngine()
    print(f"[*] Fetching {args.limit} klines...")

    df_raw = engine.fetch_binance_klines(args.symbol, interval="1h", limit=args.limit)
    if df_raw.empty:
        print("[-] Failed to fetch data from Binance.")
        # Fallback to local mock data ONLY if API fails (e.g., geoblocked test environments)
        # However, as requested by code review, we will fail gracefully instead of training on random noise.
        print("[-] Exiting pipeline. Please run from a permitted IP or provide a local parquet dataset.")
        return

    # 2. Apply existing indicators
    print("[*] Applying baseline indicators...")
    df_processed = engine.apply_indicators(df_raw)

    # 3. Apply new technical features (MACD & BB Multi-Timeframe)
    # The new DataEngine apply_indicators already imports and calls apply_all_features internally
    # but we can re-apply to ensure or if running independently.

    # Initialize MLBrain with new parameters
    brain = MLBrain(n_estimators=args.epochs)

    print("[*] Preparing Features & Labels...")

    print("[*] Performing Time-Series Cross Validation & Feature Importance Analysis...")

    # Get prepared data aligned
    data = brain.prepare_features(df_processed)
    # Re-extract the feature columns dynamically
    feature_cols = [c for c in data.columns if c.startswith('feat_')]

    X_all = data[feature_cols].values
    y_all = brain.create_labels(data)

    min_len = min(len(X_all), len(y_all))
    X = X_all[:min_len]
    y = y_all[:min_len]

    if len(np.unique(y)) < 2:
        print("[-] Insufficient label diversity. Try larger limit.")
        return

    # TimeSeries Cross-Validation
    tscv = TimeSeriesSplit(n_splits=5)
    scores = []

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        brain.model.fit(X_train, y_train)
        score = brain.model.score(X_test, y_test)
        scores.append(score)
        print(f"  -> Fold {fold+1}: Accuracy = {score:.4f}")

    print(f"[*] Average CV Accuracy: {np.mean(scores):.4f}")

    # Final full training for feature importance
    brain.model.fit(X, y)
    brain.feature_cols = feature_cols
    brain.is_trained = True

    importances = brain.model.feature_importances_
    feat_importances = pd.Series(importances, index=feature_cols).sort_values(ascending=False)

    print("\n" + "="*40)
    print("📊 FEATURE IMPORTANCE RANKING")
    print("="*40)
    for feat, imp in feat_importances.items():
        print(f"{feat:25s} : {imp:.4f}")

    print("\n[*] Feature Selection: Dropping indicators with <= 0.01 predictive value")
    selected_features = feat_importances[feat_importances > 0.01].index.tolist()
    dropped_features = feat_importances[feat_importances <= 0.01].index.tolist()

    print(f"[*] Kept {len(selected_features)} features. Dropping {len(dropped_features)} features.")
    for feat in dropped_features:
        print(f"  - Dropped: {feat}")

    # Re-Train Final Model ONLY with Selected Features
    if len(selected_features) > 0:
        print("\n[*] Re-training Final Model using optimal Feature Set...")
        X_selected = data[selected_features].values[:min_len]
        brain.model.fit(X_selected, y)
        brain.feature_cols = selected_features
        brain.is_trained = True
        print("[*] Final Model Ready!")
    else:
        print("[-] All features dropped. Model invalid.")

    print("[*] Training Complete! 🚀")

if __name__ == "__main__":
    main()
