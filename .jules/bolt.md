
## 2024-05-18 - Replacing loops and iloc with vectorized binning
**Learning:** Found a major performance bottleneck where a `for` loop combined with `iloc` was used to allocate volume to price bins when calculating the Volume Profile (Point of Control) in `logic/order_flow_logic.py`. Iterating row-by-row and accessing via `iloc` is incredibly slow in Pandas. Attempting to use `np.histogram` directly caused a discrepancy due to how it handles the rightmost bin boundary vs the original code's exact interval matching logic which excluded exactly `max_p`.
**Action:** Always prefer `np.digitize` combined with `np.bincount` instead of `np.histogram` or loops to ensure identical right-edge conditions and achieve >100x performance improvements without breaking existing edge cases.
 
## 2024-05-18 - Replacing loops and iloc with vectorized arrays in logic tools
**Learning:** Found multiple performance bottlenecks where `for` loops combined with `iloc` were used to access elements of DataFrames in backtesting tools (`tools/optimizer.py`, `tools/backtest_stat_arb.py`, `tools/time_machine_simulator.py`, `tools/backtest_cash_carry.py`). Iterating row-by-row and accessing via `iloc` is incredibly slow in Pandas and significantly impacted the speed of simulations. Pre-extracting the necessary columns into NumPy arrays using `.values` before the loop and accessing them with array indexing drastically improves performance (e.g., from ~2.5s to ~0.02s per 10k rows in `optimizer.py`).
**Action:** Always prefer pre-extracting columns to NumPy arrays using `.values` or `.to_numpy()` when iterating over Pandas DataFrames in loops to achieve >100x performance improvements without breaking existing logic. Use `float()` to cast array elements back to native types if necessary.
 
## 2024-05-18 - Replacing `.iloc` access with `.values` in logic modules
**Learning:** Found multiple places in strategy logic where single-row access via `df.iloc[-1]` or `df.iloc[row_idx]` is significantly slower than bypassing Pandas to index the underlying NumPy arrays directly via `df.values[-1]`. Additionally, when translating `.get('column', default)` onto arrays it must be rewritten safely as `df['column'].values[-1] if 'column' in df.columns else default`.
**Action:** Always prefer indexing the underlying numpy arrays over `.iloc` for scalar or single-row extractions in high-frequency/latency-sensitive logic. Always explicitly cast extracted NumPy scalar types to native Python types like `float()` to prevent downstream type or serialization errors.
 

## 2024-05-24 - DataEngine Caching and DataFrame Mutability

**Learning:** When implementing an in-memory cache that returns complex data structures like Pandas DataFrames, returning a reference to the cached object can lead to unintended mutations if downstream functions modify the DataFrame (e.g. adding indicator columns).

**Action:** Always return `df.copy()` from the cache to ensure that caller functions receive an isolated instance, preserving the integrity of the underlying cached data.

## 2024-05-24 - Replacing iterrows with numpy arrays in PerformanceAnalyzer
**Learning:** Found a severe performance bottleneck in `logic/execution/performance.py` where `pd.DataFrame.iterrows()` was used to iterate over thousands of trade records to pair buys and sells. `.iterrows()` is notoriously slow in Pandas (taking >0.6s for 10k rows vs <0.02s for alternatives).
**Action:** Always prefer pre-extracting columns to NumPy arrays using `.values` before iterating sequentially over a DataFrame for row-by-row operations. Array indexing provides a massive performance boost (~50x) without altering any existing logic.

## 2026-04-12 - Replacing nested loops with numpy stride_tricks sliding_window_view in create_labels
**Learning:** Found a major performance bottleneck where a nested `for` loop was used to iterate over a large array and its future horizon window in `logic/ml_brain.py` to generate training labels. Iterating row-by-row and repeatedly slicing/looping in Python is extremely slow. Using `np.lib.stride_tricks.sliding_window_view` to create views of the future horizon and performing vectorized boolean operations allows eliminating the loops entirely, resulting in massive performance improvements.
**Action:** Always prefer NumPy vectorized operations, such as `sliding_window_view`, over nested python `for` loops when computing trailing or forward-looking horizon metrics, ensuring identical behavior with >100x speedup.


## 2024-05-24 - Replacing pd.Series.where() and .replace() with vectorized numpy operations
**Learning:** Found a major performance bottleneck where `pd.Series.where()` and `.replace(0, np.nan)` were used extensively to clamp values (e.g., `delta.where(delta > 0, 0)`) and prevent division by zero in rolling window calculations for RSI and Bollinger Bands in `data/data_engine.py` and `logic/xaut_logic.py`. Pandas series-level operations for clamping and replacement are significantly slower than underlying numpy operations. Extracting `.values` and using `np.maximum(delta.values, 0)` and `np.where(range == 0, 0, division)` speeds up indicator generation by >3x.
**Action:** Always prefer vectorized numpy operations like `np.maximum()` and `np.where()` over Pandas scalar-friendly `.where()` and `.replace()` for conditions and clamping, especially within performance-critical loops or high-frequency technical indicator calculations.

## 2024-05-24 - Replacing nested loops with numpy vectorized slicing in array lookaheads
**Learning:** Found a major performance bottleneck in `tools/time_machine_simulator.py` where a nested `for` loop was used to look ahead in the `close_arr` to determine when Take Profit or Stop Loss conditions were hit. Iterating row-by-row in Python, especially in a nested loop simulating trading trajectories, causes O(N^2) complexity and is incredibly slow. By slicing the array (`future_closes = close_arr[j+1:]`), calculating all future returns at once vectorially (`price_rets = (future_closes / current_price) - 1.0`), and using `np.argmax()` combined with `.any()` on boolean conditions, the loop is completely eliminated. This achieves a significant speedup while preserving the exact first-hit logic.
**Action:** When simulating future conditions over an array (like Stop Loss/Take Profit hits), avoid nested Python loops. Instead, slice the remaining array, apply vectorized operations, and use `np.argmax()` to locate the first occurrence of the condition.

## 2024-05-24 - Replacing apply(pd.to_numeric) with vectorized block type conversion
**Learning:** Found a performance bottleneck where `df[cols].apply(pd.to_numeric)` was used to convert multiple columns from strings to numeric types during data ingestion in `data/data_engine.py` and various scripts. The `apply` function executes row-by-row in Python, which incurs significant overhead. Using `df[cols].astype(float)` allows Pandas to perform a vectorized block conversion, significantly bypassing Python-level loop overhead.
**Action:** Always prefer vectorized block operations like `df[cols].astype(float)` over `df[cols].apply(pd.to_numeric)` when converting large portions of a DataFrame to numeric types to achieve measurable speedups (~15% on block conversion).
