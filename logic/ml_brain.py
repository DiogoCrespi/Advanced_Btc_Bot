import joblib
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.preprocessing import RobustScaler

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
        self.profit_factor = 0.0
        self.atr_threshold = 0.0 # Rolling Threshold v3
        self.scaler = RobustScaler()
        self.status = "OBSERVATION" # Status inicial


    def prepare_features(self, df):
        """
        Engenharia de Features Centralizada (v3-Alpha).
        Unifica indicadores técnicos, microestrutura e codificação temporal.
        """
        df = df.copy()
        cl = 'close' if 'close' in df.columns else 'Close'
        hi = 'high' if 'high' in df.columns else 'High'
        lo = 'low' if 'low' in df.columns else 'Low'
        
        # 1. Macro & Ciclos
        df['feat_macro_risk'] = df.get('macro_risk', 0.5)
        df['feat_btc_dominance'] = df.get('btc_dominance', 50.0)
        
        # 2. Codificação Temporal
        try:
            from logic.features import TemporalEncoder
            df = TemporalEncoder.apply(df)
        except Exception: pass

        # 3. Indicadores Técnicos (Calculados internamente para evitar NaNs externos)
        def add_ind(dt, p, l, suf):
            # MACD
            ema_f = dt[p].ewm(span=12*l, adjust=False).mean()
            ema_s = dt[p].ewm(span=26*l, adjust=False).mean()
            dt[f'feat_macd_{suf}'] = ema_f - ema_s
            # RSI
            delta = dt[p].diff()
            gain = pd.Series(np.maximum(delta.values, 0), index=dt.index).rolling(window=14*l).mean()
            loss = pd.Series(-np.minimum(delta.values, 0), index=dt.index).rolling(window=14*l).mean()
            with np.errstate(divide='ignore', invalid='ignore'):
                rs = gain / np.where(loss == 0, np.nan, loss)
            dt[f'feat_rsi_{suf}'] = 100 - (100 / (1 + rs))
            # Bollinger
            sma = dt[p].rolling(window=20*l).mean()
            std = dt[p].rolling(window=20*l).std()
            with np.errstate(divide='ignore', invalid='ignore'):
                dt[f'feat_bb_dist_{suf}'] = (dt[p] - sma) / np.where(std == 0, np.nan, std)

        for scale, mult in [('1h', 1), ('4h', 4), ('1d', 24)]:
            add_ind(df, cl, mult, scale)

        # 4. Volatilidade e ATR (v3-Alpha)
        df['feat_atr_1h'] = (df[hi] - df[lo]).rolling(window=14).mean()
        df['feat_vol_norm'] = df[cl].pct_change().rolling(window=20).std()
        
        # 5. Order Flow (Resiliente)
        if 'taker_buy_base_volume' in df.columns:
            df['taker_buy_volume'] = df['taker_buy_base_volume']
            from logic.order_flow_logic import OrderFlowLogic
            df = OrderFlowLogic().calculate_delta_features(df)
        
        # 6. Volume Shocks
        avg_vol = df['volume'].rolling(window=50).mean()
        df['feat_vol_shock'] = df['volume'] / avg_vol.replace(0, 1)

        # 7. Estacionariedade (Log-Returns Normalizados)
        for col in [cl, hi, lo]:
            ret = np.log(df[col]).diff()
            df[f'feat_{col.lower()}_ret'] = ret
            # Normalizacao pela volatilidade rolante (Z-Score adaptativo)
            df[f'feat_{col.lower()}_ret_norm'] = ret / (df['feat_vol_norm'].replace(0, 1e-6))

        # 8. Saneamento (ffill para preservar histórico, dropna para NaNs de lookback)
        flow_cols = [c for c in df.columns if 'delta' in c or 'cvd' in c]
        df[flow_cols] = df[flow_cols].fillna(0)
        df = df.ffill().fillna(0)
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

    def train(self, df=None, train_full=False, tp=None, sl=None, horizon=None, X_custom=None, y_custom=None):
        """
        Treina o cerebro de ML com alinhamento v3-Alpha e Walk-Forward Validation (Purged).
        Suporta injecao de dados pre-processados para evitar redundancia e vazamento.
        """
        _hz = horizon if horizon is not None else (self.dna.params["horizon"] if self.dna else 12)
        
        if X_custom is not None and y_custom is not None:
            X, y = X_custom, y_custom
            self.feature_cols = [f"feat_{i}" for i in range(X.shape[1])] # Fallback names
        else:
            if df is None: return False
            data = self.prepare_features(df)
            
            # Identifica features
            self.feature_cols = [c for c in data.columns if c.startswith('feat_') and 'imbalance' not in c]
            X_all = data[self.feature_cols].values
            y_all = self.create_labels(data, horizon=_hz)
            
            min_len = min(len(X_all), len(y_all))
            X = X_all[:min_len]; y = y_all[:min_len]
        
        if len(X) < 100 or len(np.unique(y)) < 2: return False

        # --- Walk-Forward Validation com Purga (Embargo) ---
        # Substitui o split ingenuo 80/20 por janelas sequenciais seguras
        n_splits = 5
        step = len(X) // (n_splits + 1)
        scores = []
        
        for i in range(1, n_splits + 1):
            train_end = i * step
            test_start = train_end + _hz + 10 # Gap de Purga (horizonte + margem)
            test_end = test_start + step
            
            if test_end > len(X): break
            
            
            X_train_fold, y_train_fold = X[:train_end], y[:train_end]
            X_test_fold, y_test_fold = X[test_start:test_end], y[test_start:test_end]
            
            if len(X_test_fold) > 0:
                # Isolamento In-Sample: Scaler treina apenas no passado (treino)
                fold_scaler = RobustScaler()
                X_train_scaled = fold_scaler.fit_transform(X_train_fold)
                X_test_scaled = fold_scaler.transform(X_test_fold)
                
                self.model.fit(X_train_scaled, y_train_fold)
                scores.append(self.model.score(X_test_scaled, y_test_fold))

        final_score = np.mean(scores) if scores else 0.0
        
        # --- Calculo de Profit Factor OOS (Simulado no Test Fold Final) ---
        pf_oos = 1.0
        if scores:
            # Simula no ultimo fold de teste para estimar PF
            X_test_final = X[test_start:test_end]
            y_test_final = y[test_start:test_end]
            if len(X_test_final) > 0:
                y_pred = self.model.predict(fold_scaler.transform(X_test_final))
                wins = np.sum((y_pred == y_test_final) & (y_test_final != 0))
                losses = np.sum((y_pred != y_test_final) & (y_pred != 0))
                # Expectativa conservadora: TP 1.5, SL 0.8
                pf_oos = (wins * 1.5) / (losses * 0.8) if losses > 0 else (2.0 if wins > 0 else 1.0)

        # Treinamento Final (Full Scaled Train para Produção)
        X_final_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_final_scaled, y) 
        
        self.n_samples = len(X)
        self.reliability_score = final_score
        self.profit_factor = pf_oos
        self.status = "LIVE" if final_score > 0.52 and pf_oos > 1.2 else "OBSERVATION"
        
        print(f"[AUDIT] WFA Accuracy: {final_score:.2f} | Profit Factor: {pf_oos:.2f} | Samples: {self.n_samples}")
        self.is_trained = True
        return final_score


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
        
        low_vol_tag = ""
        if curr_atr < self.atr_threshold:
            low_vol_tag = " [LOW_VOL]"

        if len(current_features_row) != len(feature_names):
             return 0, 0.0, "Feature mismatch", 0.0
            
        if not np.isfinite(current_features_row).all():
            return 0, 0.0, "NaN ou Inf detectado", 0.0
        
        # Aplicacao do Scaler Persistido (Respeitando a escala do treino)
        feat_vec = self.scaler.transform(current_features_row.reshape(1, -1))
        
        if not hasattr(self.model, "estimators_") or len(self.model.estimators_) == 0:
            return 0, 0.0, "Modelo nao treinado", 0.0
            
        pred_class = self.model.predict(feat_vec)[0]
        probs = self.model.predict_proba(feat_vec)[0]
        max_prob = max(probs)
        
        _min_conf = self.dna.params["min_confidence"] if self.dna else min_confidence

        if max_prob < _min_conf:
            return 0, max_prob, f"Baixa Conviccao ({max_prob:.1%}){low_vol_tag}", self.reliability_score
        
        return pred_class, max_prob, f"Breakout v3-Alpha{low_vol_tag}", self.reliability_score

    def save_model(self, path="models/brain_rf_v3_alpha.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data_to_save = {
            'model': self.model,
            'feature_cols': self.feature_cols,
            'is_trained': self.is_trained,
            'reliability_score': self.reliability_score,
            'atr_threshold': self.atr_threshold,
            'n_samples': self.n_samples,
            'status': self.status,
            'scaler': self.scaler

        }
        joblib.dump(data_to_save, path)

    def load_model(self, path="models/brain_rf_v3_alpha.pkl"):
        if not os.path.exists(path): return False
        try:
            stored_data = joblib.load(path)
            self.model = stored_data['model']
            self.scaler = stored_data.get('scaler', RobustScaler())
            self.feature_cols = stored_data['feature_cols']
            self.is_trained = stored_data['is_trained']
            self.reliability_score = stored_data.get('reliability_score', 0.0)
            self.atr_threshold = stored_data.get('atr_threshold', 0.0)
            self.n_samples = stored_data.get('n_samples', 0)
            self.status = stored_data.get('status', "OBSERVATION")
            print(f"[LOAD] Cerebro restaurado com sucesso de: {path} ({len(self.feature_cols)} features | Status: {self.status})")

            return True
        except: return False
