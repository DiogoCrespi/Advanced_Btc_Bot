import pandas as pd
import numpy as np
import os
import sys

# Adiciona o diretorio atual ao path
sys.path.append(os.getcwd())

from logic.feature_store import FeatureStore
from logic.features import TemporalEncoder

def test_feature_store():
    print("Testing FeatureStore...")
    store = FeatureStore(data_dir="tests/scratch", filename="test_history.parquet")
    
    # Create dummy data
    dates = pd.date_range("2024-01-01", periods=100, freq="h")
    df = pd.DataFrame({
        'symbol': ['BTCBRL']*100,
        'close': np.random.uniform(50000, 60000, 100),
        'volume': np.random.uniform(10, 100, 100)
    }, index=dates)
    
    # Save
    store.save_history(df)
    print("Saved 100 rows.")
    
    # Load
    loaded_df = store.load_history()
    assert len(loaded_df) == 100
    assert 'symbol' in loaded_df.columns
    print("Loaded 100 rows successfully.")
    
    # Append (Non-overlapping)
    new_dates = pd.date_range("2024-01-06", periods=50, freq="h")
    new_df = pd.DataFrame({
        'symbol': ['BTCBRL']*50,
        'close': np.random.uniform(60000, 61000, 50),
        'volume': np.random.uniform(10, 100, 50)
    }, index=new_dates)
    
    store.append_new_data(new_df)
    final_df = store.load_history()
    print(f"Final Count: {len(final_df)} (Should be 150)")
    assert len(final_df) == 150
    print("Append successful.")

def test_temporal_encoding():
    print("\nTesting TemporalEncoder...")
    dates = pd.date_range("2024-01-01 12:00:00", periods=5, freq="h")
    df = pd.DataFrame({'close': [500]*5}, index=dates)
    encoded_df = TemporalEncoder.apply(df)
    
    print("Columns:", encoded_df.columns.tolist())
    assert 'feat_hour_sin' in encoded_df.columns
    assert 'feat_dow_sin' in encoded_df.columns
    assert 'feat_month_sin' in encoded_df.columns
    print("Temporal encoding successful.")

if __name__ == "__main__":
    try:
        test_feature_store()
        test_temporal_encoding()
        print("\nALL TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
