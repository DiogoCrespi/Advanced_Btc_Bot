import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score
import pyarrow.parquet as pq
import time

def run_v4_breakout_sandbox():
    print("[SANDBOX v4] Iniciando Arquitetura de Micro-Rompimento (Regime + Fast Order Flow)...\n")
    start_time = time.time()

    try:
        df = pd.read_parquet('data/market_history.parquet')
    except Exception as e:
        print(f"[ERRO] Falha ao carregar Parquet: {e}")
        return

    # ---------------------------------------------------------
    # 🚨 FILTRO DE ESTACIONARIEDADE: EXCLUIR PRECOS ABSOLUTOS
    # ---------------------------------------------------------
    # Removemos colunas que contem precos absolutos (open, high, low, close, bb_u, etc)
    # Mantemos apenas features que sao retornos, osciladores ou distancias percentuais.
    blacklist = ['open', 'high', 'low', 'close', 'volume', 'taker_buy_base_volume', 'ignore', 'target_label', 'open_time_ms']
    price_indicators = ['feat_bb_u', 'feat_bb_m', 'feat_bb_l'] # Versoes absolute de preco das BB
    
    features = [col for col in df.columns if col.startswith('feat_') 
                and not any(x in col for x in price_indicators)
                and 'order_book' not in col]
    
    target = 'target_label' 
    
    df = df.dropna(subset=features + [target])

    # ---------------------------------------------------------
    # 🚨 GATING DE REGIME: EXPURGO DE BAIXA VOLATILIDADE
    # ---------------------------------------------------------
    if 'feat_atr_pct' in df.columns:
        # Filtra apenas os top 40% de momentos de maior volatilidade (Percentil 60)
        volatility_threshold = df['feat_atr_pct'].quantile(0.60)
        df_filtered = df[df['feat_atr_pct'] >= volatility_threshold].copy()
        
        print(f"[REGIME] Filtro de Volatilidade Ativado (ATR > {volatility_threshold:.4f}).")
        print(f"[REGIME] Amostras Originais: {len(df)} | Amostras Retidas (Alta Volatilidade): {len(df_filtered)}")
    else:
        print("[AVISO] feat_atr_pct não encontrado. Rodando sem filtro de regime.")
        df_filtered = df.copy()

    X = df_filtered[features].values
    y = df_filtered[target].values

    # ---------------------------------------------------------
    # 🧠 TREINAMENTO (Poda Afrouxada + Penalidade Estrita)
    # ---------------------------------------------------------
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,          # Afrouxado de 10 para 12
        max_features='sqrt',
        min_samples_leaf=30,   # Poda robusta mantida
        class_weight='balanced_subsample', # Punição severa para falsos positivos
        oob_score=True,
        n_jobs=-1,
        random_state=42
    )

    print("\n[ML] Treinando motor especialista em Breakout Institucional...")
    model.fit(X, y)
    
    # Avaliação OOB (Interna, usando as amostras que ficaram de fora de cada árvore)
    oob_preds = np.argmax(model.oob_decision_function_, axis=1)
    
    precision_c1 = precision_score(y, oob_preds, pos_label=1, zero_division=0)
    recall_c1 = recall_score(y, oob_preds, pos_label=1, zero_division=0)

    print("-" * 50)
    print("📊 RESULTADOS DO SANDBOX V4 (OOB METRICS)")
    print("-" * 50)
    print(f"Precision Média (C1 - BUY):  {precision_c1:.2%}")
    print(f"Recall Médio (C1 - BUY):     {recall_c1:.2%}")
    print(f"OOB Score Global:            {model.oob_score_:.2%}")
    print(f"Tempo de Execução:           {time.time() - start_time:.2f}s")
    
    importances = list(zip(features, model.feature_importances_))
    importances.sort(key=lambda x: x[1], reverse=True)
    
    print("\n🔍 TOP 10 FEATURES (Pós-Filtro de Regime):")
    for idx, (feat, imp) in enumerate(importances[:10], 1):
        marker = "🔥" if "delta" in feat.lower() or "cvd" in feat.lower() else "  "
        print(f"{idx}. {feat:<25} {imp:.4%} {marker}")

if __name__ == "__main__":
    run_v4_breakout_sandbox()
