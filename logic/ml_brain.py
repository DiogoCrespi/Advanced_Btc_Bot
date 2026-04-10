import joblib
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

class MLBrain:
    """
    Random Forest Classifier to predict BTC price moves based on technical indicators.
    Focado em detectar anomalias de mercado e ineficiencias em multiplos Tiers.
    """
    def __init__(self, dna=None, n_estimators=200, random_state=42):
        self.dna = dna
        # Se houver DNA, os genes sobrepõem os padrões
        n_est = dna.params["n_estimators"] if dna else n_estimators
        m_depth = dna.params["max_depth"] if dna else 12
        m_leaf = dna.params["min_samples_leaf"] if dna else 10

        self.model = RandomForestClassifier(
            n_estimators=n_est,
            max_depth=m_depth,
            min_samples_leaf=m_leaf,
            random_state=random_state,
            class_weight='balanced'
        )
        self.is_trained = False
        self.feature_cols = []

    def prepare_features(self, df):
        """
        Ingestão Dinâmica refatorada (PR #49).
        Múltiplos timeframes (MACD, BB, RSI) já entram prefixados nativamente por DataEngine/Features Tool.
        Isso empodera o Random Forest a cruzar médias móveis sem viés humano.
        """
        df = df.copy()
        
        df['feat_macro_risk'] = df.get('macro_risk', 0.5)
        df['feat_btc_dominance'] = df.get('btc_dominance', 50.0)
        
        # Order Flow opcional
        if 'cvd_div' in df.columns: df['feat_cvd_div'] = df['cvd_div']
        if 'sweep_high' in df.columns: df['feat_sweep_high'] = df['sweep_high']
        if 'sweep_low' in df.columns: df['feat_sweep_low'] = df['sweep_low']
        
        # Dropamos NaNs surgidos das maiores janelas de Média Móvel (e.g. BB 1D = 480 periods)
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

    def train(self, df, train_full=False, tp=None, sl=None, horizon=None):
        """
        Treina o cerebro de ML com alinhamento garantido de amostras.
        """
        # Prioridade para os genes do DNA se fornecidos
        _tp = tp if tp is not None else (self.dna.params["tp"] if self.dna else 0.015)
        _sl = sl if sl is not None else (self.dna.params["sl"] if self.dna else 0.008)
        _hz = horizon if horizon is not None else (self.dna.params["horizon"] if self.dna else 24)

        data = self.prepare_features(df)
        self.feature_cols = [c for c in data.columns if c.startswith('feat_')]
        X_all = data[self.feature_cols].values
        y_all = self.create_labels(data, tp=_tp, sl=_sl, horizon=_hz)
        
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
            
            test_start = split_idx + _hz + 10 # Purge gap + embargo
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
        
        _min_conf = self.dna.params["min_confidence"] if self.dna else min_confidence

        if max_prob < _min_conf:
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

    def save_model(self, path="models/brain_rf_v1.pkl"):
        """
        Persiste o modelo e as colunas de features para garantir consistencia no boot.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data_to_save = {
            'model': self.model,
            'feature_cols': self.feature_cols,
            'is_trained': self.is_trained
        }
        joblib.dump(data_to_save, path)
        print(f"[SAVE] Cerebro persistido em: {path}")

    def load_model(self, path="models/brain_rf_v1.pkl"):
        """
        Carrega o modelo e restaura o estado do cérebro.
        """
        if not os.path.exists(path):
            return False
            
        try:
            stored_data = joblib.load(path)
            self.model = stored_data['model']
            self.feature_cols = stored_data['feature_cols']
            self.is_trained = stored_data['is_trained']
            print(f"[LOAD] Cerebro restaurado com sucesso de: {path} ({len(self.feature_cols)} features)")
            return True
        except Exception as e:
            print(f"⚠ Erro ao carregar cérebro: {e}")
            return False
