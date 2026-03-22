from data_engine import DataEngine
from ml_engine import MLEngine
from ict_logic import ICTLogic
from time_filters import TimeFilters
from risk_manager import RiskManager
from datetime import datetime
import pandas as pd
import torch

class AdvancedBtcBot:
    def __init__(self):
        self.data_engine = DataEngine()
        self.ml_engine = MLEngine()
        self.ict_logic = ICTLogic()
        self.time_filters = TimeFilters()
        self.risk_manager = RiskManager()
        
        self.is_trained = False

    def run_simulation(self):
        """
        Runs a simulation on historical data to demonstrate integration.
        """
        # 1. Fetch Data
        df_btc, df_eth = self.data_engine.fetch_data()
        df_btc = self.data_engine.apply_indicators(df_btc)
        df_btc = self.data_engine.check_smt_divergence(df_btc, df_eth)
        
        print(f"Data ready: {len(df_btc)} periods.")

        # 2. Train ML Engine (Simplified for demonstration)
        if not self.is_trained:
            print("Training ML model...")
            seqs, lbls = self.ml_engine.prepare_data(df_btc['Log_Returns'].dropna())
            self.ml_engine.train_model(seqs, lbls, epochs=2)
            self.is_trained = True

        # 3. Main Logic Loop (Simulated for the last 50 days)
        print("\nStarting simulation loop (Last 50 periods)...")
        results = []
        
        for i in range(len(df_btc) - 50, len(df_btc)):
            curr_row = df_btc.iloc[i]
            curr_time = df_btc.index[i]
            
            # A. Time Filters
            killzone = self.time_filters.is_killzone(curr_time)
            true_open = self.time_filters.get_true_open(df_btc, curr_time)
            bias_rel_open = self.time_filters.get_price_bias_relative_to_open(curr_row['Close'], true_open)
            
            # B. Institutional Filters
            obs = self.ict_logic.find_order_blocks(df_btc.iloc[:i])
            fvgs = self.ict_logic.detect_fvg(df_btc.iloc[:i])
            ict_bias, ict_target = self.ict_logic.get_erl_irl_bias(obs, fvgs, curr_row['Close'])
            
            # C. ML Prediction
            last_seq = df_btc['Log_Returns'].iloc[i-60:i].values
            if len(last_seq) == 60 and not pd.isna(last_seq).any():
                pred_log_ret = self.ml_engine.predict(last_seq)
            else:
                pred_log_ret = 0
            
            # D. Execution Logic (SMC + Time + ML)
            signal = "HOLD"
            entry_price = 0
            
            # Simple combined strategy:
            # 1. Must be in Kilzone (London/NY)
            # 2. Must align with True Open (Discount for Buy)
            # 3. Must have Bullish ICT Bias
            if killzone in ['London', 'NY']:
                if bias_rel_open == "Discount (Buy Zone)" and "Bullish" in ict_bias:
                    if pred_log_ret > 0: # ML confirms upside
                        # Find nearest active bullish OB for CE entry
                        active_bull_obs = [ob for ob in obs if ob['type'] == 'bullish' and not ob['mitigated']]
                        if active_bull_obs:
                            target_ob = active_bull_obs[-1]
                            entry_price = self.risk_manager.get_ce_entry(target_ob)
                            signal = f"BUY LIMIT @ {entry_price:.2f}"
            
            results.append({
                'Time': curr_time,
                'Price': curr_row['Close'],
                'Killzone': killzone,
                'ICT_Bias': ict_bias,
                'ML_Pred': pred_log_ret,
                'Signal': signal
            })

        print("Simulation complete. Printing last 5 results:")
        for res in results[-5:]:
            print(res)

if __name__ == "__main__":
    bot = AdvancedBtcBot()
    bot.run_simulation()
