import numpy as np
import pandas as pd

class OrderFlowLogic:
    """
    Engine for calculating Market Microstructure features:
    - Delta (Taker Buy vs Seller Aggression)
    - CVD (Cumulative Volume Delta)
    - Volatility-adjusted Delta
    """
    
    def calculate_delta_features(self, df):
        """
        Calcula Delta e CVD a partir de dados de Kline da Binance.
        Requer as colunas 'volume' e 'taker_buy_volume'.
        """
        df = df.copy()
        
        # Colunas padrao da Binance (ajustadas pelo DataEngine)
        vol_total = df['volume']
        vol_taker_buy = df['taker_buy_volume']
        
        # 1. Delta (Net Aggression)
        # Taker Buy = Volume que agrediu o Ask (Compra)
        # Seller Aggression = Volume que agrediu o Bid (Venda)
        vol_seller_aggr = vol_total - vol_taker_buy
        df['feat_delta'] = (vol_taker_buy - vol_seller_aggr).fillna(0)
        
        # 2. CVD (Cumulative Volume Delta) - Janelas taticas (PR #61)
        # Usaremos janelas curtas para capturar momentum intra-day institucional
        df['feat_cvd_4h'] = df['feat_delta'].rolling(window=4).sum()
        df['feat_cvd_8h'] = df['feat_delta'].rolling(window=8).sum()
        
        # 3. Delta normalized by Volume (Relative Aggression)
        df['feat_delta_rel'] = np.where(vol_total == 0, 0, df['feat_delta'] / vol_total)
        
        # 4. Divergencia Preco-Delta
        # Se o preco sobe mas o delta e negativo (Absorcao)
        price_change = df['close'].diff()
        df['feat_delta_div'] = np.where((price_change > 0) & (df['feat_delta'] < 0), -1,
                                np.where((price_change < 0) & (df['feat_delta'] > 0), 1, 0))
        
        return df

    def calculate_order_book_imbalance(self, bids, asks):
        """
        Calcula o desequilibrio de liquidez (Imbalance).
        Bids/Asks: list of [price, quantity]
        """
        if not bids or not asks:
            return 0.0
            
        # Top 10 niveis sao mais sensiveis
        sum_bid_qty = sum([float(b[1]) for b in bids[:10]])
        sum_ask_qty = sum([float(a[1]) for a in asks[:10]])
        
        total_vol = sum_bid_qty + sum_ask_qty
        if total_vol == 0:
            return 0.0
            
        imbalance = (sum_bid_qty - sum_ask_qty) / total_vol
        return imbalance

    def calculate_avwap(self, df, anchor_time):
        """
        Calcula o Anchored VWAP a partir de um ponto no tempo.
        Formula: Sum(TypicalPrice * Volume) / Sum(Volume)
        """
        if df.empty:
            return pd.Series(dtype=float)
            
        df = df.copy()
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['tp'] * df['volume']
        
        # Mascara para dados apos a ancora (inclusive)
        mask = df.index >= anchor_time
        
        # Inicializa a serie de resultado com NaNs
        avwap = pd.Series(index=df.index, data=np.nan, dtype=float)
        
        if mask.any():
            df_subset = df.loc[mask]
            cum_pv = df_subset['pv'].cumsum()
            cum_vol = df_subset['volume'].cumsum()
            
            # Evita divisao por zero
            avwap_values = np.where(cum_vol == 0, np.nan, cum_pv / cum_vol)
            avwap.loc[mask] = avwap_values
            
        return avwap
