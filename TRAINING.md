# Local Model Training Guide

This guide details the methodology, environment configuration, and execution pipeline required to train the predictive Machine Learning Engine (`MLBrain`) locally. Our system uses a specialized Random Forest architecture to classify directional market movements.

## 📊 Dataset Requirements

The Predictive Engine depends on high-quality, normalized market data. To ensure accurate feature generation and label creation, the dataset must satisfy the following criteria:

*   **Format**: `.parquet` or `.csv`
*   **Timeframe**: 1-hour (`1h`) klines/candles are standard for the current hardcoded rolling windows (e.g., 168-period for 7-day metrics).
*   **Required Features**:
    *   `open_time` (Datetime index)
    *   `open`, `high`, `low`, `close` (OHLC prices)
    *   `volume` (Total traded volume)
    *   `taker_buy_base_volume` (Required for calculating Cumulative Volume Delta - CVD)
*   **Technical Indicators** (Generated via `DataEngine`):
    *   Moving Averages (SMA_50, EMA_21)
    *   Relative Strength Index (RSI_14)
    *   Log Returns (`Log_Returns`)

## 🛠 Data Engineering Pipeline

Historical data must be fetched and processed before training. We use the `DataEngine` module to interface with the Binance Spot API.

1.  **Fetching Klines:** The `DataEngine.fetch_binance_klines(symbol, interval, limit)` method retrieves raw OHLCV and Order Flow metrics directly from the exchange.
2.  **Indicator Generation:** The `DataEngine.apply_indicators(df)` method calculates momentum and trend-following indicators.
3.  **Feature Normalization:** The `MLBrain.prepare_features(df)` method converts raw indicators into normalized, dimensionless features (e.g., `feat_dist_sma50`, `feat_volatility`, `feat_slope_ema21`) to prevent scale dominance in tree-based algorithms.

You can create an ingestion script to pull years of data:
```python
from data.data_engine import DataEngine
import pandas as pd

engine = DataEngine()
# Note: In production scripts, loop or paginate to bypass Binance limit=1000
df_raw = engine.fetch_binance_klines("BTCUSDT", interval="1h", limit=1000)
df_processed = engine.apply_indicators(df_raw)
df_processed.to_parquet("data/btc_train_data.parquet")
```

## 💻 Environment Setup

The Random Forest implementation via `scikit-learn` relies heavily on CPU parallelization. While GPU acceleration is not native to standard scikit-learn Random Forests, CPU optimization is critical.

### CPU-Optimized Training (Docker/Conda)

1.  **Create a Virtual Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
2.  **Install Dependencies**:
    Ensure you install performance-oriented libraries.
    ```bash
    pip install -r requirements.txt
    ```
3.  **Docker Setup**:
    If training inside a container, adjust your `docker-compose.yml` to allocate sufficient CPU cores for the multiprocessing pool.
    ```yaml
    deploy:
      resources:
        limits:
          cpus: '4.0'
    ```

## 🎛 Hyperparameter Tuning

Hyperparameter optimization can be executed via custom CLI scripts to find the optimal bounds for profitability and accuracy. While `scikit-learn` parameters can be modified directly in the `MLBrain` instantiation, you can expose these to your CLI wrapper:

Example CLI integration for training sessions:
```bash
python scripts/train_model.py --symbol BTCUSDT --epochs 100 --learning-rate 0.01 --window-size 168
```
*(Note: As we utilize Random Forest, the equivalent of `--epochs` corresponds to `n_estimators`, and `--window-size` dictates the horizon for indicator calculations).*

Within the `MLBrain`:
*   `n_estimators` (Default: 200) - Number of decision trees.
*   `max_depth` (Default: 12) - Limits tree depth to prevent overfitting.
*   `min_samples_leaf` (Default: 10) - Ensures robust leaf node generalization.

## 🛡️ Validation Strategy

To avoid backtesting bias and data leakage, standard K-Fold Cross-Validation is insufficient for time-series financial data.

The project strictly utilizes **Walk-Forward Validation** (also known as rolling-window validation or Time Series Split).

1.  **Temporal Integrity:** The dataset is split sequentially. The model is trained on past data (e.g., months 1-6) and validated on subsequent unseen data (month 7). This process rolls forward, mimicking live market conditions.
2.  **Embargo and Purging:** The `MLBrain.train` method explicitly implements a purge gap and embargo (`split_idx + horizon + 10`) between the training and testing sets. This ensures that overlapping labels (from the look-forward labeling horizon) do not bleed information from the test set into the training set.
3.  **Labeling:** We use a custom variation of the Triple Barrier Method (`create_labels`), which assigns classifications (-1, 0, 1) based on hitting predefined Take Profit (TP) or Stop Loss (SL) boundaries within a specific time `horizon`.

By strictly adhering to Walk-Forward Validation, the `MLBrain` provides a realistic expectation of out-of-sample performance, ensuring our Alpha generation is robust against market regime shifts.