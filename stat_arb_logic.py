import pandas as pd
import numpy as np

class StatArbLogic:
    def __init__(self, window=100, z_threshold=2.0):
        self.window = window
        self.z_threshold = z_threshold

    def calculate_zscore(self, df_btc, df_eth):
        """
        Calcula o Spread logarítmico ajustado pela Regressão Linear (Beta).
        """
        df, _ = df_btc.align(df_eth, join='inner', axis=0)
        
        log_btc = np.log(df_btc['Close'])
        log_eth = np.log(df_eth['Close'])
        
        # Cálculo do Hedge Ratio (Beta) via Rolagem: Covariância / Variância
        cov = log_btc.rolling(window=self.window).cov(log_eth)
        var = log_eth.rolling(window=self.window).var()
        beta = cov / var
        
        # O Spread Real (Resíduo da cointegração)
        spread = log_btc - (beta * log_eth)
        
        spread_mean = spread.rolling(window=self.window).mean()
        spread_std = spread.rolling(window=self.window).std()
        
        z_score = (spread - spread_mean) / spread_std
        
        return spread, z_score, beta

    def is_spread_profitable(self, z_score, spread_current, spread_mean, fee_total=0.002):
        """
        Garante que a reversão esperada (Spread atual até a média)
        é maior do que o custo total das taxas (aprox 0.2% a 0.4%).
        """
        if abs(z_score) > 4.0: # Z-Stop: Se o desvio for extremo, a cointegração quebrou
            return False
        expected_profit_margin = abs(spread_current - spread_mean)
        return expected_profit_margin > fee_total

    def get_signal(self, current_z_score):
        """
        Retorna o sinal de trade com base no Z-Score.
        """
        if pd.isna(current_z_score):
            return None
            
        if current_z_score > self.z_threshold:
            # Spread demasiado alto (BTC está caro em relação ao ETH)
            # Sinal: SHORT BTC, LONG ETH
            return -1 
        elif current_z_score < -self.z_threshold:
            # Spread demasiado baixo (BTC está barato em relação ao ETH)
            # Sinal: LONG BTC, SHORT ETH
            return 1
        elif abs(current_z_score) < 0.1:
            # Reversão à média (Fechar posições)
            return 0
        return None
