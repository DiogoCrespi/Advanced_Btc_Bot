import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from logic.order_flow_logic import OrderFlowLogic
from datetime import timedelta

class MLBrain:
    def __init__(self):
        # class_weight='balanced' removes the bias towards the most frequent class (usually Neutral or Long)
        # max_samples=0.5 mitiga o overfitting de 'Label Concurrency' causado pelo Triple Barrier Method
        self.model = RandomForestClassifier(
            n_estimators=150, 
            max_depth=12, 
            min_samples_leaf=15, # Previne overfitting de terminal nodes isolados (ruído em forward-testing)
            random_state=42, 
            class_weight='balanced_subsample',
            max_samples=0.5
        )
        self.logic = OrderFlowLogic()
        self.is_trained = False

    def prepare_features(self, df):
        """
        Transforms raw kline and indicator data into a feature matrix for ML.
        """
        df = df.copy()
        
        # 1. Rolling 7-day VWAP (AVWAP)
        # Using a Rolling 7-day VWAP instead of Calendar Anchored to avoid artificial discontinuities every Monday
        df['tp_temp'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv_temp'] = df['tp_temp'] * df['volume']
        
        # '7D' string relies on DatetimeIndex. Se falhar, fallback para 168 (assumindo 1h). Min periods assegura validade no inicio.
        try:
            df['AVWAP'] = df['pv_temp'].rolling('7D', min_periods=1).sum() / df['volume'].rolling('7D', min_periods=1).sum()
        except ValueError:
            df['AVWAP'] = df['pv_temp'].rolling(168, min_periods=1).sum() / df['volume'].rolling(168, min_periods=1).sum()
            
        df.drop(columns=['tp_temp', 'pv_temp'], inplace=True)
        
        df = self.logic.detect_liquidity_sweep(df)
        df = self.logic.detect_cvd_divergence(df)
        
        # 2. Numerical Features (Normalized)
        df['feat_dist_sma50'] = (df['close'] / df['SMA_50']) - 1
        df['feat_dist_ema21'] = (df['close'] / df['EMA_21']) - 1
        df['feat_dist_avwap'] = (df['close'] / df['AVWAP']) - 1
        df['feat_rsi'] = df['RSI_14'] / 100.0
        df['feat_volatility'] = df['Log_Returns'].rolling(24).std()
        
        # 3. Trend Slope (Essential to avoid "Catching Falling Knives")
        # Positive = Upward momentum, Negative = Downward pressure
        df['feat_slope_sma50'] = df['SMA_50'].diff(5) / df['SMA_50']
        
        # 4. Categorical signals as features
        df['feat_sweep_high'] = df['sweep_high']
        df['feat_sweep_low'] = df['sweep_low']
        df['feat_cvd_div'] = df['cvd_div']
        
        # 5. Temporal Sazonalities (Protects against Rolling VWAP jumps)
        # Assumes df index is a DatetimeIndex
        # Codificacao circular em radianos para continuidade cronologica harmonica (Decision Tree amigavel)
        df['feat_day_of_week_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 7)
        df['feat_day_of_week_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 7)
        df['feat_hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['feat_hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        
        # Drop rows with NaN from rolling calculations
        return df.dropna()

    def create_labels(self, df, tp=0.015, sl=0.008, horizon=24):
        """
        Creates labels: 1 for Long Profitable, -1 for Short Profitable, 0 for Neutral.
        A trade is profitable if it hits TP before SL within the horizon (Triple Barrier Method).
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
                
                # Check Long
                if long_outcome == 0:
                    hit_tp_long = high_ret >= tp
                    hit_sl_long = low_ret <= -sl
                    if hit_tp_long and hit_sl_long:
                        long_outcome = -1 # Pessimistic assumption (intrabar bias prevention)
                    elif hit_sl_long:
                        long_outcome = -1
                    elif hit_tp_long:
                        long_outcome = 1
                        short_outcome = -1 # Invalida o short pois o Long ja atingiu TP primeiro

                # Check Short
                if short_outcome == 0:
                    hit_tp_short = low_ret <= -tp
                    hit_sl_short = high_ret >= sl
                    if hit_tp_short and hit_sl_short:
                        short_outcome = -1 # Pessimistic assumption
                    elif hit_sl_short:
                        short_outcome = -1
                    elif hit_tp_short:
                        short_outcome = 1
                        long_outcome = -1 # Invalida o long pois o Short ja atingiu TP primeiro
                
                # Stop looking forward if both outcomes are already decided
                if long_outcome != 0 and short_outcome != 0:
                    break
            
            # Combine into single label for Random Forest
            if long_outcome == 1 and short_outcome != 1:
                labels.append(1)
            elif short_outcome == 1 and long_outcome != 1:
                labels.append(-1)
            else:
                # Neither is exclusively profitable, or both hit SL first, or timeout
                labels.append(0)
                
        # Removed future target padding (Data Leakage Fix)
        # Size of returned array determines valid X slice
        return np.array(labels)

    def train(self, df, train_full=False, tp=0.015, sl=0.008, horizon=24):
        """
        Trains the Random Forest model on historical data.
        If train_full is True, it uses 100% of data for training (no test split).
        Receives tp and sl dynamically to synchronize ML expectations with bot parameters.
        """
        data = self.prepare_features(df)
        self.feature_cols = [c for c in data.columns if c.startswith('feat_')]
        X = data[self.feature_cols].values
        
        y = self.create_labels(data, tp=tp, sl=sl, horizon=horizon)
        
        # Ajuste dinâmico de complexidade (min_samples_leaf) para evitar overfitting em historicos curtos
        dynamic_leaf = max(5, int(len(y) * 0.01))
        self.model.set_params(min_samples_leaf=dynamic_leaf)
        
        # Remove unknown future samples from the features to prevent Data Leakage
        X = X[:len(y)]
        
        # Log label distribution to detect bias
        unique, counts = np.unique(y, return_counts=True)
        dist = dict(zip(unique, counts))
        print(f"📊 Distribuição de Sinais (Treino): {dist}")
        
        if len(np.unique(y)) < 2:
            print("⚠️ Insufficient label diversity to train ML Brain.")
            return False

        from sklearn.metrics import classification_report

        if train_full:
            # Train on EVERYTHING (for Live Bot)
            self.model.fit(X, y) # Vectorized, scale-invariant fit
            print(f"🧠 ML Brain Trained! (Full History Mode: {len(X)} samples)")
            self.is_trained = True
            return 1.0 # default high score for full train if no OOS available
        else:
            # Split and Train (for Backtest/OOS Validation)
            split_idx = int(len(X) * 0.8)
            X_train, y_train = X[:split_idx], y[:split_idx]
            
            # Start test set AFTER the lookahead horizon to purge train/test leakage
            # Adding a small embargo (e.g. 10 bars) to further prevent autocorrelation leakage
            embargo = 10
            test_start = split_idx + horizon + embargo
            X_test, y_test = X[test_start:], y[test_start:]
            
            if len(X_train) == 0 or len(X_test) == 0:
                print("⚠️ Insufficient data to train after applying purge gap.")
                return 0.0
                
            self.model.fit(X_train, y_train)
            score = self.model.score(X_test, y_test)
            print(f"🧠 ML Brain Trained! Accuracy (OOS): {score:.2%}")
            
            # Relatorio Detalhado OOS
            y_pred = self.model.predict(X_test)
            report = classification_report(y_test, y_pred, zero_division=0)
            print("\n📊 Out-of-Sample Classification Report (Precision focado em Entradas):")
            print(report)
            
            self.is_trained = True
            return score

    def predict_signal(self, current_features_row, feature_names=None, min_confidence=0.55):
        """
        Returns (predicted_class, probability, reason)
        """
        if not self.is_trained:
            return 0, 0.0, "Brain not trained"
            
        if feature_names is None:
            feature_names = getattr(self, 'feature_cols', [])
            
        # Tratamento Robusto de Staleness, Divisões por Zero (Inf) e Missing Data
        if not np.isfinite(current_features_row).all():
            print("⚠️ Segurança/Staleness Alert: NaN ou Inf detectado nas features. Pulando predição para evitar ordens corrompidas e Crash na Random Forest.")
            return 0, 0.0, "Missing/Corrupted Features (NaN ou Inf)"
        
        feat_vec = current_features_row.reshape(1, -1)
        
        pred_class = self.model.predict(feat_vec)[0]
        probs = self.model.predict_proba(feat_vec)[0]
        max_prob = max(probs)
        
        # Filtro de Limiar de Confiança (Relativo devido à recalibração artificial do class_weight='balanced')
        if max_prob < min_confidence:
            pred_class = 0
            reason = f"Conviccao Baixa Ponderada ({max_prob:.1%})"
            return pred_class, max_prob, reason
        
        # Heurística para explicar o motivo
        # Criamos um dicionário chave:valor para facilitar a leitura
        feats = dict(zip(feature_names, current_features_row))
        reason = "Sinal Neutro / Sem Oportunidades"
        
        if pred_class == 1: # COMPRA
            if feats.get('feat_cvd_div', 0) == 1: reason = "Divergencia CVD (Compra)"
            elif feats.get('feat_sweep_low', 0) == 1: reason = "Sweep de Fundo (Compra)"
            elif feats.get('feat_rsi', 0.5) < 0.35: reason = "Oversold RSI"
            elif feats.get('feat_dist_sma50', 0) < -0.03: reason = "Mean Reversion (Under)"
            elif feats.get('feat_slope_sma50', 0) > 0.0001: reason = "SMA50 Up-Trend"
            else: reason = "Confluencia (Compra)"
        elif pred_class == -1: # VENDA (Agora protegido pelo Triple Barrier)
            if feats.get('feat_cvd_div', 0) == -1: reason = "Divergencia CVD (Venda)"
            elif feats.get('feat_sweep_high', 0) == 1: reason = "Sweep de Topo (Venda)"
            elif feats.get('feat_rsi', 0.5) > 0.65: reason = "Overbought RSI"
            elif feats.get('feat_slope_sma50', 0) < -0.0001: reason = "SMA50 Down-Trend"
            elif feats.get('feat_dist_sma50', 0) > 0.04: reason = "Mean Reversion (Over)"
            else: reason = "Confluencia (Venda)"
            
        return pred_class, max_prob, reason

if __name__ == "__main__":
    from data.data_engine import DataEngine
    engine = DataEngine()
    df = engine.fetch_binance_klines("BTCUSDT", limit=1500)
    df = engine.apply_indicators(df)
    
    brain = MLBrain()
    brain.train(df)
    
    # Test prep
    processed = brain.prepare_features(df)
    feature_cols = [c for c in processed.columns if c.startswith('feat_')]
    last_row = processed[feature_cols].values[-1]
    
    signal = brain.predict_signal(last_row)
    print(f"🔮 Final Signal Recommendation: {signal}")
