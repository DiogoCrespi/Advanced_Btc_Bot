import time
import pandas as pd
import numpy as np
from logic.order_flow_logic import OrderFlowLogic

def generate_dummy_data(rows=10000):
    np.random.seed(42)
    data = {
        'open': np.random.uniform(100, 200, rows),
        'high': np.random.uniform(150, 250, rows),
        'low': np.random.uniform(50, 150, rows),
        'close': np.random.uniform(100, 200, rows),
        'volume': np.random.uniform(10, 1000, rows)
    }
    df = pd.DataFrame(data)
    df['CVD'] = np.random.uniform(-1000, 1000, rows).cumsum()
    df.index = pd.date_range("2023-01-01", periods=rows, freq="1min")
    return df

def opt_detect_liquidity_sweep(df, lookback=20):
    df = df.copy()

    # Calculate rolling min/max for the lookback window, shifted by 1 so it doesn't include the current row
    prev_high = df['high'].rolling(window=lookback).max().shift(1)
    prev_low = df['low'].rolling(window=lookback).min().shift(1)

    curr_high = df['high']
    curr_low = df['low']
    curr_close = df['close']

    # Sweep High: price went above prev_high but closed below it
    sweep_high_cond = (curr_high > prev_high) & (curr_close < prev_high)
    df['sweep_high'] = np.where(sweep_high_cond, 1, 0)

    # Sweep Low: price went below prev_low but closed above it
    sweep_low_cond = (curr_low < prev_low) & (curr_close > prev_low)
    df['sweep_low'] = np.where(sweep_low_cond, 1, 0)

    # NaN handling for the first `lookback` rows to match original logic
    df.loc[df.index[:lookback], 'sweep_high'] = 0
    df.loc[df.index[:lookback], 'sweep_low'] = 0

    return df

def opt_detect_cvd_divergence(df, lookback=5):
    df = df.copy()

    price_change = df['close'] - df['close'].shift(lookback)
    cvd_change = df['CVD'] - df['CVD'].shift(lookback)

    bearish_cond = (price_change > 0) & (cvd_change < 0)
    bullish_cond = (price_change < 0) & (cvd_change > 0)

    df['cvd_div'] = np.where(bullish_cond, 1, np.where(bearish_cond, -1, 0))

    # NaN handling
    df.loc[df.index[:lookback], 'cvd_div'] = 0

    return df

def run_benchmark():
    df = generate_dummy_data()
    logic = OrderFlowLogic()

    # Original slow method
    start = time.time()
    res1 = logic.detect_liquidity_sweep(df)
    res2 = logic.detect_cvd_divergence(res1)
    end = time.time()
    print(f"Original Time taken (N={len(df)}): {end-start:.4f} seconds")

    # Optimized method
    start = time.time()
    opt_res1 = opt_detect_liquidity_sweep(df)
    opt_res2 = opt_detect_cvd_divergence(opt_res1)
    end = time.time()
    print(f"Optimized Time taken (N={len(df)}): {end-start:.4f} seconds")

    # Verify correctness
    print(f"Sweep High match: {np.array_equal(res1['sweep_high'].values, opt_res1['sweep_high'].values)}")
    print(f"Sweep Low match: {np.array_equal(res1['sweep_low'].values, opt_res1['sweep_low'].values)}")
    print(f"CVD Div match: {np.array_equal(res2['cvd_div'].values, opt_res2['cvd_div'].values)}")


if __name__ == "__main__":
    run_benchmark()
