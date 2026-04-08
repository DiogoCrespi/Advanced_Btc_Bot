import argparse
import pandas as pd
import numpy as np
import os
import sys
import pickle

# Ensure project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.data_engine import DataEngine
from logic.ml_brain import MLBrain

def parse_args():
    parser = argparse.ArgumentParser(description="Train MLBrain Model with Feature Selection (PR #49 + Local Sonda)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Symbol to train on")
    parser.add_argument("--epochs", type=int, default=200, help="n_estimators in Random Forest")
    parser.add_argument("--local", action="store_true", default=True, help="Use local historical parquet")
    parser.add_argument('--shadow', action='store_true', help='Salva como modelo de sombra (_shadow.pkl)')
    return parser.parse_args()

def main():
    args = parse_args()
    file_path = f"data/{args.symbol}_1h_historical.parquet"

    print(f"[*] Iniciando Sessão de Treinamento para {args.symbol}")

    # 1. Load Data
    if args.local and os.path.exists(file_path):
        print(f"[*] Carregando dataset local: {file_path}")
        df = pd.read_parquet(file_path)
    else:
        print(f"[*] Dataset local não encontrado. Buscando via API...")
        engine = DataEngine()
        df = engine.fetch_binance_klines(args.symbol, interval="1h", limit=3000)
        if df.empty:
            print("[-] Falha ao obter dados.")
            return
        df = engine.apply_indicators(df)

    # 2. Prepare ML Brain
    brain = MLBrain(n_estimators=args.epochs)
    data = brain.prepare_features(df)
    feature_cols = [c for c in data.columns if c.startswith('feat_')]
    
    X_all = data[feature_cols].values
    y_all = brain.create_labels(data)

    min_len = min(len(X_all), len(y_all))
    X = X_all[:min_len]
    y = y_all[:min_len]

    if len(np.unique(y)) < 2:
        print("[-] Diversidade de labels insuficiente para o treino.")
        return

    # 3. TimeSeries Cross-Validation (PR #49 Logic)
    from sklearn.model_selection import TimeSeriesSplit
    tscv = TimeSeriesSplit(n_splits=5)
    print("[*] Executando Validação Cruzada OOS (Walk-Forward)...")
    
    scores = []
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        brain.model.fit(X_train, y_train)
        score = brain.model.score(X_test, y_test)
        scores.append(score)
        print(f"  -> Fold {fold+1}: Accuracy = {score:.4f}")

    print(f"[*] Acurácia Média CV: {np.mean(scores):.4f}")

    # 4. Feature Importance & Selection
    print("\n[*] Analisando Importância das Features...")
    brain.model.fit(X, y) # Full fit for importance calculation
    importances = brain.model.feature_importances_
    feat_importances = pd.Series(importances, index=feature_cols).sort_values(ascending=False)

    print("RANKING DE IMPORTANCIA:")
    selected_features = feat_importances[feat_importances > 0.01].index.tolist()
    dropped_features = feat_importances[feat_importances <= 0.01].index.tolist()

    for feat, imp in feat_importances.items():
        status = "[KEEP]" if feat in selected_features else "[DROP]"
        print(f"   {feat:25s} : {imp:.4f} {status}")

    # 5. Final Export
    if selected_features:
        print(f"\n[*] Retreinando Modelo Final com {len(selected_features)} features...")
        X_selected = data[selected_features].values[:min_len]
        brain.model.fit(X_selected, y)
        brain.feature_cols = selected_features
        brain.is_trained = True
        
        os.makedirs("models", exist_ok=True)
        suffix = "_shadow" if args.shadow else "_v1"
        with open(f"models/brain_rf{suffix}.pkl", "wb") as f:
            pickle.dump(brain.model, f)
        with open(f"models/brain_features{suffix}.pkl", "wb") as f:
            pickle.dump(brain.feature_cols, f)
        print("[+] Modelo salvo com sucesso em models/!")
    else:
        print("[-] Erro: Todas as features foram descartadas.")

if __name__ == "__main__":
    main()
