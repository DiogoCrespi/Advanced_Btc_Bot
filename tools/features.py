import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_all_features(df, close_col="close"):
    df = df.copy()

    # 1. Base Timeframe (e.g., 1h)
    macd = df.ta.macd(close=close_col, fast=12, slow=26, signal=9)
    if macd is not None:
        df['MACD_line_1h'] = macd.iloc[:, 0]
        df['MACD_hist_1h'] = macd.iloc[:, 1]
        df['MACD_signal_1h'] = macd.iloc[:, 2]

    bbands = df.ta.bbands(close=close_col, length=20, std=2)
    if bbands is not None:
        df['BB_lower_1h'] = bbands.iloc[:, 0]
        df['BB_middle_1h'] = bbands.iloc[:, 1]
        df['BB_upper_1h'] = bbands.iloc[:, 2]
        bb_range = df['BB_upper_1h'] - df['BB_lower_1h']
        df['BB_pct_distance_1h'] = np.where(bb_range == 0, 0, (df[close_col] - df['BB_lower_1h']) / bb_range)

    # 2. Medium Timeframe Simulation (e.g., 4h equivalent on 1h bars) -> multiply periods by 4
    macd_4h = df.ta.macd(close=close_col, fast=48, slow=104, signal=36)
    if macd_4h is not None:
        df['MACD_line_4h'] = macd_4h.iloc[:, 0]
        df['MACD_hist_4h'] = macd_4h.iloc[:, 1]
        df['MACD_signal_4h'] = macd_4h.iloc[:, 2]

    bbands_4h = df.ta.bbands(close=close_col, length=80, std=2)
    if bbands_4h is not None:
        df['BB_lower_4h'] = bbands_4h.iloc[:, 0]
        df['BB_middle_4h'] = bbands_4h.iloc[:, 1]
        df['BB_upper_4h'] = bbands_4h.iloc[:, 2]
        bb_range = df['BB_upper_4h'] - df['BB_lower_4h']
        df['BB_pct_distance_4h'] = np.where(bb_range == 0, 0, (df[close_col] - df['BB_lower_4h']) / bb_range)

    # 3. High Timeframe Simulation (e.g., 1d equivalent on 1h bars) -> multiply periods by 24
    macd_1d = df.ta.macd(close=close_col, fast=288, slow=624, signal=216)
    if macd_1d is not None:
        df['MACD_line_1d'] = macd_1d.iloc[:, 0]
        df['MACD_hist_1d'] = macd_1d.iloc[:, 1]
        df['MACD_signal_1d'] = macd_1d.iloc[:, 2]

    bbands_1d = df.ta.bbands(close=close_col, length=480, std=2)
    if bbands_1d is not None:
        df['BB_lower_1d'] = bbands_1d.iloc[:, 0]
        df['BB_middle_1d'] = bbands_1d.iloc[:, 1]
        df['BB_upper_1d'] = bbands_1d.iloc[:, 2]
        bb_range = df['BB_upper_1d'] - df['BB_lower_1d']
        df['BB_pct_distance_1d'] = np.where(bb_range == 0, 0, (df[close_col] - df['BB_lower_1d']) / bb_range)

    return df
