
## 2024-05-18 - Replacing loops and iloc with vectorized binning
**Learning:** Found a major performance bottleneck where a `for` loop combined with `iloc` was used to allocate volume to price bins when calculating the Volume Profile (Point of Control) in `logic/order_flow_logic.py`. Iterating row-by-row and accessing via `iloc` is incredibly slow in Pandas. Attempting to use `np.histogram` directly caused a discrepancy due to how it handles the rightmost bin boundary vs the original code's exact interval matching logic which excluded exactly `max_p`.
**Action:** Always prefer `np.digitize` combined with `np.bincount` instead of `np.histogram` or loops to ensure identical right-edge conditions and achieve >100x performance improvements without breaking existing edge cases.

## 2026-03-29 - O(1) Data Access for Pandas series ends
**Learning:** Found a recurring pattern in latency-sensitive code paths (e.g. `multicore_master_bot.py`) where Pandas `.iloc[-1]` was used within loops to fetch the latest values or current price. Single element access with `.iloc` has a high overhead because it triggers Pandas indexing logic which is drastically slower than underlying Numpy array access.
**Action:** Always prefer `.values[-1]` when fetching the last element of a Pandas Series or DataFrame if the index metadata is not needed. This guarantees O(1) C-level array access speed.
