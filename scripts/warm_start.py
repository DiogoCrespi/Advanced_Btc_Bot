import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta

# Adiciona o diretorio raiz ao path para importar as logicas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.ml_brain import MLBrain
from data.data_engine import DataEngine

def warm_start_training(assets=["BTCBRL", "ETHBRL", "SOLBRL", "LINKBRL", "AVAXBRL", "RENDERBRL"]):
    engine = DataEngine()
    
    if not os.path.exists("models"):
        os.makedirs("models")
    if not os.path.exists("data"):
        os.makedirs("data")

    print(f"=== INICIANDO PRÉ-TREINAMENTO MASSIVO ({len(assets)} ativos) ===")
    
    for asset in assets:
        print(f"\n>>> Processando {asset}...")
        
        # 1. Busca Historico Extendido (Paginado)
        # Queremos 5000 amostras (aprox 7 meses em 1h)
        full_df = pd.DataFrame()
        end_time = int(time.time() * 1000)
        
        for i in range(5): # 5 batches de 1000
            print(f"    Fetching batch {i+1}/5...")
            df = engine.fetch_binance_klines(asset, limit=1000, endTime=end_time)
            if df.empty: break
            
            full_df = pd.concat([df, full_df])
            end_time = int(df.index[0].timestamp() * 1000) - 1
            time.sleep(0.5) # Anti-ban

        if full_df.empty:
            print(f"    [ERRO] Sem dados para {asset}")
            continue

        full_df = full_df[~full_df.index.duplicated(keep='first')]
        print(f"    Total de amostras coletadas: {len(full_df)}")

        # 2. Processamento e Treinamento
        full_df = engine.apply_indicators(full_df)
        
        # Treina Modelo v1 (Live)
        brain_v1 = MLBrain()
        print(f"    Treinando Modelo v1 (Live)...")
        score_v1 = brain_v1.train(full_df, train_full=True)
        brain_v1.save_model(f"models/{asset.lower()}_brain_v1.pkl")
        
        # Treina Modelo v3-Alpha (Shadow)
        brain_v3 = MLBrain()
        print(f"    Treinando Modelo v3-Alpha (Shadow)...")
        score_v3 = brain_v3.train(full_df, train_full=True)
        brain_v3.save_model(f"models/brain_rf_v3_alpha_{asset}.pkl")
        
        print(f"    [OK] {asset} Finalizado. Scores -> v1: {score_v1:.2f} | v3: {score_v3:.2f}")

    print("\n=== PRÉ-TREINAMENTO CONCLUÍDO ===")
    print("Sincronize a pasta 'models/' com o servidor remoto para ativar o Warm Start.")

if __name__ == "__main__":
    warm_start_training()
