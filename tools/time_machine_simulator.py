# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
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
        print(f"⏳ Buscando historico para {self.asset} (1h)...")
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
        
        print(f"\n🚀 SIMULACAO OTIMIZADA (SL: 1.5%, TP: 3.0%, Conf: 70%)\n")
        
        for i in range(start_idx, total_len - self.window_test, self.window_test):
            train_segment = df.iloc[i - self.window_train : i]
            self.brain.train(train_segment, train_full=True)
            
            test_segment = df.iloc[i : i + self.window_test]
            processed_test = self.brain.prepare_features(test_segment)
            if processed_test.empty: continue
            f_cols = [c for c in processed_test.columns if c.startswith('feat_')]
            
            # Pre-extract arrays for faster lookup in simulation loops
            feat_arr = processed_test[f_cols].values
            close_arr = processed_test['close'].values

            for j in range(len(processed_test)):
                feat_vec = feat_arr[j]
                signal, prob, reason = self.brain.predict_signal(feat_vec, f_cols)
                
                if signal != 0 and prob > self.prob_threshold:
                    self.trades += 1
                    # SL/TP Logic (look ahead in the test segment or until next training)
                    current_price = float(close_arr[j])
                    future_closes = close_arr[j+1:]
                    
                    if len(future_closes) == 0:
                        trade_result = 0
                    else:
                        price_rets = (future_closes / current_price) - 1.0
                        
                        if signal == 1:
                            tp_cond = price_rets >= self.take_profit
                            sl_cond = price_rets <= -self.stop_loss
                        else:
                            tp_cond = price_rets <= -self.take_profit
                            sl_cond = price_rets >= self.stop_loss

                        tp_idx = np.argmax(tp_cond) if tp_cond.any() else -1
                        sl_idx = np.argmax(sl_cond) if sl_cond.any() else -1

                        if tp_idx != -1 and sl_idx != -1:
                            if tp_idx < sl_idx:
                                trade_result = self.take_profit
                                self.wins += 1
                            else:
                                trade_result = -self.stop_loss
                        elif tp_idx != -1:
                            trade_result = self.take_profit
                            self.wins += 1
                        elif sl_idx != -1:
                            trade_result = -self.stop_loss
                        else:
                            final_ret = float(price_rets[-1]) * signal
                            trade_result = final_ret
                            if final_ret > 0: self.wins += 1
                    
                    self.equity *= (1 + trade_result)
                    self.equity_curve.append(self.equity)
            
            progress = (i / total_len) * 100
            print(f"🕒 [{progress:4.1f}%] Patrimonio: {self.equity:.4f} | WinRate: {(self.wins/self.trades if self.trades>0 else 0):.1%}")
            
        self.finish_report()

    def finish_report(self):
        print(f"\n{'═'*50}")
        print(f"🏁 FIM DA SIMULACAO (MAQUINA DO TEMPO)")
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
