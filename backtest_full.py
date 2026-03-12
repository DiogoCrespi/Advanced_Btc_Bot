from data_engine import DataEngine
from ml_engine import MLEngine
from ict_logic import ICTLogic
from time_filters import TimeFilters
from risk_manager import RiskManager
import pandas as pd
import numpy as np
from datetime import datetime

class FullBacktester:
    def __init__(self, initial_balance=10000, silent=False):
        self.data_engine = DataEngine()
        self.ml_engine = MLEngine()
        self.ict_logic = ICTLogic()
        self.time_filters = TimeFilters()
        self.risk_manager = RiskManager(initial_balance=initial_balance)
        
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.current_position = None
        self.pending_order = None
        self.silent = silent

    def prepare_data(self):
        if not self.silent:
            print("Fetching and processing data...")
        self.df_btc, self.df_eth = self.data_engine.fetch_data()
        self.df_btc = self.data_engine.apply_indicators(self.df_btc)
        self.df_btc = self.data_engine.check_smt_divergence(self.df_btc, self.df_eth)
        
        # Warm up ML
        self.train_split = int(len(self.df_btc) * 0.8)
        train_data = self.df_btc['Log_Returns'].iloc[1:self.train_split].dropna()
        seqs, lbls = self.ml_engine.prepare_data(train_data)
        self.ml_engine.train_model(seqs, lbls, epochs=1)
        
        # Pre-calculate
        self.all_obs = self.ict_logic.find_order_blocks(self.df_btc)
        self.all_fvgs = self.ict_logic.detect_fvg(self.df_btc)
        
        self.obs_by_time = {}
        for ob in self.all_obs:
            t = ob['timestamp']
            if t not in self.obs_by_time: self.obs_by_time[t] = []
            self.obs_by_time[t].append(ob)
            
        self.all_fvgs_sorted = sorted(self.all_fvgs, key=lambda x: x['timestamp'])

        # Pre-calculate Time Filters for the entire DF
        if not self.silent:
            print("Pre-calculating time filters...")
        self.killzones_pre = []
        self.true_opens_pre = []
        
        # Pre-calculate Midnight Opens (optimized)
        daily_opens = self.df_btc['Open'].resample('D').first()
        self.true_opens_map = daily_opens.to_dict()
        
        for t in self.df_btc.index:
            self.killzones_pre.append(self.time_filters.is_killzone(t))
            self.true_opens_pre.append(self.true_opens_map.get(t.date()))

        # Pre-calculate ML Predictions for the test split
        if not self.silent:
            print("Pre-calculating ML predictions for test split...")
        self.ml_preds = {}
        for i in range(self.train_split, len(self.df_btc)):
            last_seq = self.df_btc['Log_Returns'].iloc[i-60:i].values
            if len(last_seq) == 60:
                self.ml_preds[self.df_btc.index[i]] = self.ml_engine.predict(last_seq)

    def run(self, entry_type='50_ce', rr_ratio=3.0, ml_threshold=0.0, use_smt=True, atr_sl=False):
        if not hasattr(self, 'df_btc'):
            self.prepare_data()
            
        if not self.silent:
            print(f"Running backtest: Entry={entry_type}, RR={rr_ratio}, ML_Thresh={ml_threshold}, SMT={use_smt}, ATR_SL={atr_sl}")
        
        df_btc = self.df_btc
        train_split = self.train_split
        obs_by_time = self.obs_by_time
        all_fvgs_sorted = self.all_fvgs_sorted
        
        # State Reset
        fvg_pointer = 0
        fvgs_up_to_time = [] 
        self.persist_obs = [] 
        self.pending_order = None
        self.current_position = None
        self.balance = self.initial_balance
        self.trades = []
        
        # Reset OB flags
        for ob in self.all_obs:
            ob['mitigated'] = False
            ob['invalid'] = False
        
        for i in range(train_split, len(df_btc)):
            row = df_btc.iloc[i]
            curr_time = df_btc.index[i]
            prev_time = df_btc.index[i-1]
            
            killzone = self.killzones_pre[i]
            true_open = self.true_opens_pre[i]
            
            if prev_time in obs_by_time:
                for ob in obs_by_time[prev_time]:
                    self.persist_obs.append(ob)
            
            while fvg_pointer < len(all_fvgs_sorted) and all_fvgs_sorted[fvg_pointer]['timestamp'] <= prev_time:
                fvgs_up_to_time.append(all_fvgs_sorted[fvg_pointer])
                fvg_pointer += 1
            
            self.persist_obs = self.ict_logic.invalidate_obs(self.persist_obs, row)
            
            # 1. Manage Active Position
            if self.current_position:
                if self.current_position['type'] == 'long':
                    if row['Low'] <= self.current_position['sl']:
                        pnl = self.risk_manager.calculate_pnl_with_fees(
                            self.current_position['entry'], self.current_position['sl'], 
                            self.current_position['position_size'], side='long'
                        )
                        self.balance += pnl
                        self.trades.append({'type': 'long', 'result': 'loss', 'balance': self.balance, 'time': curr_time, 'pnl': pnl})
                        self.current_position = None
                    elif row['High'] >= self.current_position['tp']:
                        pnl = self.risk_manager.calculate_pnl_with_fees(
                            self.current_position['entry'], self.current_position['tp'], 
                            self.current_position['position_size'], side='long'
                        )
                        self.balance += pnl
                        self.trades.append({'type': 'long', 'result': 'win', 'balance': self.balance, 'time': curr_time, 'pnl': pnl})
                        self.current_position = None
                elif self.current_position['type'] == 'short':
                    if row['High'] >= self.current_position['sl']:
                        pnl = self.risk_manager.calculate_pnl_with_fees(
                            self.current_position['entry'], self.current_position['sl'], 
                            self.current_position['position_size'], side='short'
                        )
                        self.balance += pnl
                        self.trades.append({'type': 'short', 'result': 'loss', 'balance': self.balance, 'time': curr_time, 'pnl': pnl})
                        self.current_position = None
                    elif row['Low'] <= self.current_position['tp']:
                        pnl = self.risk_manager.calculate_pnl_with_fees(
                            self.current_position['entry'], self.current_position['tp'], 
                            self.current_position['position_size'], side='short'
                        )
                        self.balance += pnl
                        self.trades.append({'type': 'short', 'result': 'win', 'balance': self.balance, 'time': curr_time, 'pnl': pnl})
                        self.current_position = None

            # 2. Check for entry
            if self.pending_order and self.current_position is None:
                if self.pending_order['type'] == 'long' and row['Low'] <= self.pending_order['entry']:
                    self.current_position = self.pending_order
                    self.pending_order = None
                elif self.pending_order['type'] == 'short' and row['High'] >= self.pending_order['entry']:
                    self.current_position = self.pending_order
                    self.pending_order = None

            # 3. Check for new signals
            if self.current_position is None and self.pending_order is None:
                if killzone in ['London', 'NY']:
                    ict_bias, _ = self.ict_logic.get_erl_irl_bias(self.persist_obs, fvgs_up_to_time, row['Close'])
                    
                    pred = self.ml_preds.get(curr_time, 0)
                    
                    # SMT Check
                    smt_signal = row['SMT_Divergence'] if use_smt else 0
                    
                    # Long Signal: Relaxed (Removal of Midnight Open constraint)
                    if "Bullish" in ict_bias and pred > ml_threshold:
                        if not use_smt or smt_signal == 1:
                            active_obs = [ob for ob in self.persist_obs if ob['type'] == 'bullish' and not ob['mitigated'] and not ob['invalid']]
                            if active_obs:
                                target_ob = active_obs[-1]
                                entry = self.risk_manager.get_entry(target_ob, entry_type)
                                
                                # SL Calculation
                                if atr_sl:
                                    sl = entry - (row['ATR_14'] * 2.0)
                                else:
                                    sl = target_ob['bottom'] * 0.995
                                
                                tp = entry + (entry - sl) * rr_ratio
                                pos_size = self.risk_manager.calculate_position_size(entry, sl)
                                if pos_size > 0:
                                    self.pending_order = {'type': 'long', 'entry': entry, 'sl': sl, 'tp': tp, 'position_size': pos_size}
                                    target_ob['mitigated'] = True
                                    
                    # Short Signal: Relaxed (Removal of Midnight Open constraint)
                    elif "Bearish" in ict_bias and pred < -ml_threshold:
                        if not use_smt or smt_signal == -1:
                            active_obs = [ob for ob in self.persist_obs if ob['type'] == 'bearish' and not ob['mitigated'] and not ob['invalid']]
                            if active_obs:
                                target_ob = active_obs[-1]
                                entry = self.risk_manager.get_entry(target_ob, entry_type)
                                
                                if atr_sl:
                                    sl = entry + (row['ATR_14'] * 2.0)
                                else:
                                    sl = target_ob['top'] * 1.005
                                    
                                tp = entry - (sl - entry) * rr_ratio
                                pos_size = self.risk_manager.calculate_position_size(entry, sl)
                                if pos_size > 0:
                                    self.pending_order = {'type': 'short', 'entry': entry, 'sl': sl, 'tp': tp, 'position_size': pos_size}
                                    target_ob['mitigated'] = True
                                    
            self.risk_manager.calculate_drawdown(self.balance)
        
        return self.get_results()

    def get_results(self):
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        wins = len([t for t in self.trades if t['result'] == 'win'])
        total = len(self.trades)
        win_rate = (wins / total * 100) if total > 0 else 0
        return {
            'roi': roi,
            'win_rate': win_rate,
            'total_trades': total,
            'max_drawdown': self.risk_manager.max_drawdown * 100
        }

    def report(self):
        res = self.get_results()
        print("\n--- FINAL BACKTEST REPORT ---")
        print(f"ROI:             {res['roi']:.2f}%")
        print(f"Win Rate:        {res['win_rate']:.2f}%")
        print(f"Total Trades:    {res['total_trades']}")
        print(f"Max Drawdown:    {res['max_drawdown']:.2f}%")

if __name__ == "__main__":
    backtester = FullBacktester()
    backtester.run()
    backtester.report()
