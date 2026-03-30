import pandas as pd
import numpy as np
import time
import os
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
from ml_brain import MLBrain
from data_engine import DataEngine

class TimeMachineSimulator:
    def __init__(self, asset_yf="BTC-USD", window_train=1000, window_test=500):
        self.asset = asset_yf
        self.window_train = window_train
        self.window_test = window_test
        self.brain = MLBrain()
        self.engine = DataEngine()
        
        # Risk Management
        self.stop_loss = 0.015  # 1.5%
        self.take_profit = 0.03 # 3.0%
        self.prob_threshold = 0.7
        
        # Performance Tracking
        self.equity = 1.0
        self.equity_curve = [1.0]
        self.trades = 0
        self.wins = 0

    def fetch_long_history(self):
        print(f"⏳ Buscando histórico para {self.asset} (1h)...")
        try:
            # We'll use 1 year of data for a more focused backtest (faster training blocks)
            df = yf.download(self.asset, period="1y", interval="1h")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'})
            
            # Synthetic CVD
            np.random.seed(42)
            df['taker_buy_base_volume'] = df['volume'] * (0.5 + np.random.uniform(-0.02, 0.02, size=len(df)))
            buy_vol = df['taker_buy_base_volume']
            sell_vol = df['volume'] - buy_vol
            df['CVD'] = (buy_vol - sell_vol).cumsum()
            
            print(f"✅ Dados carregados: {len(df)} horas")
            return self.engine.apply_indicators(df)
        except Exception as e:
            print(f"❌ Erro ao buscar dados: {e}")
            return pd.DataFrame()

    def run_simulation(self):
        df = self.fetch_long_history()
        if df.empty: return
        
        total_len = len(df)
        start_idx = self.window_train
        
        print(f"\n🚀 SIMULAÇÃO OTIMIZADA (SL: 1.5%, TP: 3.0%, Conf: 70%)\n")
        
        for i in range(start_idx, total_len - self.window_test, self.window_test):
            train_segment = df.iloc[i - self.window_train : i]
            self.brain.train(train_segment, train_full=True)
            
            test_segment = df.iloc[i : i + self.window_test]
            processed_test = self.brain.prepare_features(test_segment)
            if processed_test.empty: continue
            f_cols = [c for c in processed_test.columns if c.startswith('feat_')]
            
            for j in range(len(processed_test)):
                feat_vec = processed_test[f_cols].iloc[j].values
                signal, prob, reason = self.brain.predict_signal(feat_vec, f_cols)
                
                if signal != 0 and prob > self.prob_threshold:
                    self.trades += 1
                    # SL/TP Logic (look ahead in the test segment or until next training)
                    trade_result = 0
                    current_price = processed_test['close'].iloc[j]
                    
                    found_exit = False
                    for k in range(j + 1, len(processed_test)):
                        check_price = processed_test['close'].iloc[k]
                        price_ret = (check_price / current_price) - 1
                        
                        # Apply Long strategy
                        if signal == 1:
                            if price_ret >= self.take_profit:
                                trade_result = self.take_profit; found_exit = True; self.wins += 1; break
                            elif price_ret <= -self.stop_loss:
                                trade_result = -self.stop_loss; found_exit = True; break
                        # Apply Short strategy
                        elif signal == -1:
                            if price_ret <= -self.take_profit:
                                trade_result = self.take_profit; found_exit = True; self.wins += 1; break
                            elif price_ret >= self.stop_loss:
                                trade_result = -self.stop_loss; found_exit = True; break
                    
                    # If no exit hit by end of segment, take current return
                    if not found_exit and j + 1 < len(processed_test):
                        # ⚡ Bolt Optimization: Using `.values[-1]` instead of `.iloc[-1]` for direct numpy memory access.
                        # Eliminates pandas overhead (~10-20µs per lookup) in hot inner backtest loops.
                        final_ret = (processed_test['close'].values[-1] / current_price) - 1
                        trade_result = final_ret * signal
                        if trade_result > 0: self.wins += 1
                    
                    self.equity *= (1 + trade_result)
                    self.equity_curve.append(self.equity)
            
            progress = (i / total_len) * 100
            print(f"🕒 [{progress:4.1f}%] Patrimônio: {self.equity:.4f} | WinRate: {(self.wins/self.trades if self.trades>0 else 0):.1%}")
            
        self.finish_report()

    def finish_report(self):
        print(f"\n{'═'*50}")
        print(f"🏁 FIM DA SIMULAÇÃO (MÁQUINA DO TEMPO)")
        print(f"{'═'*50}")
        print(f"📈 Retorno Total: {(self.equity - 1)*100:.2f}%")
        print(f"📊 Total de Trades: {self.trades}")
        print(f"🎯 Win Rate Final: {(self.wins/self.trades if self.trades > 0 else 0)*100:.2f}%")
        
        # Max Drawdown calculation
        peak = pd.Series(self.equity_curve).expanding().max()
        dd = (pd.Series(self.equity_curve) - peak) / peak
        max_dd = dd.min()
        print(f"📉 Max Drawdown: {max_dd*100:.2f}%")
        print(f"{'═'*50}\n")

if __name__ == "__main__":
    sim = TimeMachineSimulator()
    sim.run_simulation()
