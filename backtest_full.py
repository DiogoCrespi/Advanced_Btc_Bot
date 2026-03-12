from data_engine import DataEngine
from ml_engine import MLEngine
from ict_logic import ICTLogic
from time_filters import TimeFilters
from risk_manager import RiskManager
import pandas as pd
import numpy as np
from datetime import datetime

class FullBacktester:
    def __init__(self, initial_balance=10000):
        self.data_engine = DataEngine()
        self.ml_engine = MLEngine()
        self.ict_logic = ICTLogic()
        self.time_filters = TimeFilters()
        self.risk_manager = RiskManager(initial_balance=initial_balance)
        
        self.balance = initial_balance
        self.trades = []
        self.current_position = None

    def run(self):
        print("Fetching and processing data...")
        df_btc, df_eth = self.data_engine.fetch_data()
        df_btc = self.data_engine.apply_indicators(df_btc)
        df_btc = self.data_engine.check_smt_divergence(df_btc, df_eth)
        
        # Warm up ML (using first 80% for training)
        train_split = int(len(df_btc) * 0.8)
        print(f"Training ML model on {train_split} periods...")
        train_data = df_btc['Log_Returns'].iloc[1:train_split].dropna()
        seqs, lbls = self.ml_engine.prepare_data(train_data)
        self.ml_engine.train_model(seqs, lbls, epochs=1)
        
        self.persist_obs = []
        
        for i in range(train_split, len(df_btc)):
            row = df_btc.iloc[i]
            curr_time = df_btc.index[i]
            
            # 1. Manage Position
            if self.current_position:
                if self.current_position['type'] == 'long':
                    if row['Low'] <= self.current_position['sl']:
                        self.balance -= self.current_position['risk_amount']
                        self.trades.append({'type': 'long', 'result': 'loss', 'balance': self.balance, 'time': curr_time})
                        self.current_position = None
                    elif row['High'] >= self.current_position['tp']:
                        self.balance += self.current_position['risk_amount'] * 2.0 
                        self.trades.append({'type': 'long', 'result': 'win', 'balance': self.balance, 'time': curr_time})
                        self.current_position = None
                elif self.current_position['type'] == 'short':
                    if row['High'] >= self.current_position['sl']:
                        self.balance -= self.current_position['risk_amount']
                        self.trades.append({'type': 'short', 'result': 'loss', 'balance': self.balance, 'time': curr_time})
                        self.current_position = None
                    elif row['Low'] <= self.current_position['tp']:
                        self.balance += self.current_position['risk_amount'] * 2.0
                        self.trades.append({'type': 'short', 'result': 'win', 'balance': self.balance, 'time': curr_time})
                        self.current_position = None

            # 2. Check for new signals
            if self.current_position is None:
                killzone = self.time_filters.is_killzone(curr_time)
                
                if killzone in ['London', 'NY']:
                    true_open = self.time_filters.get_true_open(df_btc, curr_time)
                    bias_rel_open = self.time_filters.get_price_bias_relative_to_open(row['Close'], true_open)
                    
                    # Update OBs from data
                    new_obs = self.ict_logic.find_order_blocks(df_btc.iloc[:i])
                    # Sync persist_obs (add only new ones)
                    for nob in new_obs:
                        if not any(o['timestamp'] == nob['timestamp'] for o in self.persist_obs):
                            self.persist_obs.append(nob)
                    
                    fvgs = self.ict_logic.detect_fvg(df_btc.iloc[:i])
                    ict_bias, _ = self.ict_logic.get_erl_irl_bias(self.persist_obs, fvgs, row['Close'])
                    
                    last_seq = df_btc['Log_Returns'].iloc[i-60:i].values
                    pred = self.ml_engine.predict(last_seq) if len(last_seq) == 60 else 0
                    
                    if bias_rel_open == "Discount (Buy Zone)" and "Bullish" in ict_bias and pred > 0:
                        active_obs = [ob for ob in self.persist_obs if ob['type'] == 'bullish' and not ob['mitigated']]
                        if active_obs:
                            target_ob = active_obs[-1]
                            entry = self.risk_manager.get_ce_entry(target_ob)
                            sl = target_ob['bottom'] * 0.995
                            tp = entry + (entry - sl) * 2.0
                            
                            self.current_position = {
                                'type': 'long', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk_amount': self.balance * 0.02
                            }
                            target_ob['mitigated'] = True
                            print(f"[{curr_time}] OPEN LONG @ {entry:.2f} (Balance: {self.balance:.2f})")
                    elif bias_rel_open == "Premium (Sell Zone)" and "Bearish" in ict_bias and pred < 0:
                        active_obs = [ob for ob in self.persist_obs if ob['type'] == 'bearish' and not ob['mitigated']]
                        if active_obs:
                            target_ob = active_obs[-1]
                            entry = self.risk_manager.get_ce_entry(target_ob)
                            sl = target_ob['top'] * 1.005
                            tp = entry - (sl - entry) * 2.0
                            
                            self.current_position = {
                                'type': 'short', 'entry': entry, 'sl': sl, 'tp': tp,
                                'risk_amount': self.balance * 0.02
                            }
                            target_ob['mitigated'] = True
                            print(f"[{curr_time}] OPEN SHORT @ {entry:.2f} (Balance: {self.balance:.2f})")
                
                if i % 200 == 0:
                    print(f"[{curr_time}] P:{row['Close']:.2f} Balance:{self.balance:.2f} Trades:{len(self.trades)}")

            self.risk_manager.calculate_drawdown(self.balance)

    def report(self):
        print("\n--- FINAL BACKTEST REPORT ---")
        print(f"Initial Balance: $10000")
        print(f"Final Balance:   ${self.balance:.2f}")
        roi = ((self.balance - 10000) / 10000) * 100
        print(f"ROI:             {roi:.2f}%")
        print(f"Max Drawdown:    {self.risk_manager.max_drawdown * 100:.2f}%")
        
        wins = len([t for t in self.trades if t['result'] == 'win'])
        losses = len([t for t in self.trades if t['result'] == 'loss'])
        total = wins + losses
        if total > 0:
            print(f"Total Trades:    {total}")
            print(f"Win Rate:        {(wins/total)*100:.2f}%")
        else:
            print("No trades executed.")

if __name__ == "__main__":
    backtester = FullBacktester()
    backtester.run()
    backtester.report()
