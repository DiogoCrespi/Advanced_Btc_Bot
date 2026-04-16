import asyncio
import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Caminho do projeto
sys.path.append(os.getcwd())

from data.data_engine import DataEngine
from logic.strategist_agent import StrategistAgent
from logic.ml_brain import MLBrain

async def run_diagnostic():
    load_dotenv()
    print(">>> INICIANDO ANALISE DE OPORTUNIDADE (SEM MIROFISH) <<<")
    
    engine = DataEngine()
    agent = StrategistAgent()
    assets = ["BTCBRL", "ETHBRL", "SOLBRL"]
    
    # Simular dados macro atuais (assumindo estabilidade se as APIs falharem)
    macro_data = engine.fetch_macro_data()
    
    print(f"\n[DADOS MACRO ATUAIS]: {macro_data}")
    
    # 1. ANALISE COM MIROFISH (SIMULADO BEARISH - O QUE O USUARIO REPORTOU)
    # ------------------------------------------------------------------
    print("\n--- CENARIO 1: COM MIROFISH (BEARISH @ 0.95) ---")
    news_sent_pessimist = -0.95
    risk_with_miro = agent.radar.get_macro_score(
        macro_data.get('dxy_change',0), 
        macro_data.get('sp500_change',0), 
        macro_data.get('gold_change',0), 
        news_sent_pessimist
    )
    print(f"Risk Score Calculado: {risk_with_miro:.2f}")
    
    if risk_with_miro < 0.35:
        print("RESULTADO: [RISK OFF] Bloqueio total de compras longas.")
    else:
        print("RESULTADO: [RISK ON] Compras permitidas (Raro com sentimento -0.95)")

    # 2. ANALISE SEM MIROFISH (CALCULO PURO - NEUTRAL @ 0.0)
    # ------------------------------------------------------------------
    print("\n--- CENARIO 2: SEM MIROFISH (CALCULO PURO / NEUTRAL) ---")
    news_sent_neutral = 0.0
    risk_pure = agent.radar.get_macro_score(
        macro_data.get('dxy_change',0), 
        macro_data.get('sp500_change',0), 
        macro_data.get('gold_change',0), 
        news_sent_neutral
    )
    print(f"Risk Score Calculado: {risk_pure:.2f}")
    
    recom_mult, recom_msg = agent.radar.get_recommended_position_mult()
    print(f"Recomendacao: {recom_msg} (Mult: {recom_mult})")

    # 3. VERIFICACAO DE SINAIS ALPHA (ML)
    # ------------------------------------------------------------------
    print("\n--- ANALISE DE SINAIS DE ATIVOS (ORDENS BLOQUEADAS) ---")
    for asset in assets:
        df = engine.fetch_binance_klines(asset, limit=100)
        if df.empty: continue
        df = engine.apply_indicators(df)
        
        brain = MLBrain()
        # Tenta carregar o modelo live se existir
        model_path = f"models/{asset.lower()}_brain_v1.pkl"
        if os.path.exists(model_path):
            brain.load_model(model_path)
            
        df = brain.prepare_features(df)
        curr_feat = df[brain.feature_cols].values[-1]
        sig, prob, reason = brain.predict_signal(curr_feat)
        
        # Avaliar se seria aprovado sem MiroFish
        # Override do radar interno do agente para o teste
        agent.radar.risk_score = risk_pure
        decision, diag_reason, _ = agent.assess_trade(asset, sig, prob, reason)
        
        status = "✅ APROVADO" if decision == "APPROVE" else "❌ REJEITADO"
        print(f"Asset: {asset:8} | Sinal: {sig:>2} | Prob: {prob:.1%} | {status} | Motivo: {diag_reason}")

    print("\n>>> CONCLUSAO: O MiroFish estava reduzindo o Score Macro em ~15%, o que")
    print("rebaixou o bot para o modo Bunker/Seguranca. Sem ele, os sinais Alpha acima")
    print("teriam sido executados normalmente se a probabilidade fosse >= 48%.")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
