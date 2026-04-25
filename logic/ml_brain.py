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
    v3-Alpha: Especialista em Breakouts com Gating de Volatilidade.
    """
    def __init__(self, dna=None, n_estimators=200, random_state=42):
        self.dna = dna
        # Se houver DNA, os genes sobrepõem os padrões
        n_est = dna.params["n_estimators"] if dna else n_estimators
        self.max_depth = dna.params["max_depth"] if dna else 11 # v3-Alpha Target
        m_leaf = dna.params["min_samples_leaf"] if dna else 40 # v3-Alpha Target
        self.n_jobs = dna.params.get("n_jobs", 1) if dna else 1 # Default 1 para evitar overhead em herança

        self.model = RandomForestClassifier(
            n_estimators=n_est,
            max_depth=self.max_depth,
            min_samples_leaf=m_leaf,
            random_state=random_state,
            class_weight='balanced_subsample', # v3-Alpha: Punicao severa para falsos positivos
            oob_score=True,
            n_jobs=self.n_jobs
        )
        self.is_trained = False
        self.feature_cols = []
        self.n_samples = 0
        self.reliability_score = 0.0
        self.atr_threshold = 0.0 # Rolling Threshold v3
        self.status = "OBSERVATION" # Status inicial: OBSERVATION ou LIVE


    def prepare_features(self, df):
        """
        Ingestão Dinâmica refatorada (v3-Alpha).
        Implementa Gating de Volatilidade e saneamento de features.
        """
        df = df.copy()
        
        # 1. Macro & Dominance
        df['feat_macro_risk'] = df.get('macro_risk', 0.5)
        df['feat_btc_dominance'] = df.get('btc_dominance', 50.0)
        
        # 2. Codificacao Temporal Ciclica (Sin/Cos)
        try:
            from logic.features import TemporalEncoder
            df = TemporalEncoder.apply(df)
        except ImportError:
            pass

        # 3. Order Flow (PR #60/61 + Local Div)
        if 'feat_cvd_4h' not in df.columns: df['feat_cvd_4h'] = 0.0
        if 'feat_cvd_8h' not in df.columns: df['feat_cvd_8h'] = 0.0
        if 'feat_delta' not in df.columns: df['feat_delta'] = 0.0
        if 'cvd_div' in df.columns: df['feat_cvd_div'] = df['cvd_div']
        if 'sweep_high' in df.columns: df['feat_sweep_high'] = df['sweep_high']
        if 'sweep_low' in df.columns: df['feat_sweep_low'] = df['sweep_low']

        
        # 3. Gating de Volatilidade (Rolling ATR Percentile)
        # Calibrado com o percentil 5 (muito mais permissivo) para evitar falsos vetos
        # em regimes de volatilidade normal/baixa frente ao historico de treinamento.
        if 'feat_atr_pct' in df.columns:
            historical_atr = df['feat_atr_pct'].tail(1000)
            self.atr_threshold = historical_atr.quantile(0.05)
            # Protecao: Nunca cair abaixo de um threshold absoluto minimo (0.05%)
            self.atr_threshold = max(0.05, self.atr_threshold)
        
        # Dropamos NaNs (necessario para o RF)
        return df.dropna()

    def create_labels(self, df, tp=0.015, sl=0.008, horizon=4):
        """
        Creates labels using Triple Barrier Method.
        v3-Alpha: Horizon reduzido para 4h para capturar Alpha Decay.
        """
        from numpy.lib.stride_tricks import sliding_window_view

        if 'high' not in df.columns or 'low' not in df.columns:
            return np.array([])

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        n = len(closes)
        valid_n = n - horizon

        if valid_n <= 0:
            return np.array([])
            
        entries = closes[:valid_n, None]

        h_views = sliding_window_view(highs[1:], window_shape=horizon)[:valid_n]
        l_views = sliding_window_view(lows[1:], window_shape=horizon)[:valid_n]

        hit_tp_long = h_views >= entries * (1 + tp)
        hit_sl_long = l_views <= entries * (1 - sl)

        hit_tp_short = l_views <= entries * (1 - tp)
        hit_sl_short = h_views >= entries * (1 + sl)

        def get_first_hit(cond):
            first_idx = np.argmax(cond, axis=1)
            first_idx[~cond.any(axis=1)] = horizon
            return first_idx
            
        f_tp_l = get_first_hit(hit_tp_long)
        f_sl_l = get_first_hit(hit_sl_long)
        f_tp_s = get_first_hit(hit_tp_short)
        f_sl_s = get_first_hit(hit_sl_short)

        long_outcomes = np.zeros(valid_n, dtype=int)
        l_active = (f_sl_l < horizon) | (f_tp_l < horizon)
        long_outcomes[l_active & (f_sl_l <= f_tp_l)] = -1
        long_outcomes[l_active & (f_tp_l < f_sl_l)] = 1

        short_outcomes = np.zeros(valid_n, dtype=int)
        s_active = (f_sl_s < horizon) | (f_tp_s < horizon)
        short_outcomes[s_active & (f_sl_s <= f_tp_s)] = -1
        short_outcomes[s_active & (f_tp_s < f_sl_s)] = 1

        labels = np.zeros(valid_n, dtype=int)
        labels[(long_outcomes == 1) & (short_outcomes != 1)] = 1
        labels[(short_outcomes == 1) & (long_outcomes != 1)] = -1

        return labels

    def train(self, df, train_full=False, tp=None, sl=None, horizon=None):
        """
        Treina o cerebro de ML com alinhamento e filtros v3-Alpha.
        """
        _tp = tp if tp is not None else (self.dna.params["tp"] if self.dna else 0.015)
        _sl = sl if sl is not None else (self.dna.params["sl"] if self.dna else 0.008)
        _hz = horizon if horizon is not None else (self.dna.params["horizon"] if self.dna else 12) # v3-Alpha: Aumentado de 4 para 12

        data = self.prepare_features(df)
        
        # v3-Alpha: Gating no Treino (Opcional, mas Sandbox provou ser superior)
        if 'feat_atr_pct' in data.columns:
            # Filtro de Volatilidade mais suave (30th percentile -> 15th percentile se necessario)
            self.atr_threshold = data['feat_atr_pct'].quantile(0.30)
            data_filtered = data[data['feat_atr_pct'] >= self.atr_threshold].copy()
            
            if len(data_filtered) < 1000:
                print(f"[AVISO] Dataset insuficiente ({len(data_filtered)}) com 30th percentile. Usando 10th percentile...")
                self.atr_threshold = data['feat_atr_pct'].quantile(0.10)
                data = data[data['feat_atr_pct'] >= self.atr_threshold].copy()
            else:
                data = data_filtered

            if len(data) < 500:
                print(f"[AVISO] Dataset criticamente curto ({len(data)}). Ignorando filtro de regime.")
                self.atr_threshold = 0.0
                data = self.prepare_features(df) # Recarrega sem filtro

        self.feature_cols = [c for c in data.columns if c.startswith('feat_') and 'bb_u' not in c and 'bb_m' not in c and 'bb_l' not in c]
        X_all = data[self.feature_cols].values
        y_all = self.create_labels(data, tp=_tp, sl=_sl, horizon=_hz)
        
        min_len = min(len(X_all), len(y_all))
        X = X_all[:min_len]
        y = y_all[:min_len]
        
        if len(np.unique(y)) < 2:
            print("Insufficient label diversity to train ML Brain v3.")
            return False

        # Split Walk-Forward com Purge
        split_idx = int(len(X) * 0.8)
        X_train, y_train = X[:split_idx], y[:split_idx]
        
        test_start = split_idx + _hz + 10 # Purge gap + embargo
        X_test, y_test = X[test_start:], y[test_start:]
        
        print(f"[ML-DEBUG] Training with X_train: {X_train.shape}, y_train: {y_train.shape}, Classes: {np.unique(y_train)}")
        self.model.oob_score = False # Temporarily disable to bypass sklearn bug
        self.model.fit(X_train, y_train)
        self.n_samples = len(X_train)
        score = self.model.score(X_test, y_test) if len(X_test) > 0 else 0.0
        
        # Score OOB para robustez
        oob = self.model.oob_score_ if hasattr(self.model, 'oob_score_') and self.n_samples > 100 else 0.5
        self.reliability_score = min(1.0, self.n_samples / 5000) * oob
        
        # Audit Report Log
        diff = score - oob
        audit_msg = f"[AUDIT] Samples: {self.n_samples} | Accuracy: {score:.2f} | OOB: {oob:.2f} | Diff: {diff:.2f}"
        if diff > 0.15: audit_msg += " -> ⚠️ OVERFITTING ALERT"
        print(audit_msg)
        
        # Um modelo e considerado LIVE apenas se tiver maturidade minima
        self.status = "LIVE" if self.n_samples >= 400 else "OBSERVATION"
        
        self.is_trained = True
        return score if len(X_test) > 0 else oob


    def get_feature_importances(self):
        """
        Retorna a importancia das features ordenada.
        Utilizado para auditar se o TemporalEncoder (Sin/Cos) esta dominando o modelo.
        """
        if not self.is_trained: return {}
        importances = self.model.feature_importances_
        feat_map = sorted(zip(self.feature_cols, importances), key=lambda x: x[1], reverse=True)
        return dict(feat_map)

    def predict_signal(self, current_features_row, feature_names=None, min_confidence=0.55):
        """
        Predicao v3-Alpha: Inclui check de Gating de Volatilidade.
        """
        if not self.is_trained:
            return 0, 0.0, "Brain not trained", 0.0
            
        if feature_names is None:
            feature_names = self.feature_cols
            
        # 1. Check de Gating de Volatilidade (v3-Alpha)
        # Se as features passadas contem o ATR, validamos contra o threshold movel
        feats = dict(zip(feature_names, current_features_row))
        curr_atr = feats.get('feat_atr_pct', 0.0)
        
        if curr_atr < self.atr_threshold:
            reason = f"VETO REGIME: Baixa Volatilidade ({curr_atr:.2f} < {self.atr_threshold:.2f})"
            return 0, 0.0, reason, self.reliability_score

        if len(current_features_row) != len(feature_names):
             return 0, 0.0, "Feature mismatch", 0.0
            
        if not np.isfinite(current_features_row).all():
            return 0, 0.0, "NaN ou Inf detectado", 0.0
        
        if not hasattr(self.model, "estimators_") or len(self.model.estimators_) == 0:
            return 0, 0.0, "Model not properly initialized", 0.0

        feat_vec = current_features_row.reshape(1, -1)
        pred_class = self.model.predict(feat_vec)[0]
        probs = self.model.predict_proba(feat_vec)[0]
        max_prob = max(probs)
        
        _min_conf = self.dna.params["min_confidence"] if self.dna else min_confidence

        if max_prob < _min_conf:
            return 0, max_prob, f"Baixa Conviccao ({max_prob:.1%})", self.reliability_score
        
        return pred_class, max_prob, "Breakout v3-Alpha", self.reliability_score

    def save_model(self, path="models/brain_rf_v3_alpha.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data_to_save = {
            'model': self.model,
            'feature_cols': self.feature_cols,
            'is_trained': self.is_trained,
            'reliability_score': self.reliability_score,
            'atr_threshold': self.atr_threshold,
            'n_samples': self.n_samples,
            'status': self.status

        }
        joblib.dump(data_to_save, path)

    def load_model(self, path="models/brain_rf_v3_alpha.pkl"):
        if not os.path.exists(path): return False
        try:
            stored_data = joblib.load(path)
            self.model = stored_data['model']
            self.feature_cols = stored_data['feature_cols']
            self.is_trained = stored_data['is_trained']
            self.reliability_score = stored_data.get('reliability_score', 0.0)
            self.atr_threshold = stored_data.get('atr_threshold', 0.0)
            self.n_samples = stored_data.get('n_samples', 0)
            self.status = stored_data.get('status', "OBSERVATION")
            print(f"[LOAD] Cerebro restaurado com sucesso de: {path} ({len(self.feature_cols)} features | Status: {self.status})")

            return True
        except: return False
