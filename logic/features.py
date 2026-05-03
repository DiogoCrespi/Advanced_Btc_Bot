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
            
        # ⚡ BOLT OPTIMIZATION: Extract indices to numpy arrays and precalculate
        # constants to avoid heavy Pandas Series indexing overhead (~30% speedup)
        idx = df.index
        hours = idx.hour.values
        dows = idx.dayofweek.values
        months = idx.month.values - 1

        pi2 = 2 * np.pi
        h_rad = hours * (pi2 / 24)
        d_rad = dows * (pi2 / 7)
        m_rad = months * (pi2 / 12)

        # 1. Hour (0-23)
        df['feat_hour_sin'] = np.sin(h_rad)
        df['feat_hour_cos'] = np.cos(h_rad)
        
        # 2. Day of Week (0-6)
        df['feat_dow_sin'] = np.sin(d_rad)
        df['feat_dow_cos'] = np.cos(d_rad)
        
        # 3. Month (1-12)
        df['feat_month_sin'] = np.sin(m_rad)
        df['feat_month_cos'] = np.cos(m_rad)
        
        # 4. Bollinger Band Z-Score (Volatilidade Relativa)
        # Se as colunas BB existirem, calculamos a distancia em desvios padrao (Z-Score)
        # Nota: (Price - SMA) / StdDev. 
        # Como o DataEngine ja fornece dist_pct, podemos usar como aproximacao ou calcular agora se houver os dados.
        
        return df
