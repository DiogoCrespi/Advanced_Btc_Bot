# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import os
import sys
import pandas as pd
import orjson as json
from datetime import datetime

# Adiciona o diretorio raiz ao sys.path
sys.path.append(os.getcwd())

from data.data_engine import DataEngine
from logic.ml_brain import MLBrain
from logic.feature_store import FeatureStore

def run_massive_cycle(symbol="BTCUSDT", target_samples=20000):
    print(f"[MASSIVE] Iniciando Ciclo de Treinamento Gold Standard para {symbol}")
    print(f"[PARAMS] Meta: {target_samples} amostras")
    
    engine = DataEngine()
    store = FeatureStore()
    
    # 1. Backfill Progressivo
    print("[1/4] Coletando dados historicos...")
    df = engine.fetch_historical_backfill(symbol, target_samples=target_samples)
    if df.empty:
        print("[MASSIVE] Falha ao coletar dados.")
        return
    
    # Persistir no Parquet para garantir integridade
    df['symbol'] = symbol
    store.append_new_data(df)
    
    # 2. Preparacao de Dataframe (Indicadores)
    print("[2/4] Calculando indicadores e features...")
    df = engine.apply_indicators(df)
    
    # 3. Treinamento com CPU Guard
    print(f"[3/4] Treinando MLBrain (n_jobs=4, samples={len(df)})...")
    # Configuracao de ALTA PERFORMANCE para o ciclo massivo
    brain = MLBrain(n_estimators=300) 
    brain.max_depth = 20
    brain.n_jobs = 4 # Threaded parallelization
    
    # 80/20 split com audit implicito no .train()
    score = brain.train(df, train_full=False)
    
    # 4. Auditoria de Importancia
    print("[4/4] Gerando Relatorio de Auditoria...")
    importances = brain.get_feature_importances()
    
    # Filtra e formata top 15
    top_15 = list(importances.items())[:15]
    
    print("\n" + "="*50)
    print(f"AUDIT REPORT: {symbol} MASSIVE CYCLE")
    print("="*50)
    print(f"Total Samples: {brain.n_samples}")
    print(f"Test Accuracy: {score:.4f}")
    print(f"OOB Reliability: {brain.reliability_score:.4f}")
    print(f"Status Final: {brain.status}")
    print("-" * 50)
    print("TOP FEATURES (Importance):")
    for feat, val in top_15:
        print(f"  > {feat:<25}: {val:.4%}")
    print("-" * 50)
    
    # Salva Snapshot de Auditoria
    audit_data = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "samples": int(brain.n_samples),
        "test_score": float(score),
        "reliability": float(brain.reliability_score),
        "top_features": [[feat, float(val)] for feat, val in top_15]
    }
    
    audit_path = "results/massive_audit_btcusdt.json"
    os.makedirs("results", exist_ok=True)
    with open(audit_path, "wb") as f:
        f.write(json.dumps(audit_data, option=json.OPT_INDENT_2))
    
    # Salva Modelo v2
    model_path = f"models/{symbol.lower()}_brain_v2_massive.pkl"
    brain.save_model(model_path)
    
    print(f"\n[MASSIVE] Ciclo concluido com sucesso!")
    print(f"[SAVE] Modelo salvo: {model_path}")
    print(f"[SAVE] Auditoria salva: {audit_path}")

if __name__ == "__main__":
    run_massive_cycle()
