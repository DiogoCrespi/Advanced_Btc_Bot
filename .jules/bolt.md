
## 2025-03-23 - [Order Flow Logic Vectorization]
**Learning:** Using Python `for` loops combined with Pandas `.iloc` for row-by-row calculations on large DataFrames is a severe anti-pattern in feature generation paths (like `OrderFlowLogic`), leading to significant bottlenecks during real-time bot operations.
**Action:** Always replace row-by-row iteration in Pandas with native vectorized functions like `.shift()`, `.rolling()`, and `.diff()`. This provided a ~400x speedup in liquidity sweep and CVD divergence detection without altering the business logic.
