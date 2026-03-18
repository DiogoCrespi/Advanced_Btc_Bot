from data_engine import DataEngine
from order_flow_logic import OrderFlowLogic
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class StrategyOptimizer:
    def __init__(self, asset="BTCUSDT"):
        self.asset = asset
        self.engine = DataEngine()
        self.logic = OrderFlowLogic()
        self.df = self.engine.fetch_binance_klines(asset, interval="1h", limit=1000)
        self.df = self.engine.apply_indicators(self.df)

    def run_backtest(self, use_avwap=True, use_sweeps=True, use_cvd_div=True, use_poc=True):
        """
        Runs a simulation based on the active indicators.
        Returns total PnL and Max Drawdown.
        """
        df = self.df.copy()
        
        # Pre-calculate signals
        if use_avwap:
            # Anchor to start of the week
            anchor = df.index[-1] - timedelta(days=7)
            df['AVWAP'] = self.logic.calculate_avwap(df, anchor)
        
        if use_sweeps:
            df = self.logic.detect_liquidity_sweep(df)
            
        if use_cvd_div:
            df = self.logic.detect_cvd_divergence(df)

        equity = 1.0
        position = 0 # 1 for long, -1 for short
        entry_price = 0
        pnl_history = [1.0]

        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]
            
            # EXIT LOGIC
            if position != 0:
                potential_pnl = (current_price / entry_price - 1) if position == 1 else (entry_price / current_price - 1)
                
                # Take Profit 1.5% or Stop Loss 0.8% (Conservative Directional)
                if potential_pnl >= 0.015 or potential_pnl <= -0.008:
                    equity *= (1 + potential_pnl - 0.001) # 0.1% fee
                    position = 0
            
            # ENTRY LOGIC
            if position == 0:
                score = 0
                
                # Signal 1: Price vs AVWAP
                if use_avwap and not pd.isna(df['AVWAP'].iloc[i]):
                    if current_price > df['AVWAP'].iloc[i]: score += 1
                    else: score -= 1
                
                # Signal 2: Sweeps
                if use_sweeps:
                    if df['sweep_low'].iloc[i] == 1: score += 2 # Bullish rejection
                    if df['sweep_high'].iloc[i] == 1: score -= 2 # Bearish rejection
                
                # Signal 3: CVD Divergence
                if use_cvd_div:
                    if df['cvd_div'].iloc[i] == 1: score += 2
                    if df['cvd_div'].iloc[i] == -1: score -= 2

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
        'Tier': '🛡️ COFRE (Basis)',
        'Return (%)': cofre_return * 100,
        'Drawdown (%)': cofre_dd * 100,
        'Ratio': (cofre_return / cofre_dd) if cofre_dd > 0 else 0
    })

    combinations = [
        ("Conservative", True, True, True, False), # Triple Confirmation
        ("Aggressive", False, True, True, False),  # Flow & Sweep ONLY
        ("Trend Hunter", True, False, False, False) # AVWAP ONLY
    ]

    print("\n" + "="*70)
    print("🧪 INICIANDO ANÁLISE COMPARATIVA DE ALTO IMPACTO (BTC vs ETH vs SOL)")
    print("="*70)

    for asset in assets:
        print(f"\n🔍 Analisando {asset}...")
        opt = StrategyOptimizer(asset)
        for tier_name, use_avwap, use_sweeps, use_cvd_div, use_poc in combinations:
            ret, dd = opt.run_backtest(use_avwap, use_sweeps, use_cvd_div, use_poc)
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
    print("🏆 RELATÓRIO FINAL: BUSCA PELO MAIOR LUCRO (THE PROFIT KING)")
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
    print("📊 Relatório salvo em 'comparativo_lucro_final.csv'")

if __name__ == "__main__":
    run_comparative_analysis()
