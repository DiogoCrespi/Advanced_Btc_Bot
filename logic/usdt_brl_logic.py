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

    def _evaluate_buy_signal(self, macro_risk: float, rsi: float, bb_pct: float, slope: float) -> tuple[int, float, str]:
        """
        Avalia as condicoes de compra de USDT.
        """
        # 1. Risco Macro Elevado (Safe Harbor)
        if macro_risk > 0.75:
            confidence = 0.6 + (macro_risk - 0.75)
            reason = f"Macro Risk High ({macro_risk:.2f}) -> Safe Harbor"
            return 1, confidence, reason
            
        # 2. Media Reversao (USDT barato)
        elif rsi < self.RSI_BUY_THRESHOLD and bb_pct < self.BB_BUY_ZONE:
            confidence = 0.55 + (self.RSI_BUY_THRESHOLD - rsi) / 100
            reason = f"USDT Discount (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"
            return 1, confidence, reason

        # 3. Momentum de Alta com RSI ainda baixo
        elif slope > 0.0005 and rsi < 45:
            confidence = 0.52
            reason = "USDT Momentum Up (Recovery)"
            return 1, confidence, reason

        return 0, 0.0, ""

    def _evaluate_sell_signal(self, macro_risk: float, rsi: float, bb_pct: float) -> tuple[int, float, str]:
        """
        Avalia as condicoes de venda de USDT.
        """
        # 1. Media Reversao (USDT caro)
        if rsi > self.RSI_SELL_THRESHOLD and bb_pct > self.BB_SELL_ZONE:
            signal = -1
            confidence = 0.55 + (rsi - self.RSI_SELL_THRESHOLD) / 100
            reason = f"USDT Premium (RSI:{rsi:.0f}, BB:{bb_pct:.2f})"
            
            # 2. Risco Macro Baixo (Oportunidade de voltar para BRL se estiver caro)
            if macro_risk < 0.3:
                confidence += 0.1
                reason += " + Macro Risk Low (Exiting USD)"

            return signal, confidence, reason

        return 0, 0.0, ""

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

        rsi = float(df['rsi'].values[-1]) if 'rsi' in df.columns else 50.0
        bb_pct = float(df['bb_pct'].values[-1]) if 'bb_pct' in df.columns else 0.5
        slope = float(df['slope'].values[-1]) if 'slope' in df.columns else 0.0
        # price isn't actually used in signal derivation, though kept if needed downstream
        # price = float(df['close'].values[-1])

        # ─── LOGICA DE COMPRA (BRL -> USDT) ───
        signal, confidence, reason = self._evaluate_buy_signal(macro_risk, rsi, bb_pct, slope)

        # ─── LOGICA DE VENDA (USDT -> BRL) ───
        if signal == 0:
            signal, confidence, reason = self._evaluate_sell_signal(macro_risk, rsi, bb_pct)

        if signal == 0:
            return 0, 0.0, "USDT Neutro"

        # Clamp na confianca
        confidence = float(np.clip(confidence, 0.0, 0.95))

        return signal, confidence, reason
