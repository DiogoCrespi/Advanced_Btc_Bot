# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import numpy as np
import pandas as pd

class UsdtBrlLogic:
    """
    Analisa o par USDT/BRL para detectar oportunidades de:
    1. Media Reversao (comprar USDT barato, vender caro).
    2. Safe Harbor (refugio em USDT quando o risco macro e alto).
    
    A logica foca no premio/desconto do USDT em relacao ao BRL.
    """

    # Limiares de sinal para Media Reversao
    RSI_BUY_THRESHOLD = 35   # USDT "barato" (sobrevenda)
    RSI_SELL_THRESHOLD = 65  # USDT "caro" (sobrecompra)
    BB_BUY_ZONE = 0.2        # Perto da banda inferior
    BB_SELL_ZONE = 0.8       # Perto da banda superior

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enriquece o DataFrame USDTBRL com indicadores tecnicos.
        """
        df = df.copy()
        close = df['close']

        # Medias Moveis
        df['sma20'] = close.rolling(window=20).mean()
        df['sma50'] = close.rolling(window=50).mean()

        # RSI (14 periodos)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands (20 periodos, ±2σ)
        std20 = close.rolling(window=20).std()
        df['bb_upper'] = df['sma20'] + 2 * std20
        df['bb_lower'] = df['sma20'] - 2 * std20
        band_width = (df['bb_upper'] - df['bb_lower']).replace(0, np.nan)
        df['bb_pct'] = (close - df['bb_lower']) / band_width

        # Slope (Momentum)
        df['slope'] = df['sma20'].diff(5) / df['sma20']

        return df.dropna()

    def get_signal(self, df: pd.DataFrame, macro_risk: float = 0.5) -> tuple[int, float, str]:
        """
        Gera um sinal de trading para USDT/BRL.
        
        Sinal:
         1 = Comprar USDT com BRL
        -1 = Vender USDT para BRL
         0 = Neutro
        """
        if df.empty or len(df) < 2:
            return 0, 0.0, "Dados insuficientes"

        last = df.iloc[-1]
        rsi = float(last.get('rsi', 50.0))
        bb_pct = float(last.get('bb_pct', 0.5))
        slope = float(last.get('slope', 0.0))
        price = float(last['close'])

        signal = 0
        confidence = 0.0
        reason = "USDT Neutro"

        # ─── LOGICA DE COMPRA (BRL -> USDT) ───
        
        # 1. Risco Macro Elevado (Safe Harbor)
        if macro_risk > 0.75:
            signal = 1
            confidence = 0.6 + (macro_risk - 0.75)
            reason = f"Macro Risk High ({macro_risk:.2f}) -> Safe Harbor"
            
        # 2. Media Reversao (USDT barato)
        elif rsi < self.RSI_BUY_THRESHOLD and bb_pct < self.BB_BUY_ZONE:
            signal = 1
            confidence = 0.55 + (self.RSI_BUY_THRESHOLD - rsi) / 100
            reason = f"USDT Discount (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"

        # 3. Momentum de Alta com RSI ainda baixo
        elif slope > 0.0005 and rsi < 45:
            signal = 1
            confidence = 0.52
            reason = "USDT Momentum Up (Recovery)"

        # ─── LOGICA DE VENDA (USDT -> BRL) ───
        
        # 1. Media Reversao (USDT caro)
        elif rsi > self.RSI_SELL_THRESHOLD and bb_pct > self.BB_SELL_ZONE:
            signal = -1
            confidence = 0.55 + (rsi - self.RSI_SELL_THRESHOLD) / 100
            reason = f"USDT Premium (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"
            
        # 2. Risco Macro Baixo (Oportunidade de voltar para BRL se estiver caro)
        if signal == -1 and macro_risk < 0.3:
            confidence += 0.1
            reason += " + Macro Risk Low (Exiting USD)"

        # Clamp na confianca
        confidence = float(np.clip(confidence, 0.0, 0.95))

        return signal, confidence, reason
