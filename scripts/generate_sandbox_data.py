import sys
import os
import pandas as pd
import numpy as np

# Add project root to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.data_engine import DataEngine
from logic.ml_brain import MLBrain

def generate_sandbox_data():
    print("[DATA] Gerando dataset massivo para Sandbox v3 - ETHUSDT (10.000+ candles)...")
    engine = DataEngine()
    symbol = "ETHUSDT"
    target_count = 10000
    all_dfs = []
    
    current_start = None
    
    # Binance retorna do mais antigo para o mais novo se startTime for passado.
    # Para buscar o PASSADO, precisamos ir voltando no tempo.
    # No entanto, a API da Binance sem startTime retorna os MAIS RECENTES.
    # Vamos buscar o bloco mais recente primeiro, e depois ir voltando usando o open_time do primeiro candle do bloco.
    
    for i in range(10): # 10 blocos de 1000 = 10.000
        print(f"  -> Buscando bloco {i+1}/10...")
        limit = 1000
        # Se ja temos dados, buscamos o que vem ANTES do registro mais antigo que temos
        # Note: endTime seria melhor para ir voltando, mas vamos usar uma logica simples de gap temporal.
        # Na verdade, a API da Binance tem 'endTime'. Vamos usar se possivel.
        
        params = {"symbol": symbol, "interval": "1h", "limit": 1000}
        if current_start:
             # Para buscar ANTES de current_start, precisamos usar endTime
             params["endTime"] = current_start - 1
             
        # Fazendo o request manual via engine para ter controle total do endTime
        data = engine._make_request('api', "/api/v3/klines", params=params)
        
        if not data:
            break
            
        df_batch = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count', 
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        
        # Numeric conversion
        cols = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume']
        # BOLT OPTIMIZATION: Replacing apply(pd.to_numeric) with vectorized block astype(float) for faster data conversion
        df_batch[cols] = df_batch[cols].astype(float)
        
        df_batch['open_time_ms'] = df_batch['open_time']
        df_batch['open_time'] = pd.to_datetime(df_batch['open_time'], unit='ms')
        df_batch.set_index('open_time', inplace=True)
        
        all_dfs.append(df_batch)
        
        # O proximo bloco deve terminar antes do inicio deste bloco
        current_start = int(df_batch['open_time_ms'].min())
        
        if len(data) < 1000:
            break
            
    if not all_dfs:
        print("[ERRO] Falha ao buscar dados.")
        return
        
    df = pd.concat(all_dfs).sort_index()
    print(f"[DATA] Total bruto capturado: {len(df)} amostras.")
    
    df = engine.apply_indicators(df)
    
    # Gerar Labels (Triple Barrier) - Horizon reduzido para 4h (v4 Breakout)
    brain = MLBrain()
    labels = brain.create_labels(df, tp=0.015, sl=0.008, horizon=4)
    
    # Alinhar
    min_len = len(labels)
    df = df.iloc[:min_len].copy()
    df['target_label'] = np.where(labels == 1, 1, 0) # Simplificado para UP=1, else=0
    
    # Salvar
    os.makedirs("data", exist_ok=True)
    df.to_parquet('data/market_history.parquet')
    print(f"[DATA] Dataset massivo salvo em data/market_history.parquet ({len(df)} amostras).")

if __name__ == "__main__":
    generate_sandbox_data()
