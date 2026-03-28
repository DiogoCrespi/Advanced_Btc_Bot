
## 2024-05-18 - Replacing loops and iloc with vectorized binning
**Learning:** Found a major performance bottleneck where a `for` loop combined with `iloc` was used to allocate volume to price bins when calculating the Volume Profile (Point of Control) in `logic/order_flow_logic.py`. Iterating row-by-row and accessing via `iloc` is incredibly slow in Pandas. Attempting to use `np.histogram` directly caused a discrepancy due to how it handles the rightmost bin boundary vs the original code's exact interval matching logic which excluded exactly `max_p`.
**Action:** Always prefer `np.digitize` combined with `np.bincount` instead of `np.histogram` or loops to ensure identical right-edge conditions and achieve >100x performance improvements without breaking existing edge cases.
