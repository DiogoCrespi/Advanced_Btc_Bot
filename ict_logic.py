import pandas as pd
import numpy as np

class ICTLogic:
    def __init__(self):
        self.fresh_levels = [] # List of active Order Blocks
        self.fvgs = [] # Fair Value Gaps

    def detect_sweep(self, row, level):
        """
        Detects a 'Sweep' (Fake Breakout):
        Price breaks the level (High > Level or Low < Level) 
        but closes back within the level.
        """
        # Bullish Sweep (Liquidity grab below support)
        if row['Low'] < level and row['Close'] > level:
            return "Bullish Sweep"
        
        # Bearish Sweep (Liquidity grab above resistance)
        if row['High'] > level and row['Close'] < level:
            return "Bearish Sweep"
        
        return None

    def find_order_blocks(self, df):
        """
        Identifies Order Blocks based on strong engulfing movements.
        """
        obs = []
        for i in range(1, len(df)):
            prev_row = df.iloc[i-1]
            curr_row = df.iloc[i]
            
            # Bullish OB: Previous candle negative, current positive and strong
            if prev_row['Close'] < prev_row['Open'] and curr_row['Close'] > curr_row['Open']:
                if (curr_row['Close'] - curr_row['Open']) > (prev_row['Open'] - prev_row['Close']) * 2:
                    obs.append({
                        'type': 'bullish',
                        'top': float(prev_row['High']),
                        'bottom': float(prev_row['Low']),
                        'timestamp': df.index[i-1],
                        'mitigated': False
                    })
                    
            # Bearish OB: Previous candle positive, current negative and strong
            elif prev_row['Close'] > prev_row['Open'] and curr_row['Close'] < curr_row['Open']:
                if (curr_row['Open'] - curr_row['Close']) > (prev_row['Close'] - prev_row['Open']) * 2:
                    obs.append({
                        'type': 'bearish',
                        'top': float(prev_row['High']),
                        'bottom': float(prev_row['Low']),
                        'timestamp': df.index[i-1],
                        'mitigated': False
                    })
        return obs

    def detect_fvg(self, df):
        """
        Detects Fair Value Gaps (Internal Range Liquidity).
        """
        fvgs = []
        for i in range(2, len(df)):
            # Bullish FVG (Gap up)
            if df['Low'].iloc[i] > df['High'].iloc[i-2]:
                fvgs.append({
                    'type': 'bullish',
                    'top': float(df['Low'].iloc[i]),
                    'bottom': float(df['High'].iloc[i-2]),
                    'timestamp': df.index[i-1]
                })
            # Bearish FVG (Gap down)
            elif df['High'].iloc[i] < df['Low'].iloc[i-2]:
                fvgs.append({
                    'type': 'bearish',
                    'top': float(df['Low'].iloc[i-2]),
                    'bottom': float(df['High'].iloc[i]),
                    'timestamp': df.index[i-1]
                })
        return fvgs

    def get_erl_irl_bias(self, obs, fvgs, current_price):
        """
        Calculates bias based on ERL to IRL cycle.
        Price moves from ERL (Pools/OBs) to IRL (FVGs).
        """
        # Logic: If current price is near an ERL (OB), the target is the nearest IRL (FVG).
        bias = "Neutral"
        target = None
        
        # Simple distance logic
        for ob in obs:
            if not ob['mitigated']:
                if ob['type'] == 'bullish' and current_price <= ob['top']:
                    bias = "Bullish (ERL Rebound)"
                    # Target nearest Bearish FVG
                    for fvg in fvgs:
                        if fvg['type'] == 'bearish' and fvg['bottom'] > current_price:
                            target = fvg['bottom']
                            break
                    break
                elif ob['type'] == 'bearish' and current_price >= ob['bottom']:
                    bias = "Bearish (ERL Rebound)"
                    # Target nearest Bullish FVG
                    for fvg in fvgs:
                        if fvg['type'] == 'bullish' and fvg['top'] < current_price:
                            target = fvg['top']
                            break
                    break
        return bias, target

if __name__ == "__main__":
    # Test with mockup
    ict = ICTLogic()
    # Mock data to test OB/FVG detection
    data = {
        'Open': [100, 105, 102, 115, 120],
        'High': [106, 108, 106, 118, 125],
        'Low': [98, 104, 100, 110, 118],
        'Close': [104, 102, 110, 116, 122]
    }
    df = pd.DataFrame(data)
    obs = ict.find_order_blocks(df)
    fvgs = ict.detect_fvg(df)
    print(f"OBs Found: {obs}")
    print(f"FVGs Found: {fvgs}")
    bias, tgt = ict.get_erl_irl_bias(obs, fvgs, 112)
    print(f"Bias: {bias}, Target: {tgt}")
