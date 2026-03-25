import pandas as pd
import numpy as np

class OrderFlowLogic:
    def __init__(self):
        pass

    def calculate_avwap(self, df, anchor_time):
        """
        Calculates Anchored VWAP starting from a specific timestamp.
        Matemática: (Preço * Volume).cumsum() / Volume.cumsum()
        """
        df = df.copy()
        # Filter data from anchor_time onwards
        mask = df.index >= anchor_time
        anchor_df = df.loc[mask].copy()
        
        if anchor_df.empty:
            return pd.Series(index=df.index)

        # Average price = (High + Low + Close) / 3
        anchor_df['tp'] = (anchor_df['high'] + anchor_df['low'] + anchor_df['close']) / 3
        anchor_df['pv'] = anchor_df['tp'] * anchor_df['volume']
        
        anchor_df['cum_pv'] = anchor_df['pv'].cumsum()
        anchor_df['cum_vol'] = anchor_df['volume'].cumsum()
        
        anchor_df['AVWAP'] = anchor_df['cum_pv'] / anchor_df['cum_vol']
        
        return anchor_df['AVWAP'].reindex(df.index)

    def calculate_volume_profile(self, df, bins=24):
        """
        Calculates the Volume Profile and identifies the POC (Point of Control).
        """
        if df.empty:
            return None
            
        prices = df['close']
        volumes = df['volume']
        
        # Determine price range
        min_p = prices.min()
        max_p = prices.max()
        
        if min_p == max_p:
            return None
            
        # Create bins
        price_bins = np.linspace(min_p, max_p, bins + 1)
        volume_by_bin = np.zeros(bins)
        
        # Allocate volume to bins
        for i in range(len(prices)):
            p = prices.iloc[i]
            v = volumes.iloc[i]
            # Find which bin the price falls into
            bin_idx = np.digitize(p, price_bins) - 1
            if 0 <= bin_idx < bins:
                volume_by_bin[bin_idx] += v
        
        # POC is the bin with highest volume
        poc_idx = np.argmax(volume_by_bin)
        poc_price = (price_bins[poc_idx] + price_bins[poc_idx+1]) / 2
        
        return {
            'poc': poc_price,
            'bins': price_bins,
            'volumes': volume_by_bin
        }

    def detect_liquidity_sweep(self, df, lookback=20):
        """
        Detects Liquidity Sweep (SMC): 
        Price breaks the high/low of the last X candles but closes back inside.

        ⚡ Bolt Optimization: Vectorized logic using Pandas rolling windows
        to eliminate O(N) looping and improve performance significantly.
        """
        df = df.copy()
        
        # Calculate previous highs and lows using rolling window
        # shift(1) ensures we don't include the current candle in the lookback
        prev_high = df['high'].rolling(window=lookback).max().shift(1)
        prev_low = df['low'].rolling(window=lookback).min().shift(1)

        # Sweep High: price went above prev_high but closed below it
        cond_sweep_high = (df['high'] > prev_high) & (df['close'] < prev_high)
        df['sweep_high'] = np.where(cond_sweep_high, 1, 0)

        # Sweep Low: price went below prev_low but closed above it
        cond_sweep_low = (df['low'] < prev_low) & (df['close'] > prev_low)
        df['sweep_low'] = np.where(cond_sweep_low, 1, 0)
                
        return df

    def detect_cvd_divergence(self, df, lookback=5):
        """
        Detects CVD Divergence:
        Price makes a higher high, but CVD makes a lower high (Bearish).
        Price makes a lower low, but CVD makes a higher low (Bullish).

        ⚡ Bolt Optimization: Vectorized logic using Pandas diff to eliminate
        row-by-row iteration and improve efficiency for large data frames.
        """
        df = df.copy()
        
        # Calculate changes over the lookback period
        price_change = df['close'].diff(lookback)
        cvd_change = df['CVD'].diff(lookback)

        # Define conditions for divergence
        cond_bearish = (price_change > 0) & (cvd_change < 0)
        cond_bullish = (price_change < 0) & (cvd_change > 0)

        # Use np.select to assign values based on conditions
        conditions = [cond_bullish, cond_bearish]
        choices = [1, -1]

        df['cvd_div'] = np.select(conditions, choices, default=0)
                
        return df

if __name__ == "__main__":
    # Test with dummy data or real data
    from data.data_engine import DataEngine
    engine = DataEngine()
    df = engine.fetch_binance_klines("BTCUSDT", interval="1h")
    
    logic = OrderFlowLogic()
    
    # Test AVWAP (Anchor to start of day)
    today_start = df.index[-1].replace(hour=0, minute=0, second=0)
    df['AVWAP'] = logic.calculate_avwap(df, today_start)
    
    # Test Sweeps
    df = logic.detect_liquidity_sweep(df)
    
    # Test CVD Divergence
    df = logic.detect_cvd_divergence(df)
    
    # Test Volume Profile (POC)
    profile = logic.calculate_volume_profile(df.tail(24)) # last 24h
    
    print(df[['close', 'AVWAP', 'sweep_high', 'sweep_low', 'cvd_div']].tail())
    if profile:
        print(f"POC (Point of Control) last 100h: {profile['poc']:.2f}")
