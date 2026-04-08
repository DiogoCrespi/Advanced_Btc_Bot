import os
import sys
import pickle
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logic.ml_brain import MLBrain

def train_and_select_features():
    file_path = "data/BTCUSDT_1h_historical.parquet" 
    if not os.path.exists(file_path):
        print(f"Dataset não encontrado: {file_path}. Rode o download_data.py primeiro.")
        return

    print("[*] Carregando dataset e instanciando motor quantitativo...")
    df = pd.read_parquet(file_path)

    brain = MLBrain()
    print("[*] Treinamento Inicial (Feature Importance Analysis)...")
    base_score = brain.train(df, train_full=False)
    print(f"[*] Precisão OOS (Walk-Forward) Inicial: {base_score:.4f}")

    if not brain.model:
        return

    # Poda de Features (Remoção do Ruído)
    importances = brain.model.feature_importances_
    features = brain.feature_cols
    
    print("\n[!] Dissecação de Importância das Features:")
    weak_features = []
    
    for feat, imp in sorted(zip(features, importances), key=lambda x: x[1], reverse=True):
        status = ""
        if imp < 0.01:
            weak_features.append(feat)
            status = "-> [DROPPED]"
        print(f"   {feat:20}: {imp:.4f} {status}")
        
    if weak_features:
        print(f"\n[*] Podando {len(weak_features)} features fracas (< 0.01) para evitar over-fitting...")
        df.drop(columns=weak_features, inplace=True, errors='ignore')
        
        print("[*] Retreinando o modelo hiper-focado (Final Mode)...")
        new_score = brain.train(df, train_full=False) 
        print(f"[*] Nova Precisão OOS Walk-Forward: {new_score:.4f}")
        
        # Realiza o treino de cobertura total usando 100% dos dados para predições do bot ao-vivo
        brain.train(df, train_full=True)
    else:
        print("\n[*] Nenhuma feature fraca detectada, todas mantém alta convicção preditiva.")
        brain.train(df, train_full=True)
        
    os.makedirs("models", exist_ok=True)
    with open("models/brain_rf_v1.pkl", "wb") as f:
        pickle.dump(brain.model, f)
    
    with open("models/brain_features_v1.pkl", "wb") as f:
        pickle.dump(brain.feature_cols, f)
        
    print("[+] Salvamento concluído em models/brain_rf_v1.pkl")

if __name__ == "__main__":
    train_and_select_features()
