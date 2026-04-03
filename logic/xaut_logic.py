# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import numpy as np
import pandas as pd


class XAUTAnalyzer:
    """
    Analisa o ratio XAUT/BTC (preco do XAUTBTC) para detectar oportunidades
    de rotacao de capital: BTC → XAUT (ouro) e XAUT → BTC.

    A logica e de Mean Reversion no ratio:
    - Ratio baixo (XAUT barato vs BTC) → Comprar XAUT com BTC
    - Ratio alto (XAUT caro vs BTC)    → Vender XAUT, recuperar BTC + lucro
    
    Capital sempre medido em BTC. Objetivo: acumular mais BTC ao longo do tempo.
    """

    # ─── Limiares de Sinal ───────────────────────────────────────────────────
    RSI_BUY_STRONG   = 32   # RSI abaixo disso → forte sinal de compra XAUT
    RSI_BUY_MILD     = 42   # RSI abaixo disso (com slope positivo) → compra moderada
    RSI_SELL_STRONG  = 68   # RSI acima disso → forte sinal de venda XAUT
    RSI_SELL_MILD    = 58   # RSI acima disso (com Bollinger) → venda moderada
    BB_BUY_ZONE      = 0.15 # bb_pct abaixo disso = zona de compra
    BB_SELL_ZONE     = 0.85 # bb_pct acima disso  = zona de venda
    MIN_CONFIDENCE   = 0.55 # Limiar minimo de confianca para gerar sinal

    def compute_ratio_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recebe um DataFrame OHLCV do par XAUTBTC e retorna o mesmo DF
        enriquecido com features do ratio para analise de sinal.

        Parametros
        ----------
        df : DataFrame com colunas 'open', 'high', 'low', 'close', 'volume'
             indexado por DatetimeIndex (velas horarias).

        Retorna
        -------
        DataFrame com colunas adicionais de features, sem NaNs.
        """
        df = df.copy()

        # O preco de fechamento do XAUTBTC e o proprio ratio (BTC por 1 XAUT)
        ratio = df['close']

        # ── Medias Moveis do Ratio ────────────────────────────────────────
        df['ratio_sma20'] = ratio.rolling(window=20, min_periods=20).mean()
        df['ratio_sma50'] = ratio.rolling(window=50, min_periods=50).mean()

        # ── RSI do Ratio (14 periodos) ────────────────────────────────────
        delta = ratio.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs    = gain / loss.replace(0, np.nan)
        df['ratio_rsi'] = 100 - (100 / (1 + rs))

        # ── Bollinger Bands (20 periodos, ±2σ) ────────────────────────────
        std20 = ratio.rolling(window=20).std()
        df['bb_upper']  = df['ratio_sma20'] + 2 * std20
        df['bb_lower']  = df['ratio_sma20'] - 2 * std20
        band_width      = (df['bb_upper'] - df['bb_lower']).replace(0, np.nan)
        df['bb_pct']    = (ratio - df['bb_lower']) / band_width  # 0=fundo, 1=topo

        # ── Slope da SMA20 (momentum de curto prazo do ratio) ─────────────
        # Slope positivo = ratio subindo (XAUT valorizando vs BTC)
        df['ratio_slope'] = df['ratio_sma20'].diff(5) / df['ratio_sma20']

        # ── Distancia Percentual do Preco a SMA50 ────────────────────────
        df['dist_sma50'] = (ratio / df['ratio_sma50']) - 1

        return df.dropna()

    def get_signal(self, df: pd.DataFrame) -> tuple[int, float, str]:
        """
        Analisa as features do ratio XAUTBTC e retorna um sinal de trading.

        Retorna
        -------
        (signal, confidence, reason)
            signal      : 1 = comprar XAUT | -1 = vender XAUT→BTC | 0 = aguardar
            confidence  : float [0.0, 1.0]
            reason      : string descritiva do motivo
        """
        if df is None or len(df) < 2:
            return 0, 0.0, "Dados insuficientes"

        last = df.iloc[-1]
        rsi    = float(last.get('ratio_rsi',   50.0))
        bb_pct = float(last.get('bb_pct',       0.5))
        slope  = float(last.get('ratio_slope',  0.0))

        # Validacao de dados corrompidos
        if not all(np.isfinite([rsi, bb_pct, slope])):
            return 0, 0.0, "Features invalidas (NaN/Inf)"

        signal     = 0
        confidence = 0.0
        reason     = "Ratio Neutro"

        # ── Sinais de COMPRA XAUT (ratio baixo = XAUT barato vs BTC) ─────
        if rsi < self.RSI_BUY_STRONG and bb_pct < self.BB_BUY_ZONE:
            # Forca maxima: RSI baixo + preco no fundo das Bandas
            signal     = 1
            confidence = 0.55 + max(0, (self.RSI_BUY_STRONG - rsi) / 80)
            reason     = f"XAUT Barato vs BTC (RSI:{rsi:.0f}+BB)"

        elif rsi < self.RSI_BUY_MILD and slope > 0.0002:
            # Momentum ouro crescente com RSI ainda baixo
            signal     = 1
            confidence = 0.53 + max(0, (self.RSI_BUY_MILD - rsi) / 80)
            reason     = f"Momentum Ouro Crescente (RSI:{rsi:.0f})"

        elif bb_pct < self.BB_BUY_ZONE and slope > 0:
            # Preco no fundo das Bandas + slope comecando a virar
            signal     = 1
            confidence = 0.52
            reason     = f"Mean Reversion Fundo (BB:{bb_pct:.2f})"

        # ── Sinais de VENDA XAUT→BTC (ratio alto = XAUT caro vs BTC) ─────
        elif rsi > self.RSI_SELL_STRONG and bb_pct > self.BB_SELL_ZONE:
            # Forca maxima: RSI alto + preco no topo das Bandas
            signal     = -1
            confidence = 0.55 + max(0, (rsi - self.RSI_SELL_STRONG) / 80)
            reason     = f"XAUT Caro vs BTC (RSI:{rsi:.0f}+BB)"

        elif rsi > self.RSI_SELL_MILD and bb_pct > self.BB_SELL_ZONE:
            # RSI moderadamente alto + no topo de Bollinger
            signal     = -1
            confidence = 0.52
            reason     = f"Sobrecompra Ratio (BB:{bb_pct:.2f})"

        # Filtro de confianca minima
        if confidence < self.MIN_CONFIDENCE:
            signal = 0

        # Clamp na confianca
        confidence = min(confidence, 0.98)

        return signal, confidence, reason

    def calc_pnl_btc(self, position: dict, current_ratio: float) -> float:
        """
        Calcula o PnL em BTC de uma posicao XAUT aberta.

        PnL BTC = (qty_XAUT × ratio_atual) − custo_BTC_entrada
        """
        return (position['xaut_qty'] * current_ratio) - position['cost_btc']

    def calc_pnl_pct(self, position: dict, current_ratio: float) -> float:
        """
        Calcula o PnL percentual relativo ao custo de entrada em BTC.
        """
        pnl       = self.calc_pnl_btc(position, current_ratio)
        cost_btc  = position['cost_btc']
        return pnl / cost_btc if cost_btc > 0 else 0.0

    def is_dca_allowed(
        self,
        existing_positions: list,
        current_ratio: float,
        min_distance_pct: float = 0.015,
    ) -> bool:
        """
        Verifica se e seguro abrir mais uma posicao via DCA.

        Regra: a nova entrada deve estar ao menos `min_distance_pct` (1,5%)
        abaixo da entrada mais proxima ja existente, para evitar empilhamento
        de posicoes no mesmo nivel de preco.

        Parametros
        ----------
        existing_positions : lista de dicts de posicoes abertas
        current_ratio      : ratio XAUTBTC atual
        min_distance_pct   : distancia minima (default 1,5%)
        """
        if not existing_positions:
            return True  # Nenhuma posicao aberta → DCA sempre permitido

        for pos in existing_positions:
            entry = pos.get('ratio_entry', 0)
            if entry <= 0:
                continue
            # Distancia percentual entre o ratio atual e a entrada existente
            dist = abs(current_ratio - entry) / entry
            if dist < min_distance_pct:
                return False  # Muito proximo de uma entrada existente

        return True
