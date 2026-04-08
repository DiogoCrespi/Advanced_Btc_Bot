# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

class MLBrain:
    """
    Random Forest Classifier to predict BTC price moves based on technical indicators.
    Focado em detectar anomalias de mercado e ineficiencias em multiplos Tiers.
    """
    def __init__(self, n_estimators=200, random_state=42):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=12,
            min_samples_leaf=10,
            random_state=random_state,
            class_weight='balanced' # Lida com o desequilibrio de classes (Neutro e mais comum)
        )
        self.is_trained = False
        self.feature_cols = []

    def prepare_features(self, df):
        """
        Gera features normalizadas e delta de indicadores.
        """
        df = df.copy()
        
        # Features Distancia (Relative to Price)
        df['feat_dist_sma50'] = (df['close'] / df['SMA_50']) - 1
        df['feat_dist_ema21'] = (df['close'] / df['EMA_21']) - 1
        
        # Momentum e Forca
        df['feat_rsi'] = df['RSI_14'] / 100
        df['feat_returns'] = df['Log_Returns']
        
        # Volatilidade (Standard Deviation of returns) - Proxy para Vol
        df['feat_volatility'] = df['Log_Returns'].rolling(window=14).std()
        
        # Slopes (Vectorized using .diff() for speed)
        df['feat_slope_sma50'] = df['SMA_50'].diff(5) / df['SMA_50']
        df['feat_slope_ema21'] = df['EMA_21'].diff(5) / df['EMA_21']
        
        # Order Flow Metrics (Se disponiveis)
        df['feat_cvd_div']  = df.get('cvd_div', 0)
        df['feat_sweep_high'] = df.get('sweep_high', 0)
        df['feat_sweep_low']  = df.get('sweep_low', 0)
        
        # Macro Risk (Novo!)
        df['feat_macro_risk'] = df.get('macro_risk', 0.5)
        
        # Fluxo de Capital - Bitcoin Dominance (Novo!)
        df['feat_btc_dominance'] = df.get('btc_dominance', 50.0)
        
        # Novas features dinamicas (MACD e Bollinger Bands Multi-Timeframe)
        df['feat_macd_line_1h'] = df.get('MACD_line_1h', 0)
        df['feat_macd_hist_1h'] = df.get('MACD_hist_1h', 0)
        df['feat_macd_signal_1h'] = df.get('MACD_signal_1h', 0)
        df['feat_bb_pct_distance_1h'] = df.get('BB_pct_distance_1h', 0)

        df['feat_macd_line_4h'] = df.get('MACD_line_4h', 0)
        df['feat_macd_hist_4h'] = df.get('MACD_hist_4h', 0)
        df['feat_macd_signal_4h'] = df.get('MACD_signal_4h', 0)
        df['feat_bb_pct_distance_4h'] = df.get('BB_pct_distance_4h', 0)

        df['feat_macd_line_1d'] = df.get('MACD_line_1d', 0)
        df['feat_macd_hist_1d'] = df.get('MACD_hist_1d', 0)
        df['feat_macd_signal_1d'] = df.get('MACD_signal_1d', 0)
        df['feat_bb_pct_distance_1d'] = df.get('BB_pct_distance_1d', 0)

        # Limpeza: Dropamos NaNs (provenientes do rolling) para evitar Crash na RF
        return df.dropna()

    def create_labels(self, df, tp=0.015, sl=0.008, horizon=24):
        """
        Creates labels using Triple Barrier Method.
        """
        labels = []
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        for i in range(len(closes) - horizon):
            entry = closes[i]
            long_outcome = 0
            short_outcome = 0
            
            for j in range(i+1, i+1+horizon):
                high_ret = (highs[j] / entry) - 1
                low_ret = (lows[j] / entry) - 1
                
                if long_outcome == 0:
                    hit_tp_long = (high_ret >= tp)
                    hit_sl_long = (low_ret <= -sl)
                    if hit_tp_long and hit_sl_long: long_outcome = -1
                    elif hit_sl_long: long_outcome = -1
                    elif hit_tp_long: long_outcome = 1
                
                if short_outcome == 0:
                    hit_tp_short = (low_ret <= -tp)
                    hit_sl_short = (high_ret >= sl)
                    if hit_tp_short and hit_sl_short: short_outcome = -1
                    elif hit_sl_short: short_outcome = -1
                    elif hit_tp_short: short_outcome = 1

                if long_outcome != 0 and short_outcome != 0:
                    break
            
            if long_outcome == 1 and short_outcome != 1:
                labels.append(1)
            elif short_outcome == 1 and long_outcome != 1:
                labels.append(-1)
            else:
                labels.append(0)
                
        return np.array(labels)

    def train(self, df, train_full=False, tp=0.015, sl=0.008, horizon=24):
        """
        Treina o cerebro de ML com alinhamento garantido de amostras.
        """
        data = self.prepare_features(df)
        self.feature_cols = [c for c in data.columns if c.startswith('feat_')]
        X_all = data[self.feature_cols].values
        y_all = self.create_labels(data, tp=tp, sl=sl, horizon=horizon)
        
        # Alinhamento CRITICO para evitar Found input variables with inconsistent numbers of samples
        min_len = min(len(X_all), len(y_all))
        X = X_all[:min_len]
        y = y_all[:min_len]
        
        if len(np.unique(y)) < 2:
            print("⚠ Insufficient label diversity to train ML Brain.")
            return False

        if train_full:
            # Train on EVERYTHING (for Live Bot)
            X_aligned = X[:len(y)]
            y_aligned = y[:len(X_aligned)]
            self.model.fit(X_aligned, y_aligned) 
            print(f"🧠 ML Brain Trained! (Full: {len(X_aligned)} samples)")
            self.is_trained = True
            return 1.0
        else:
            split_idx = int(len(X) * 0.8)
            X_train, y_train = X[:split_idx], y[:split_idx]
            
            test_start = split_idx + horizon + 10 # Purge gap + embargo
            X_test, y_test = X[test_start:], y[test_start:]
            
            if len(X_train) == 0 or len(X_test) == 0:
                return 0.0
                
            self.model.fit(X_train, y_train)
            score = self.model.score(X_test, y_test)
            self.is_trained = True
            return score

    def predict_signal(self, current_features_row, feature_names=None, min_confidence=0.55):
        """
        Executa predicao com checks de seguranca para NaN/Inf.
        """
        if not self.is_trained:
            return 0, 0.0, "Brain not trained"
            
        if feature_names is None:
            feature_names = self.feature_cols
            
        if len(current_features_row) != len(feature_names):
             # Protecao extra contra mismatch de features
             return 0, 0.0, f"Feature mismatch: Expected {len(feature_names)}, got {len(current_features_row)}"
            
        if not np.isfinite(current_features_row).all():
            return 0, 0.0, "NaN ou Inf detectado nas features"
        
        feat_vec = current_features_row.reshape(1, -1)
        pred_class = self.model.predict(feat_vec)[0]
        probs = self.model.predict_proba(feat_vec)[0]
        max_prob = max(probs)
        
        if max_prob < min_confidence:
            return 0, max_prob, f"Conviccao Baixa ({max_prob:.1%})"
        
        # Heuristicas basicas para o 'reason'
        feats = dict(zip(feature_names, current_features_row))
        reason = "Confluencia ML"
        
        if pred_class == 1:
            if feats.get('feat_cvd_div', 0) == 1: reason = "Divergencia CVD (Compra)"
            elif feats.get('feat_sweep_low', 0) == 1: reason = "Sweep de Fundo (Compra)"
        elif pred_class == -1:
            if feats.get('feat_cvd_div', 0) == -1: reason = "Divergencia CVD (Venda)"
            elif feats.get('feat_sweep_high', 0) == 1: reason = "Sweep de Topo (Venda)"
            
        return pred_class, max_prob, reason
