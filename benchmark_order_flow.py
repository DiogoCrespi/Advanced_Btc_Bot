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
        'volume': np.random.uniform(10, 1000, rows),
        'CVD': np.random.uniform(-1000, 1000, rows).cumsum()
    }
    df = pd.DataFrame(data)
    df.index = pd.date_range("2023-01-01", periods=rows, freq="1min")
    return df

def run_benchmark():
    df = generate_dummy_data()
    logic = OrderFlowLogic()

    # Original slow method
    start = time.time()
    res1 = logic.detect_liquidity_sweep(df)
    res2 = logic.detect_cvd_divergence(res1)
    end = time.time()

    print(f"Time taken (N={len(df)}): {end-start:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()
