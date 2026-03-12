from data_engine import DataEngine
from ml_engine import MLEngine
from ict_logic import ICTLogic
from time_filters import TimeFilters
from risk_manager import RiskManager
from binance_ws import BinanceWS
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os

class RealtimeBtcBot:
    def __init__(self, symbol="btcusdt"):
        self.symbol = symbol
        self.data_engine = DataEngine()
        self.ml_engine = MLEngine()
        self.ict_logic = ICTLogic()
        self.time_filters = TimeFilters()
        self.risk_manager = RiskManager()
        
        self.df = None
        self.is_trained = False
        self.last_candle_time = 0
        
        # Buffer for live data
        self.current_live_price = 0

    def warm_up(self):
        """
        Fetches historical data to warm up indicators and train ML.
        """
        print("Warming up with historical data...")
        df_btc, df_eth = self.data_engine.fetch_data()
        df_btc = self.data_engine.apply_indicators(df_btc)
        df_btc = self.data_engine.check_smt_divergence(df_btc, df_eth)
        self.df = df_btc
        
        print(f"Data warmed up: {len(self.df)} periods.")

        # Train ML
        print("Training ML model on historical data...")
        seqs, lbls = self.ml_engine.prepare_data(self.df['Log_Returns'].dropna())
        self.ml_engine.train_model(seqs, lbls, epochs=2)
        self.is_trained = True
        print("ML Model trained and ready.")

    def process_tick(self, ticker):
        """
        Callback for BinanceWS. Processes each real-time price tick.
        """
        self.current_live_price = ticker['price']
        curr_time = datetime.fromtimestamp(ticker['time'] / 1000)
        
        # Check if we have a new day/period (simplified to every update for testing)
        # In a real bot, we'd wait for a new 1h/4h/1d candle.
        
        # Execute logic
        self.run_logic(curr_time)

    def run_logic(self, curr_time):
        """
        Main decision engine based on the current live price.
        """
        if self.df is None or not self.is_trained:
            return

        # 1. Update current bias relative to Open
        true_open = self.time_filters.get_true_open(self.df, curr_time)
        bias_rel_open = self.time_filters.get_price_bias_relative_to_open(self.current_live_price, true_open)
        
        # 2. Check Killzone
        killzone = self.time_filters.is_killzone(curr_time)
        
        # 3. ICT/SMC Filters
        obs = self.ict_logic.find_order_blocks(self.df)
        fvgs = self.ict_logic.detect_fvg(self.df)
        ict_bias, ict_target = self.ict_logic.get_erl_irl_bias(obs, fvgs, self.current_live_price)
        
        # 4. ML Prediction (on latest data)
        last_seq = self.df['Log_Returns'].tail(60).values
        pred_log_ret = 0
        if len(last_seq) == 60:
            pred_log_ret = self.ml_engine.predict(last_seq)
            
        # 5. Signal Convergence
        status_msg = f"[{curr_time}] PRICE: {self.current_live_price} | ZONE: {killzone if killzone else 'DeadZone'} | ICT: {ict_bias} | ML: {pred_log_ret:.6f}"
        print(status_msg)
        
        if killzone in ['London', 'NY']:
            if bias_rel_open == "Discount (Buy Zone)" and "Bullish" in ict_bias and pred_log_ret > 0:
                print(f">>> SIGNAL: BULLISH CONVERGENCE detected at {self.current_live_price}")
            elif bias_rel_open == "Premium (Sell Zone)" and "Bearish" in ict_bias and pred_log_ret < 0:
                print(f">>> SIGNAL: BEARISH CONVERGENCE detected at {self.current_live_price}")
        else:
            # Low probability window
            pass

    def start(self):
        self.warm_up()
        print(f"Starting Real-time Monitoring for {self.symbol}...")
        self.ws = BinanceWS(symbol=self.symbol, callback=self.process_tick)
        self.ws.start()
        
        try:
            while True:
                time.sleep(5) # Keep main thread alive
        except KeyboardInterrupt:
            print("Shutting down real-time bot...")
            self.ws.stop()

if __name__ == "__main__":
    bot = RealtimeBtcBot()
    bot.start()
