import pandas as pd
import numpy as np
from logic.ml_brain import MLBrain
from data.data_engine import DataEngine

def check_labels():
    engine = DataEngine()
    asset = "BTCBRL"
    print(f"Checking labels for {asset}...")
    df = engine.fetch_binance_klines(asset, limit=1000)
    if df.empty:
        print("Failed to fetch data")
        return
    
    df = engine.apply_indicators(df)
    brain = MLBrain()
    
    # Simulate training process
    tp = 0.015
    sl = 0.008
    hz = 4
    
    labels = brain.create_labels(df, tp=tp, sl=sl, horizon=hz)
    
    unique, counts = np.unique(labels, return_counts=True)
    dist = dict(zip(unique, counts))
    print(f"Labels Distribution (TP={tp}, SL={sl}, HZ={hz}):")
    print(dist)
    
    # Try with longer horizon
    hz_long = 12
    labels_long = brain.create_labels(df, tp=tp, sl=sl, horizon=hz_long)
    unique_l, counts_l = np.unique(labels_long, return_counts=True)
    dist_l = dict(zip(unique_l, counts_l))
    print(f"Labels Distribution (TP={tp}, SL={sl}, HZ={hz_long}):")
    print(dist_l)

if __name__ == "__main__":
    check_labels()
