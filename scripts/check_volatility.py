import pandas as pd
import joblib
import os
from data.data_engine import DataEngine

def check_volatility():
    engine = DataEngine()
    assets = ["BTCBRL", "ETHBRL", "SOLBRL"]
    
    for asset in assets:
        print(f"\n--- Analise: {asset} ---")
        df = engine.fetch_binance_klines(asset, "1h", 1000)
        if df.empty:
            print(f"[-] Erro ao buscar dados para {asset}")
            continue
        df = engine.apply_indicators(df)
        
        curr_atr = df['feat_atr_pct'].iloc[-1]
        
        # Load v3 model to get threshold
        model_path = f"models/brain_rf_v3_alpha_{asset}.pkl"
        if os.path.exists(model_path):
            model_data = joblib.load(model_path)
            threshold = model_data.get('atr_threshold', 0.0)
            print(f"ATR Atual: {curr_atr:.4f}%")
            print(f"Threshold: {threshold:.4f}%")
            if curr_atr >= threshold:
                print("🟢 REGIME ATIVO: Volatilidade suficiente para sinais v3.")
            else:
                print("🔴 REGIME MORTO: Abaixo do threshold de breakout.")
        else:
            print("[-] Modelo v3 nao encontrado.")

if __name__ == "__main__":
    check_volatility()
