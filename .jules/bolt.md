## 2024-05-18 - Avoid Pandas iloc in loops
**Learning:** Iterating over Pandas DataFrames using `iloc` in `for` loops is a severe performance bottleneck.
**Action:** Always use Pandas vectorized operations (e.g., `rolling()`, `shift()`, `diff()`, `np.where()`, `np.select()`) to maintain optimal performance.
