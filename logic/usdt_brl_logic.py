# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import numpy as np
import pandas as pd

class UsdtBrlLogic:
    """
    Analisa o par USDT/BRL para detectar oportunidades de:
    1. Media Reversao (comprar USDT barato, vender caro).
    2. Safe Harbor (refugio em USDT quando o risco macro e alto).
    """

    # Limiares de sinal para Media Reversao (Aliviados para modo Batedor)
    RSI_BUY_THRESHOLD = 42   # USDT "barato" (sobrevenda)
    RSI_SELL_THRESHOLD = 58  # USDT "caro" (sobrecompra)
    BB_BUY_ZONE = 0.3        # Perto da banda inferior
    BB_SELL_ZONE = 0.7       # Perto da banda superior

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df['close']
        df['sma20'] = close.rolling(window=20).mean()
        df['sma50'] = close.rolling(window=50).mean()

        delta = close.diff()
        gain = pd.Series(np.maximum(delta.values, 0), index=df.index).rolling(window=14).mean()
        loss = pd.Series(-np.minimum(delta.values, 0), index=df.index).rolling(window=14).mean()
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = gain / np.where(loss == 0, np.nan, loss)
        df['rsi'] = 100 - (100 / (1 + rs))

        std20 = close.rolling(window=20).std()
        df['bb_upper'] = df['sma20'] + 2 * std20
        df['bb_lower'] = df['sma20'] - 2 * std20
        
        # BOLT Fix: Use np.where to avoid NaNs on zero bandwidth
        band_width = df['bb_upper'] - df['bb_lower']
        df['bb_pct'] = np.where(band_width == 0, 0.5, (close - df['bb_lower']) / band_width)
        
        df['slope'] = df['sma20'].diff(5) / df['sma20']
        
        # Fill RSI and slope NaNs for stable periods (like in tests)
        df['rsi'] = df['rsi'].fillna(50.0)
        df['slope'] = df['slope'].fillna(0.0)
        
        return df.dropna()

    def _evaluate_buy_signal(self, macro_risk: float, rsi: float, bb_pct: float, slope: float) -> tuple:
        if macro_risk > 0.75:
            confidence = 0.6 + (macro_risk - 0.75)
            reason = f"Macro Risk High ({macro_risk:.2f}) -> Safe Harbor"
            return 1, confidence, reason
        elif rsi < self.RSI_BUY_THRESHOLD and bb_pct < self.BB_BUY_ZONE:
            confidence = 0.55 + (self.RSI_BUY_THRESHOLD - rsi) / 100
            reason = f"USDT Discount (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"
            return 1, confidence, reason
        elif slope > 0.0005 and rsi < 45:
            confidence = 0.52
            reason = "USDT Momentum Up (Recovery)"
            return 1, confidence, reason
        return 0, 0.0, ""

    def _evaluate_sell_signal(self, macro_risk: float, rsi: float, bb_pct: float) -> tuple:
        if rsi > self.RSI_SELL_THRESHOLD and bb_pct > self.BB_SELL_ZONE:
            signal = -1
            confidence = 0.55 + (rsi - self.RSI_SELL_THRESHOLD) / 100
            reason = f"USDT Premium (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"
            if macro_risk < 0.3:
                confidence += 0.1
                reason += " + Macro Risk Low (Exiting USD)"
            return signal, confidence, reason
        return 0, 0.0, ""

    def get_signal(self, df: pd.DataFrame, macro_risk: float = 0.5) -> tuple:
        if df.empty or len(df) < 2:
            return 0, 0.0, "Dados insuficientes", {}

        rsi = float(df['rsi'].values[-1]) if 'rsi' in df.columns else 50.0
        bb_pct = float(df['bb_pct'].values[-1]) if 'bb_pct' in df.columns else 0.5
        slope = float(df['slope'].values[-1]) if 'slope' in df.columns else 0.0

        signal, confidence, reason = self._evaluate_buy_signal(macro_risk, rsi, bb_pct, slope)
        if signal == 0:
            signal, confidence, reason = self._evaluate_sell_signal(macro_risk, rsi, bb_pct)

        metrics = {'rsi': rsi, 'bb_pct': bb_pct, 'slope': slope}
        if signal == 0:
            return 0, 0.0, "USDT Neutro", metrics

        confidence = float(np.clip(confidence, 0.0, 0.95))
        return signal, confidence, reason, metrics
