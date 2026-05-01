# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import numpy as np
import pandas as pd

class TemporalEncoder:
    """
    Transforma informacao temporal linear em features ciclicas (Sin/Cos).
    Isso permite que o modelo entenda que 23h esta proximo de 00h e que
    Dezembro esta proximo de Janeiro.
    """
    @staticmethod
    def apply(df):
        """
        Aplica codificacao radial em Hour, DayOfWeek e Month.
        """
        df = df.copy()
        
        # Assume que o index e um DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            return df
            
        # Pre-extract to numpy arrays and pre-calculate constants for massive speedup
        hours = df.index.hour.values
        dows = df.index.dayofweek.values
        months = df.index.month.values

        pi_2_24 = 2 * np.pi / 24
        pi_2_7 = 2 * np.pi / 7
        pi_2_12 = 2 * np.pi / 12

        # 1. Hour (0-23)
        df['feat_hour_sin'] = np.sin(pi_2_24 * hours)
        df['feat_hour_cos'] = np.cos(pi_2_24 * hours)
        
        # 2. Day of Week (0-6)
        df['feat_dow_sin'] = np.sin(pi_2_7 * dows)
        df['feat_dow_cos'] = np.cos(pi_2_7 * dows)
        
        # 3. Month (1-12)
        df['feat_month_sin'] = np.sin(pi_2_12 * (months - 1))
        df['feat_month_cos'] = np.cos(pi_2_12 * (months - 1))
        
        # 4. Bollinger Band Z-Score (Volatilidade Relativa)
        # Se as colunas BB existirem, calculamos a distancia em desvios padrao (Z-Score)
        # Nota: (Price - SMA) / StdDev. 
        # Como o DataEngine ja fornece dist_pct, podemos usar como aproximacao ou calcular agora se houver os dados.
        
        return df
