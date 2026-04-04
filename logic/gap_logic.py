# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pandas as pd
import numpy as np

class GapLogic:
    """
    Logic to detect and analyze market gaps (CME, FVG, etc.) for situational awareness.
    """
    
    def detect_cme_gaps(self, df):
        """
        Detects CME (Chicago Mercantile Exchange) style gaps.
        On 24/7 crypto data, this can be simulated by identifying 'weekend gap' gaps
        whenever there's a significant price jump from Friday 16:00 (CME close) 
        to Sunday 18:00 (CME open).
        """
        df = df.copy()
        # Ensure we have a DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            return df
            
        # We look for a jump from the close of the last candle before weekend
        # to the open of the first candle after weekend.
        # Since Binance IS 24/7, 'CME Gaps' are levels where CME price *would* have a gap.
        
        # Mark Friday 21:00 UTC (Estimated CME Close)
        friday_close = df[df.index.weekday == 4].between_time('20:00', '21:00')
        # Mark Sunday 22:00 UTC (Estimated CME Open)
        sunday_open = df[df.index.weekday == 6].between_time('22:00', '23:59')
        
        # This detection is more about identifying if a gap *existed* at the CME level.
        # For simplicity, we detect gaps between any consecutive candles > X%.
        df['gap_size'] = (df['open'] / df['close'].shift(1)) - 1
        
        return df

    def detect_fvg(self, df):
        """
        Detects Fair Value Gaps (FVG) - 3-candle inefficiency.
        Bullish FVG: Candle 1 High < Candle 3 Low (Gap in between)
        Bearish FVG: Candle 1 Low > Candle 3 High (Gap in between)
        """
        df = df.copy()
        
        # Bullish FVG
        # Candle T-2 High < Candle T Low
        bullish_fvg = (df['high'].shift(2) < df['low'])
        df['fvg_bullish'] = np.where(bullish_fvg, df['low'] - df['high'].shift(2), 0)
        
        # Bearish FVG
        # Candle T-2 Low > Candle T High
        bearish_fvg = (df['low'].shift(2) > df['high'])
        df['fvg_bearish'] = np.where(bearish_fvg, df['low'].shift(2) - df['high'], 0)
        
        # FVG Center Price (Target)
        df['fvg_target'] = np.where(
            df['fvg_bullish'] > 0, (df['high'].shift(2) + df['low']) / 2,
            np.where(df['fvg_bearish'] > 0, (df['low'].shift(2) + df['high']) / 2, np.nan)
        )
        
        return df

    def classify_gap(self, df, row_idx):
        """
        Classifies a gap at a specific index based on volume and prior trend.
        - Breakaway: Gap out of consolidation with high volume.
        - Exhaustion: Gap at the end of a trend with extreme volume.
        """
        if row_idx < 20: return "None"
        if row_idx >= len(df): return "None"
        
        row_open = float(df['open'].to_numpy()[row_idx])
        row_volume = float(df['volume'].to_numpy()[row_idx])
        prev_row_close = float(df['close'].to_numpy()[row_idx-1])

        gap_size = abs(row_open / prev_row_close - 1)
        
        if gap_size < 0.005: return "Normal"
        
        avg_vol = float(df['volume'].to_numpy()[max(0, row_idx-20):row_idx].mean())
        is_high_vol = row_volume > avg_vol * 1.5
        
        # Trend detection
        prev_idx_10 = max(0, row_idx-10)
        trend = (prev_row_close / float(df['close'].to_numpy()[prev_idx_10])) - 1
        
        if is_high_vol and abs(trend) < 0.01:
            return "Breakaway"
        elif is_high_vol and abs(trend) > 0.05:
            return "Exhaustion"
            
        return "Common"

    def evaluate_opportunity(self, df, row_idx):
        """
        Differentiates between a Real Opportunity and a Fake/Risky one.
        Returns: (conviction_score, is_opportunity, classification)
        """
        classification = self.classify_gap(df, row_idx)
        
        if classification == "None":
            return 0.0, False, "None"
            
        row_open = float(df['open'].to_numpy()[row_idx])
        row_volume = float(df['volume'].to_numpy()[row_idx])
        prev_row_close = float(df['close'].to_numpy()[row_idx-1])
        gap_size = (row_open / prev_row_close) - 1
        
        # Scoring criteria
        score = 0.0
        
        # 1. Volume Confluence
        avg_vol = float(df['volume'].to_numpy()[max(0, row_idx-20):row_idx].mean())
        vol_boost = min(1.0, (row_volume / avg_vol) / 4.0) # Cap at 4x Avg
        score += vol_boost * 0.4 # Volume is 40% of the score
        
        # 2. Trend Confluence (SMA50 Slope)
        # Assuming SMA_50 is available. If not, fallback to simple closes.
        if 'SMA_50' in df.columns:
            sma_slope = float(df['SMA_50'].diff(5).to_numpy()[row_idx])
            if (gap_size > 0 and sma_slope > 0) or (gap_size < 0 and sma_slope < 0):
                score += 0.3 # Trend alignment is 30%
        else:
            # Fallback simple trend
            prev_idx_20 = max(0, row_idx-20)
            trend_20 = (prev_row_close / float(df['close'].to_numpy()[prev_idx_20])) - 1
            if (gap_size > 0 and trend_20 > 0) or (gap_size < 0 and trend_20 < 0):
                score += 0.2
        
        # 3. Order Flow Confluence (CVD Divergence)
        if 'cvd_div' in df.columns:
            cvd_div = float(df['cvd_div'].to_numpy()[row_idx])
            if (gap_size > 0 and cvd_div == 1) or (gap_size < 0 and cvd_div == -1):
                score += 0.3 # CVD confluence is 30%
        
        # Classification overrides
        if classification == "Breakaway":
            score += 0.2 # Breakaway is inherently higher conviction
        elif classification == "Exhaustion":
            score -= 0.5 # Exhaustion is RISKY, penalize heavily
            
        conviction = max(0.0, min(1.0, score))
        is_opp = conviction >= 0.7 # High threshold for Real Opportunity
        
        return conviction, is_opp, classification
