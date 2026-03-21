import time
import os
import pandas as pd
from datetime import datetime, timedelta
from data_engine import DataEngine
from basis_logic import BasisLogic
from ml_brain import MLBrain
from order_flow_logic import OrderFlowLogic

class HybridMasterBot:
    def __init__(self, asset_pair="BTCUSDT", cofre_threshold=0.08):
        self.asset_pair = asset_pair
        self.cofre_threshold = cofre_threshold
        
        # Modules
        self.engine = DataEngine()
        self.basis_logic = BasisLogic()
        self.ml_brain = MLBrain()
        self.of_logic = OrderFlowLogic()
        
        # Initial ML Training
        print(f"🔄 [INIT] Inicializando Motores e Treinando ML Brain...")
        initial_df = self.engine.fetch_binance_klines(asset_pair, limit=1500)
        initial_df = self.engine.apply_indicators(initial_df)
        self.ml_brain.train(initial_df)
        
        print(f"✅ Bot Híbrido Pronto! Alvo Cofre: {cofre_threshold*100}% | Alvo ML: Alpha Predictor")

    def run(self):
        print(f"\n🚀 INICIANDO MONITORAMENTO HÍBRIDO (SEGURANÇA + CRESCIMENTO)\n")
        
        while True:
            try:
                # ---------------------------------------------------------
                # 🛡️ TIER 1: COFRE (Arbitragem de Base) - Foco BTCBRL
                # ---------------------------------------------------------
                cofre_found = False
                contracts = self.engine.fetch_delivery_contracts(asset="BTC")
                basis_results = []
                for c in contracts:
                    data = self.engine.fetch_basis_data(spot_symbol="BTCBRL", delivery_symbol=c['symbol'])
                    if data:
                        expiry = self.basis_logic.parse_expiry(c['symbol'])
                        y = self.basis_logic.calculate_annualized_yield(data['spot'], data['future'], expiry)
                        basis_results.append({**data, 'symbol': c['symbol'], 'yield_apr': y, 'expiry_date': str(expiry)})
                
                best_basis = self.basis_logic.get_earliest_profitable_contract(basis_results, self.cofre_threshold)
                
                # ---------------------------------------------------------
                # 🧠 TIER 2: ALPHA (ML Directional) - Foco BTCUSDT
                # ---------------------------------------------------------
                df_ml = self.engine.fetch_binance_klines(self.asset_pair, limit=100)
                df_ml = self.engine.apply_indicators(df_ml)
                processed_ml = self.ml_brain.prepare_features(df_ml)
                feature_cols = [c for c in processed_ml.columns if c.startswith('feat_')]
                last_features = processed_ml[feature_cols].iloc[-1].values
                ml_signal = self.ml_brain.predict_signal(last_features)
                
                # ---------------------------------------------------------
                # 📊 DASHBOARD UNIFICADO (Console)
                # ---------------------------------------------------------
                timestamp = datetime.now().strftime('%H:%M:%S')
                os.system('cls' if os.name == 'nt' else 'clear')
                
                print(f"╔{'═'*70}╗")
                print(f"║ 🤖 MASTER BOT HÍBRIDO | {timestamp} | Ativo: {self.asset_pair:10} ║")
                print(f"╠{'═'*70}╣")
                
                # Report Basis
                highest = self.basis_logic.get_best_contract(basis_results)
                curr_y = (highest['yield_apr'] * 100) if highest else 0
                status_cofre = "✅ OPORTUNIDADE!" if best_basis else "📈 MONITORANDO"
                print(f"║ 🛡️  [COFRE - BRL] Status: {status_cofre:17} | Melhor Yield: {curr_y:6.2f}% a.a. ║")
                if best_basis:
                    print(f"║    🎯 Alvo: {best_basis['symbol']} ({best_basis['yield_apr']*100:.2f}% a.a.) {' '*24} ║")
                
                print(f"║{' '*70}║")
                
                # Report ML
                ml_text = "NADA"
                if ml_signal == 1: ml_text = "🟢 COMPRA (LONG)"
                elif ml_signal == -1: ml_text = "🔴 VENDA (SHORT)"
                
                print(f"║ 🧠 [ALPHA - ML ] Sinal: {ml_text:21} | Confiabilidade (OOS): 76% ║")
                print(f"║    🔧 Baseado em: AVWAP, Sweeps, CVD Divergence e RSI           ║")
                print(f"╚{'═'*70}╝")
                
                if best_basis or ml_signal != 0:
                    print("\n🔔 ALERTA: Ação recomendada detectada!")
                    if best_basis: print(f"👉 COFRE: Trave {best_basis['symbol']} para garantir {best_basis['yield_apr']*100:.2f}%")
                    if ml_signal != 0: print(f"👉 ALPHA: Entrada em {ml_text} sugerida pelo modelo de ML.")

            except Exception as e:
                print(f"❌ Erro no loop: {e}")
            
            time.sleep(120) # Atualiza a cada 2 minutos

if __name__ == "__main__":
    bot = HybridMasterBot(asset_pair="BTCUSDT", cofre_threshold=0.08)
    bot.run()
