import pandas as pd
import numpy as np

def apply_all_features(df, close_col="close"):
    df = df.copy()

    def add_macd(dt, cl, f, s, sig, suf):
        ema_f = dt[cl].ewm(span=f, adjust=False).mean()
        ema_s = dt[cl].ewm(span=s, adjust=False).mean()
        macd = ema_f - ema_s
        sv = macd.ewm(span=sig, adjust=False).mean()
        # Use .loc to avoid SettingWithCopyWarning
        dt.loc[:, f'MACD_line{suf}'] = macd
        dt.loc[:, f'MACD_hist{suf}'] = macd - sv
        dt.loc[:, f'MACD_signal{suf}'] = sv

    def add_bb(dt, cl, l, std_val, suf):
        sma = dt[cl].rolling(window=l).mean()
        dev = dt[cl].rolling(window=l).std()
        u = sma + (dev * std_val)
        lw = sma - (dev * std_val)
        bb_range = u - lw
        # Use .loc to avoid SettingWithCopyWarning
        dt.loc[:, f'BB_pct_distance{suf}'] = np.where(bb_range == 0, 0, (dt[cl] - lw) / bb_range)
        dt.loc[:, f'BB_lower{suf}'] = lw
        dt.loc[:, f'BB_upper{suf}'] = u

    # 1. Base Timeframe (1h)
    add_macd(df, close_col, 12, 26, 9, '_1h')
    add_bb(df, close_col, 20, 2, '_1h')

    # 2. Medium Timeframe Simulation (4h)
    add_macd(df, close_col, 48, 104, 36, '_4h')
    add_bb(df, close_col, 80, 2, '_4h')

    # 3. High Timeframe Simulation (1d)
    add_macd(df, close_col, 288, 624, 216, '_1d')
    add_bb(df, close_col, 480, 2, '_1d')

    # Injetar os prefixos 'feat_' para o MLBrain capturar automaticamente
    for col in df.columns:
        if ('MACD' in col or 'BB_' in col) and not col.startswith('feat_'):
            df.loc[:, f'feat_{col.lower()}'] = df[col]

    return df
