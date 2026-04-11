import pandas as pd
import numpy as np
from data.data_engine import DataEngine
from logic.ml_brain import MLBrain

def verify_integration():
    print("[*] Verificando integração: DataEngine -> tools.features -> MLBrain")
    
    # 1. Gerar dados falsos (velas 1h)
    dates = pd.date_range("2025-01-01", periods=1000, freq="h")
    df = pd.DataFrame({
        'open': np.linspace(50000, 60000, 1000) + np.random.normal(0, 100, 1000),
        'high': np.linspace(50100, 60100, 1000) + np.random.normal(0, 100, 1000),
        'low': np.linspace(49900, 59900, 1000) + np.random.normal(0, 100, 1000),
        'close': np.linspace(50050, 60050, 1000) + np.random.normal(0, 100, 1000),
        'volume': np.random.randint(100, 1000, 1000)
    }, index=dates)

    engine = DataEngine()
    
    # 2. Aplicar indicadores (isso chama o tools.features)
    print("[*] Aplicando indicadores...")
    df_processed = engine.apply_indicators(df)
    
    # 3. Verificar se as colunas 'feat_' e 'MACD_line_4h' etc. existem
    critical_cols = ['feat_macd_line_4h', 'feat_bb_pct_distance_1d', 'feat_returns']
    found_cols = [c for c in df_processed.columns if c in critical_cols]
    print(f"[*] Colunas críticas encontradas: {found_cols}")
    
    if len(found_cols) == len(critical_cols):
        print("[OK] DataEngine e tools.features conversam corretamente.")
    else:
        print("[ERRO] Algumas colunas críticas sumiram no processo!")
        return

    # 4. Verificar ingestão no MLBrain
    print("[*] Verificando ingestão no MLBrain...")
    brain = MLBrain()
    data_for_ml = brain.prepare_features(df_processed)
    
    ml_features = [c for c in data_for_ml.columns if c.startswith('feat_')]
    print(f"[*] Total de features detectadas pelo MLBrain: {len(ml_features)}")
    
    if len(ml_features) > 20: # MACD(3x3) + BB(3x2) + RSI(3) + others...
        print("[OK] MLBrain está capturando as features dinâmicas com prefixo 'feat_'.")
    else:
        print(f"[AVISO] Poucas features detectadas ({len(ml_features)}). Verifique o prefixamento.")

if __name__ == "__main__":
    verify_integration()
