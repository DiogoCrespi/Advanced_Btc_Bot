from data_engine import DataEngine
from stat_arb_logic import StatArbLogic
from risk_manager import RiskManager
import pandas as pd
import numpy as np

class StatArbBacktester:
    def __init__(self):
        self.data_engine = DataEngine()
        self.logic = StatArbLogic(window=100, z_threshold=2.0)
        self.risk = RiskManager(initial_balance=10000)
        self.active_trade = None
        self.trades_history = []

    def close_trade(self, p_btc, p_eth, time, reason="Close"):
        pnl_btc = self.risk.calculate_pnl_with_fees(
            self.active_trade['entry_btc'], p_btc, self.active_trade['qty_btc'], is_short=self.active_trade['short_btc']
        )
        pnl_eth = self.risk.calculate_pnl_with_fees(
            self.active_trade['entry_eth'], p_eth, self.active_trade['qty_eth'], is_short=not self.active_trade['short_btc']
        )
        
        net_pnl = pnl_btc + pnl_eth
        self.risk.balance += net_pnl
        self.trades_history.append({
            'time': time, 
            'pnl': net_pnl, 
            'balance': self.risk.balance,
            'reason': reason
        })
        self.active_trade = None

    def run(self):
        print("Fetching BTC and ETH data...")
        df_btc, df_eth = self.data_engine.fetch_data() 
        
        print("Calculating Cointegration (Z-Score & Beta)...")
        spread, z_score, betas = self.logic.calculate_zscore(df_btc, df_eth)
        
        common_index = df_btc.index.intersection(df_eth.index)
        df_btc = df_btc.loc[common_index]
        df_eth = df_eth.loc[common_index]
        z_score = z_score.loc[common_index]
        betas = betas.loc[common_index]
        spread = spread.loc[common_index]
        
        spread_mean = spread.rolling(window=self.logic.window).mean()
        
        print(f"Starting simulation over {len(common_index)} candles...")
        
        # ⚡ BOLT OPTIMIZATION: Convert Pandas Series to NumPy arrays before looping
        # This eliminates the massive overhead of Pandas `.iloc` in tight loops
        z_arr = z_score.to_numpy()
        beta_arr = betas.to_numpy()
        spread_arr = spread.to_numpy()
        spread_mean_arr = spread_mean.to_numpy()
        btc_close_arr = df_btc['Close'].to_numpy()
        eth_close_arr = df_eth['Close'].to_numpy()

        for i in range(100, len(common_index)):
            z = float(z_arr[i])
            beta = float(beta_arr[i])
            s_curr = float(spread_arr[i])
            s_mean = float(spread_mean_arr[i])
            
            p_btc = float(btc_close_arr[i])
            p_eth = float(eth_close_arr[i])
            time = common_index[i]
            
            signal = self.logic.get_signal(z)
            
            # 1. Manage Active Position
            if self.active_trade is not None:
                # Saída por Reversão à Média
                if signal == 0:
                    self.close_trade(p_btc, p_eth, time, "Take Profit")
                # Saída por Z-Stop (Quebra de Cointegração)
                elif abs(z) > 4.0:
                    self.close_trade(p_btc, p_eth, time, "Z-Stop Limit")

            # 2. Open Position (Deviation)
            elif self.active_trade is None and signal is not None and signal != 0:
                if self.logic.is_spread_profitable(z, s_curr, s_mean):
                    # Alocação calibrada: 25% do capital (Equilíbrio entre ROI e Fee Drag)
                    qty_btc, _ = self.risk.calculate_pair_position(p_btc, p_eth, risk_fraction=0.25)
                    
                    adjusted_qty_eth = (qty_btc * p_btc * beta) / p_eth
                    
                    self.active_trade = {
                        'entry_btc': p_btc,
                        'entry_eth': p_eth,
                        'qty_btc': qty_btc,
                        'qty_eth': adjusted_qty_eth,
                        'short_btc': True if signal == -1 else False,
                        'time': time
                    }

            self.risk.calculate_drawdown(self.risk.balance)

        self.report()

    def report(self):
        roi = ((self.risk.balance - 10000) / 10000) * 100
        print(f"\n--- FINAL REFINED STAT ARB REPORT ---")
        print(f"Total Trades:    {len(self.trades_history)}")
        print(f"Final Balance:   ${self.risk.balance:.2f}")
        print(f"ROI:             {roi:.2f}%")
        print(f"Max Drawdown:    {self.risk.max_drawdown*100:.2f}%")

if __name__ == "__main__":
    tester = StatArbBacktester()
    tester.run()
