# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")
from ml_brain import MLBrain
from data_engine import DataEngine

def analyze_frequency(asset="BTC-USD", years=1):
    engine = DataEngine()
    brain = MLBrain()
    
    print(f"⏳ Buscando {years} ano(s) de historico para analise...")
    df = yf.download(asset, period=f"{years}y", interval="1h")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    
    # Synthetic CVD
    np.random.seed(42)
    df['taker_buy_base_volume'] = df['volume'] * (0.5 + np.random.uniform(-0.02, 0.02, size=len(df)))
    df['CVD'] = (df['taker_buy_base_volume'] - (df['volume'] - df['taker_buy_base_volume'])).cumsum()
    
    df = engine.apply_indicators(df)
    
    # Train on first 1000h
    train_size = 1000
    brain.train(df.iloc[:train_size], train_full=True)
    
    test_data = df.iloc[train_size:]
    processed = brain.prepare_features(test_data)
    f_cols = [c for c in processed.columns if c.startswith('feat_')]
    
    thresholds = [0.6, 0.7, 0.8]
    results = {}
    
    print(f"\n📊 ANALISE DE DENSIDADE DE SINAIS (Total: {len(test_data)} horas)\n")
    print(f"{'Confianca':<12} | {'Sinais':<10} | {'Trades/Mes':<12} | {'Espera Media':<15}")
    print("-" * 60)
    
    # Pre-extract numpy arrays for fast lookups in loops (~100x speedup)
    feat_arr = processed[f_cols].values
    for thr in thresholds:
        signals = 0
        last_signal_idx = 0
        wait_times = []
        
        for i in range(len(processed)):
            feat_vec = feat_arr[i]
            sig, prob, reason = brain.predict_signal(feat_vec, f_cols)
            
            if sig != 0 and prob >= thr:
                signals += 1
                if last_signal_idx > 0:
                    wait_times.append(i - last_signal_idx)
                last_signal_idx = i
        
        monthly_avg = (signals / len(test_data)) * 24 * 30
        avg_wait = np.mean(wait_times) if wait_times else 0
        
        print(f"{thr:>10.0%}   | {signals:>10} | {monthly_avg:>12.1f} | {avg_wait:>12.1f} horas")
        results[thr] = monthly_avg

    print("\n💡 CONCLUSAO:")
    if results[0.7] < 2:
        print("⚠  70%+ de confianca e muito RARO (custo de oportunidade alto).")
        print("👉 Sugestao: Use 65% para manter o robo ativo ou adicione mais moedas (ETH/SOL).")
    else:
        print(f"✅ 70%+ gera {results[0.7]:.1f} trades por mes. E um bom equilibrio.")

if __name__ == "__main__":
    analyze_frequency()
