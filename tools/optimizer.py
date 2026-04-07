# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
from data_engine import DataEngine
from order_flow_logic import OrderFlowLogic
from ml_brain import MLBrain
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class StrategyOptimizer:
    def __init__(self, asset="BTCUSDT"):
        self.asset = asset
        self.engine = DataEngine()
        self.logic = OrderFlowLogic()
        self.ml_brain = MLBrain()
        self.df = self.engine.fetch_binance_klines(asset, interval="1h", limit=1500)
        self.df = self.engine.apply_indicators(self.df)

    def run_backtest(self, use_avwap=True, use_sweeps=True, use_cvd_div=True, use_poc=True, use_ml=False):
        """
        Runs a simulation based on the active indicators or ML model.
        Returns total PnL and Max Drawdown.
        """
        df = self.df.copy()
        
        if use_ml:
            print(f"🧠 [ML MODE] Treinando cerebro para {self.asset}...")
            # Train on the first part of data
            self.ml_brain.train(df.iloc[:len(df)//2])
            df = self.ml_brain.prepare_features(df)
            feature_cols = [c for c in df.columns if c.startswith('feat_')]
            # Start backtest from the point where OOS data begins
            start_idx = len(df)//2
        else:
            # Pre-calculate signals (Rule-based)
            if use_avwap:
                anchor = df.index[-1] - timedelta(days=7)
                df['AVWAP'] = self.logic.calculate_avwap(df, anchor)
            
            if use_sweeps:
                df = self.logic.detect_liquidity_sweep(df)
                
            if use_cvd_div:
                df = self.logic.detect_cvd_divergence(df)
            
            start_idx = 1

        equity = 1.0
        position = 0 # 1 for long, -1 for short
        entry_price = 0
        pnl_history = [1.0]

        # Pre-extract arrays for faster lookup in loops
        close_arr = df['close'].values
        if not use_ml:
            has_avwap = use_avwap and 'AVWAP' in df.columns
            if has_avwap:
                avwap_arr = df['AVWAP'].values
            if use_sweeps:
                sweep_low_arr = df['sweep_low'].values
                sweep_high_arr = df['sweep_high'].values
            if use_cvd_div:
                cvd_div_arr = df['cvd_div'].values

        for i in range(start_idx, len(df)):
            current_price = float(close_arr[i])
            
            # EXIT LOGIC
            if position != 0:
                potential_pnl = (current_price / entry_price - 1) if position == 1 else (entry_price / current_price - 1)
                
                # Take Profit 1.5% or Stop Loss 0.8%
                if potential_pnl >= 0.015 or potential_pnl <= -0.008:
                    equity *= (1 + potential_pnl - 0.001) # 0.1% fee
                    position = 0
            
            # ENTRY LOGIC
            if position == 0:
                if use_ml:
                    # ML Mode uses predicted class
                    feat_vec = df[feature_cols].iloc[i].values
                    signal, prob, reason = self.ml_brain.predict_signal(feat_vec, feature_cols)
                    if signal == 1:
                        position = 1
                        entry_price = current_price
                    elif signal == -1:
                        position = -1
                        entry_price = current_price
                        
                else:
                    score = 0
                    
                    # Signal 1: Price vs AVWAP
                    if has_avwap and not pd.isna(avwap_arr[i]):
                        if current_price > float(avwap_arr[i]): score += 1
                        else: score -= 1
                    
                    # Signal 2: Sweeps
                    if use_sweeps:
                        if sweep_low_arr[i] == 1: score += 2
                        if sweep_high_arr[i] == 1: score -= 2
                    
                    # Signal 3: CVD Divergence
                    if use_cvd_div:
                        if cvd_div_arr[i] == 1: score += 2
                        elif cvd_div_arr[i] == -1: score -= 2

                    # Threshold to enter
                    if score >= 3:
                        position = 1
                        entry_price = current_price
                    elif score <= -3:
                        position = -1
                        entry_price = current_price
            
            pnl_history.append(equity)

        total_return = equity - 1
        max_dd = 0
        peak = 1.0
        for p in pnl_history:
            if p > peak: peak = p
            dd = (peak - p) / peak
            if dd > max_dd: max_dd = dd
            
        return total_return, max_dd

def run_comparative_analysis():
    assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    all_results = []
    
    # Cofre Simulation (Basis Arbitrage is ~10-15% a.a., so ~0.03% daily)
    # For a 1000h period (~42 days), we expect ~1.2% return with 0.1% DD
    cofre_return = 1.25 / 100
    cofre_dd = 0.05 / 100
    all_results.append({
        'Asset': 'VARIOUS',
        'Tier': '🛡 COFRE (Basis)',
        'Return (%)': cofre_return * 100,
        'Drawdown (%)': cofre_dd * 100,
        'Ratio': (cofre_return / cofre_dd) if cofre_dd > 0 else 0
    })

    combinations = [
        ("Conservative", True, True, True, False, False), # Triple Confirmation
        ("Aggressive", False, True, True, False, False),  # Flow & Sweep ONLY
        ("Trend Hunter", True, False, False, False, False), # AVWAP ONLY
        ("🧠 ML BRAIN", False, False, False, False, True)   # Machine Learning Aggregation
    ]

    print("\n" + "="*70)
    print("🧪 INICIANDO ANALISE COMPARATIVA DE ALTO IMPACTO (BTC vs ETH vs SOL)")
    print("="*70)

    for asset in assets:
        print(f"\n🔍 Analisando {asset}...")
        opt = StrategyOptimizer(asset)
        for tier_name, use_avwap, use_sweeps, use_cvd_div, use_poc, use_ml in combinations:
            ret, dd = opt.run_backtest(use_avwap, use_sweeps, use_cvd_div, use_poc, use_ml)
            all_results.append({
                'Asset': asset,
                'Tier': tier_name,
                'Return (%)': ret * 100,
                'Drawdown (%)': dd * 100,
                'Ratio': (ret / dd) if dd > 0 else 0
            })
            print(f"[{tier_name:12}] {asset} -> Retorno: {ret*100:6.2f}% | DD: {dd*100:5.2f}%")

    # Final Report Generation
    print("\n" + "="*70)
    print("🏆 RELATORIO FINAL: BUSCA PELO MAIOR LUCRO (THE PROFIT KING)")
    print("="*70)
    
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values(by='Return (%)', ascending=False)
    
    print(df_results.to_string(index=False))
    
    best = df_results.iloc[0]
    print("\n" + "="*70)
    print(f"🥇 O VENCEDOR ABSOLUTO: {best['Asset']} no modo {best['Tier']}!")
    print(f"🔥 Retorno: {best['Return (%)']:.2f}% | Risco: {best['Drawdown (%)']:.2f}%")
    print("="*70 + "\n")

    # Save to file
    df_results.to_csv("comparativo_lucro_final.csv", index=False)
    print("📊 Relatorio salvo em 'comparativo_lucro_final.csv'")

if __name__ == "__main__":
    run_comparative_analysis()
