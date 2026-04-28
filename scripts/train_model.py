import argparse
import pandas as pd
import numpy as np
import os
import sys
import joblib

# Ensure project root is in PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.data_engine import DataEngine
from logic.ml_brain import MLBrain

def parse_args():
    parser = argparse.ArgumentParser(description="Train MLBrain v3-Alpha (Breakout Specialist)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Symbol to train on")
    parser.add_argument("--limit", type=int, default=10000, help="Number of candles")
    return parser.parse_args()

def main():
    args = parse_args()
    print(f"[*] Iniciando Treinamento v3-Alpha para {args.symbol}...")
    
    engine = DataEngine()
    
    # 1. Fetch Massive Data (10k+)
    # Usando a logica de paginacao ja validada no sandbox
    all_dfs = []
    current_start = None
    blocks = (args.limit // 1000) + 1
    
    for i in range(blocks):
        print(f"  -> Buscando bloco {i+1}/{blocks}...")
        params = {"symbol": args.symbol, "interval": "1h", "limit": 1000}
        if current_start:
            params["endTime"] = current_start - 1
        
        data = engine._make_request('api', "/api/v3/klines", params=params)
        if not data: break
        
        df_batch = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count', 
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        df_batch['open_time_ms'] = df_batch['open_time']
        df_batch['open_time'] = pd.to_datetime(df_batch['open_time'], unit='ms')
        df_batch.set_index('open_time', inplace=True)
        all_dfs.append(df_batch)
        current_start = int(df_batch['open_time_ms'].min())
        if len(data) < 1000: break
        
    if not all_dfs:
        print("[-] Falha ao obter dados.")
        return
        
    df = pd.concat(all_dfs).sort_index()
    # Converte colunas para numerico (DataEngine espera isso)
    cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume']
    df[cols] = df[cols].astype(float)
    
    print(f"[*] Aplicando indicadores e saneamento...")
    df = engine.apply_indicators(df)
    
    # 2. Train v3-Alpha Brain
    # Note: O MLBrain.train() agora ja lida com:
    # - Filtro de Regime (ATR Gating)
    # - Horizonte Curto (4h)
    # - Purged CV
    # - Hiperparametros Otimizados
    brain = MLBrain()
    score = brain.train(df)
    
    if score:
        print(f"[+] Treino concluído! Score (OOB/Test): {score:.4f}")
        # Salva como v3_alpha para deploy shadow
        path = f"models/brain_rf_v3_alpha_{args.symbol}.pkl"
        brain.save_model(path)
        print(f"[+] Modelo v3-Alpha salvo em: {path}")
    else:
        print("[-] Falha no treinamento.")

if __name__ == "__main__":
    main()
