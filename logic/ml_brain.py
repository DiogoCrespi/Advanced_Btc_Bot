import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from logic.order_flow_logic import OrderFlowLogic
from datetime import timedelta

class MLBrain:
    def __init__(self):
        # class_weight='balanced' removes the bias towards the most frequent class (usually Neutral or Long)
        self.model = RandomForestClassifier(
            n_estimators=150, 
            max_depth=12, 
            random_state=42, 
            class_weight='balanced'
        )
        self.scaler = StandardScaler()
        self.logic = OrderFlowLogic()
        self.is_trained = False

    def prepare_features(self, df):
        """
        Transforms raw kline and indicator data into a feature matrix for ML.
        """
        df = df.copy()
        
        # 1. Order Flow Signals (Logic)
        # For ML Training, we use a rolling anchor that covers the whole history
        # instead of a fixed 7-day anchor.
        anchor_all = df.index[0]
        df['AVWAP'] = self.logic.calculate_avwap(df, anchor_all)
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
        
        # Drop rows with NaN from rolling calculations
        return df.dropna()

    def create_labels(self, df, tp=0.015, sl=0.008, horizon=24):
        """
        Creates labels: 1 for Long Profitable, -1 for Short Profitable, 0 for Neutral.
        A trade is profitable if it hits TP before SL within the horizon.
        """
        labels = []
        prices = df['close'].values
        
        for i in range(len(prices) - horizon):
            window = prices[i+1 : i+1+horizon]
            entry = prices[i]
            
            label = 0
            for p in window:
                ret = (p / entry) - 1
                if ret >= tp: # Hit TP first
                    label = 1
                    break
                if ret <= -sl: # Hit SL first
                    label = -1
                    break
            
            labels.append(label)
                
        # Padding for the last horizon rows
        labels.extend([0] * horizon)
        return np.array(labels)

    def train(self, df, train_full=False):
        """
        Trains the Random Forest model on historical data.
        If train_full is True, it uses 100% of data for training (no test split).
        """
        data = self.prepare_features(df)
        feature_cols = [c for c in data.columns if c.startswith('feat_')]
        X = data[feature_cols].values
        y = self.create_labels(data)
        
        # Log label distribution to detect bias
        unique, counts = np.unique(y, return_counts=True)
        dist = dict(zip(unique, counts))
        print(f"📊 Distribuição de Sinais (Treino): {dist}")
        
        if len(np.unique(y)) < 2:
            print("⚠️ Insufficient label diversity to train ML Brain.")
            return False

        if train_full:
            # Train on EVERYTHING (for Live Bot)
            self.scaler.fit(X)
            self.model.fit(self.scaler.transform(X), y)
            print(f"🧠 ML Brain Trained! (Full History Mode: {len(X)} samples)")
        else:
            # Split and Train (for Backtest/OOS Validation)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            self.scaler.fit(X_train)
            self.model.fit(self.scaler.transform(X_train), y_train)
            score = self.model.score(self.scaler.transform(X_test), y_test)
            print(f"🧠 ML Brain Trained! Accuracy (OOS): {score:.2%}")
            
        self.is_trained = True
        return True

    def predict_signal(self, current_features_row, feature_names):
        """
        Returns (predicted_class, probability, reason)
        """
        if not self.is_trained:
            return 0, 0.0, "Brain not trained"
        
        feat_vec = current_features_row.reshape(1, -1)
        feat_scaled = self.scaler.transform(feat_vec)
        
        pred_class = self.model.predict(feat_scaled)[0]
        probs = self.model.predict_proba(feat_scaled)[0]
        max_prob = max(probs)
        
        # Heurística para explicar o motivo
        # Criamos um dicionário chave:valor para facilitar a leitura
        feats = dict(zip(feature_names, current_features_row))
        reason = "Confluência"
        
        if pred_class == 1: # COMPRA
            if feats.get('feat_cvd_div', 0) == 1: reason = "Divergência CVD"
            elif feats.get('feat_sweep_low', 0) == 1: reason = "Sweep de Fundo"
            elif feats.get('feat_rsi', 0.5) < 0.3: reason = "Vendido (RSI)"
            elif feats.get('feat_slope_sma50', 0) > 0.0001: reason = "Tendência Alta"
        elif pred_class == -1: # VENDA
            if feats.get('feat_cvd_div', 0) == -1: reason = "Pressão Vendedora"
            elif feats.get('feat_sweep_high', 0) == 1: reason = "Sweep de Topo"
            elif feats.get('feat_slope_sma50', 0) < -0.0001: reason = "Tendência Baixa"
            elif feats.get('feat_dist_sma50', 0) > 0.05: reason = "Esticado (Média)"
            
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
    last_row = processed[feature_cols].iloc[-1].values
    
    signal = brain.predict_signal(last_row)
    print(f"🔮 Final Signal Recommendation: {signal}")
