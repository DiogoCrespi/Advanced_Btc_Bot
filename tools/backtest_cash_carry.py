# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
from data_engine import DataEngine
from funding_logic import FundingLogic
from risk_manager import RiskManager
import pandas as pd
import numpy as np

class CashCarryBacktester:
    def __init__(self, initial_balance=10000):
        self.data_engine = DataEngine(period="360d", interval="1h")
        self.logic = FundingLogic(risk_free_rate_annual=0.10)
        self.risk = RiskManager(initial_balance=initial_balance)
        self.balance = initial_balance
        self.active_position = None
        self.trade_history = []

    def run(self, symbol_spot="BTC-USD", symbol_futures="BTCUSDT"):
        print(f"Starting Cash & Carry backtest for {symbol_spot}...")
        
        # 1. Fetch Prices and Funding Rates (1 year back)
        one_year_ago_ms = int((pd.Timestamp.now() - pd.Timedelta(days=365)).timestamp() * 1000)
        df_prices, _ = self.data_engine.fetch_data() # BTC Spot
        df_funding = self.data_engine.fetch_funding_history(symbol=symbol_futures, startTime=one_year_ago_ms)
        
        if df_funding.empty:
            print("Failed to fetch funding history.")
            return
            
        print(f"Prices rows: {len(df_prices)}")
        print(f"Funding rows: {len(df_funding)}")

        # 2. Align Data
        # Ensure indices are localized to None and rounded to Hour
        df_prices.index = df_prices.index.tz_localize(None).round('h')
        df_funding.index = df_funding.index.tz_localize(None).round('h')

        # Funding is typically every 8h. Prices are every 1h.
        combined = df_prices[['Close']].join(df_funding, how='inner')
        if not combined.empty:
            print(f"Aligned data: {len(combined)} rows after inner join.")
            print(f"Data range: {combined.index[0]} to {combined.index[-1]}")
        else:
            print("No overlapping data found.")
            # Print sample to debug
            print("Prices sample index:", df_prices.index[:5])
            print("Funding sample index:", df_funding.index[:5])
            return

        # 3. Simulation Loop
        # Pre-extract arrays for performance
        close_arr = combined['Close'].values
        funding_arr = combined['fundingRate'].values
        time_arr = combined.index

        for i in range(len(combined)):
            time = time_arr[i]
            price = float(close_arr[i])
            funding_rate = float(funding_arr[i])
            
            # Historical fundings for signal (last 5 cycles)
            historical_fundings = funding_arr[max(0, i-5):i+1].tolist()
            
            signal = self.logic.get_signal(funding_rate, historical_fundings)

            # ENTRY
            if self.active_position is None and signal == 1:
                # Alocacao 50/50: Metade Spot, Metade Short Futuros
                pos_value = self.balance / 2
                qty_spot = pos_value / price
                qty_fut = qty_spot # Hedge 1:1
                
                self.active_position = {
                    'entry_time': time,
                    'entry_price': price,
                    'qty': qty_spot,
                    'spot_val': pos_value,
                    'fut_val': pos_value
                }
                print(f"[{time}] ENTRY | Price: ${price:.2f} | Funding Annualized: {self.logic.calculate_annualized_funding(funding_rate)*100:.2f}%")

            # DURING POSITION
            if self.active_position:
                # Receive/Pay Funding
                # P&L = Position Size * Funding Rate
                # Note: Funding na Binance e pago pelo Long para o Short se taxa > 0.
                # Como somos SHORT, recebemos funding positivo.
                funding_pnl = self.active_position['qty'] * price * funding_rate
                self.balance += funding_pnl
                
                # Check Liquidation / Rebalance
                dist, liq_p = self.risk.check_liquidation_risk(self.active_position['entry_price'], price)
                if dist < 0.15: # Risco se < 15%
                    # Simulacao de Margem: No backtest simplificado, apenas registramos o alerta
                    # Em prod, moveriamos fundos do Spot para Futuros.
                    pass

                # EXIT
                if signal == 0:
                    exit_pnl_spot = (price - self.active_position['entry_price']) * self.active_position['qty']
                    exit_pnl_fut = (self.active_position['entry_price'] - price) * self.active_position['qty']
                    
                    # Total P&L do Ativo (Spot + Fut) deve ser ~0 exceto por funding e slippage
                    total_pnl = exit_pnl_spot + exit_pnl_fut
                    # A maior parte do lucro veio do funding acumulado no self.balance
                    
                    self.trade_history.append({
                        'entry': self.active_position['entry_time'],
                        'exit': time,
                        'final_balance': self.balance
                    })
                    print(f"[{time}] EXIT | Final Balance: ${self.balance:.2f} | ROI: {((self.balance-10000)/10000)*100:.2f}%")
                    self.active_position = None

        self.report()

    def report(self):
        roi = ((self.balance - 10000) / 10000) * 100
        print(f"\n--- CASH & CARRY FINAL REPORT ---")
        print(f"Final Balance: ${self.balance:.2f}")
        print(f"Total ROI:     {roi:.2f}%")

if __name__ == "__main__":
    tester = CashCarryBacktester()
    tester.run()
